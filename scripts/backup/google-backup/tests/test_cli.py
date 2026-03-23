"""Tests for CLI argument parsing and dispatch."""
from google_backup.__main__ import parse_args


def test_parse_all_flag():
    args = parse_args(["--all"])
    assert args.all is True


def test_parse_individual_services():
    args = parse_args(["--gmail", "--contacts"])
    assert args.gmail is True
    assert args.contacts is True
    assert args.calendar is False


def test_parse_status_flag():
    args = parse_args(["--status"])
    assert args.status is True


def test_parse_auth_command():
    args = parse_args(["auth"])
    assert args.command == "auth"


def test_default_is_sync_command():
    args = parse_args(["--all"])
    assert args.command == "sync"
