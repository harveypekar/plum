"""Tests for priority queue and related models."""

import sys
from pathlib import Path

# Allow imports from aiserver directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models import ChatRequest, GenerateRequest, QueueStatusResponse


def test_generate_request_has_priority_default_zero():
    req = GenerateRequest(prompt="hello")
    assert req.priority == 0


def test_chat_request_defaults():
    req = ChatRequest(messages=[{"role": "user", "content": "hi"}])
    assert req.priority == 5
    assert req.stream is True
    assert req.model is None
    assert req.stop is None


def test_chat_request_custom():
    req = ChatRequest(
        messages=[{"role": "user", "content": "hi"}],
        model="q8",
        priority=0,
        stream=False,
        stop=["User:"],
    )
    assert req.priority == 0
    assert req.stream is False
    assert req.stop == ["User:"]


def test_queue_status_response():
    resp = QueueStatusResponse(
        entries=[],
        active=None,
        total=0,
    )
    assert resp.total == 0
