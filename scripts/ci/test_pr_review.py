#!/usr/bin/env python3
"""Tests for pr-review.py — unit tests for the review agent logic."""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

sys.path.insert(0, os.path.dirname(__file__))

# Import after path setup
import importlib
pr_review = importlib.import_module("pr-review")


class TestDiffTruncation(unittest.TestCase):
    """Verify large diffs get truncated before sending to the API."""

    @patch.object(pr_review, "urlopen")
    def test_large_diff_is_truncated(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "content": [{"text": "Looks good."}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        big_diff = "x" * 200_000
        result = pr_review.call_claude(
            big_diff, {"title": "test", "body": "test"}, "fake-key"
        )

        # Check the request body was truncated
        call_args = mock_urlopen.call_args
        sent_request = call_args[0][0]
        sent_body = json.loads(sent_request.data)
        user_content = sent_body["messages"][0]["content"]
        assert "truncated" in user_content
        assert len(user_content) < 200_000
        assert result == "Looks good."

    @patch.object(pr_review, "urlopen")
    def test_small_diff_not_truncated(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "content": [{"text": "LGTM"}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        small_diff = "--- a/file.py\n+++ b/file.py\n+print('hi')"
        result = pr_review.call_claude(
            small_diff, {"title": "test", "body": ""}, "fake-key"
        )

        call_args = mock_urlopen.call_args
        sent_request = call_args[0][0]
        sent_body = json.loads(sent_request.data)
        user_content = sent_body["messages"][0]["content"]
        assert "truncated" not in user_content
        assert result == "LGTM"


class TestAPIError(unittest.TestCase):
    """Verify API errors are handled gracefully."""

    @patch.object(pr_review, "urlopen")
    def test_api_error_exits(self, mock_urlopen):
        error = HTTPError(
            "https://api.anthropic.com/v1/messages",
            429, "Rate limited", {}, None
        )
        mock_urlopen.side_effect = error

        with self.assertRaises(SystemExit) as ctx:
            pr_review.call_claude(
                "diff", {"title": "t", "body": ""}, "fake-key"
            )
        assert ctx.exception.code == 1


class TestRequestFormat(unittest.TestCase):
    """Verify the API request is well-formed."""

    @patch.object(pr_review, "urlopen")
    def test_request_has_correct_headers(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "content": [{"text": "ok"}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        pr_review.call_claude("diff", {"title": "t", "body": ""}, "test-key")

        sent_request = mock_urlopen.call_args[0][0]
        assert sent_request.get_header("X-api-key") == "test-key"
        assert sent_request.get_header("Content-type") == "application/json"
        assert sent_request.get_header("Anthropic-version") == "2023-06-01"

    @patch.object(pr_review, "urlopen")
    def test_request_uses_correct_model(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "content": [{"text": "ok"}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        pr_review.call_claude("diff", {"title": "t", "body": ""}, "key")

        sent_request = mock_urlopen.call_args[0][0]
        sent_body = json.loads(sent_request.data)
        assert sent_body["model"] == "claude-sonnet-4-6"
        assert sent_body["system"] == pr_review.SYSTEM_PROMPT


class TestBinaryDiffHandling(unittest.TestCase):
    """Verify diffs with binary content don't crash."""

    @patch("subprocess.run")
    def test_binary_diff_decoded_safely(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=b"--- a/img.png\n+++ b/img.png\n\xff\xfe binary"
        )
        result = pr_review.get_pr_diff("1", "owner/repo")
        assert isinstance(result, str)
        assert "binary" in result


class TestPRSizeWarning(unittest.TestCase):
    """Verify large PRs get a size warning appended."""

    @patch("subprocess.run")
    def test_large_pr_stats(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout='{"additions": 5000, "deletions": 100}'
        )
        stats = pr_review.get_pr_stats("1", "owner/repo")
        assert stats["additions"] == 5000


class TestMissingEnvVars(unittest.TestCase):
    """Verify main exits when required env vars are missing."""

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_vars_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            pr_review.main()
        assert ctx.exception.code == 1


if __name__ == "__main__":
    unittest.main()
