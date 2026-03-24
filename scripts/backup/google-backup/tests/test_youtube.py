"""Tests for YouTube backup service."""
import json
from unittest.mock import MagicMock, patch

from google_backup.services.youtube import YouTubeService
from google_backup.state import ServiceState


def _mock_youtube_api(subscriptions, playlists, playlist_items, liked_videos):
    """Build a mock YouTube API service."""
    service = MagicMock()

    # subscriptions().list() + pagination on resource
    sub_mock = MagicMock()
    sub_mock.execute.return_value = {"items": subscriptions}
    service.subscriptions.return_value.list.return_value = sub_mock
    service.subscriptions.return_value.list_next.return_value = None

    # playlists().list() + pagination on resource
    pl_mock = MagicMock()
    pl_mock.execute.return_value = {"items": playlists}
    service.playlists.return_value.list.return_value = pl_mock
    service.playlists.return_value.list_next.return_value = None

    # playlistItems().list() + pagination on resource
    def _playlist_items(playlistId, **kwargs):
        mock = MagicMock()
        mock.execute.return_value = {"items": playlist_items.get(playlistId, [])}
        return mock
    service.playlistItems.return_value.list.side_effect = _playlist_items
    service.playlistItems.return_value.list_next.return_value = None

    # videos().list() + pagination on resource
    vid_mock = MagicMock()
    vid_mock.execute.return_value = {"items": liked_videos}
    service.videos.return_value.list.return_value = vid_mock
    service.videos.return_value.list_next.return_value = None

    return service


def test_youtube_sync_creates_files(tmp_path):
    subs = [{"snippet": {"resourceId": {"channelId": "UC1"}, "title": "Channel One"}}]
    playlists = [{"id": "PL1", "snippet": {"title": "Favorites"}}]
    playlist_items = {"PL1": [{"snippet": {"resourceId": {"videoId": "vid1"}}}]}
    liked = [{"id": "vid2", "snippet": {"title": "Cool Video"}}]

    mock_api = _mock_youtube_api(subs, playlists, playlist_items, liked)
    state = ServiceState.load(tmp_path / "state", "youtube")

    with patch("google_backup.services.youtube.build", return_value=mock_api):
        svc = YouTubeService()
        result = svc.sync(MagicMock(), state, tmp_path / "youtube")

    assert result.items_synced > 0
    assert (tmp_path / "youtube" / "subscriptions.json").exists()
    assert (tmp_path / "youtube" / "liked_videos.json").exists()
    assert (tmp_path / "youtube" / "playlists" / "PL1.json").exists()


def test_youtube_logs_removed_subscriptions(tmp_path, caplog):
    """When a subscription disappears between runs, it should be logged."""
    backup_dir = tmp_path / "youtube"
    backup_dir.mkdir(parents=True)

    # Previous run had two subscriptions
    (backup_dir / "subscriptions.json").write_text(json.dumps([
        {"snippet": {"resourceId": {"channelId": "UC1"}, "title": "Channel One"}},
        {"snippet": {"resourceId": {"channelId": "UC2"}, "title": "Channel Two"}},
    ]))

    # Current run has only one
    subs = [{"snippet": {"resourceId": {"channelId": "UC1"}, "title": "Channel One"}}]
    mock_api = _mock_youtube_api(subs, [], {}, [])
    state = ServiceState.load(tmp_path / "state", "youtube")

    with patch("google_backup.services.youtube.build", return_value=mock_api):
        import logging
        with caplog.at_level(logging.INFO, logger="google_backup.services.youtube"):
            svc = YouTubeService()
            svc.sync(MagicMock(), state, backup_dir)

    assert any("Channel Two" in r.message for r in caplog.records)
