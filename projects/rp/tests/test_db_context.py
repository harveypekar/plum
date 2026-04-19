"""Tests for pipeline context storage on add_message."""

import pytest


@pytest.mark.asyncio
async def test_add_message_stores_pipeline_context(tmp_path):
    """add_message with context kwargs stores them on the row."""
    from projects.rp.db import add_message

    import inspect
    sig = inspect.signature(add_message)
    params = list(sig.parameters.keys())
    assert "system_prompt" in params
    assert "scene_state" in params
    assert "post_prompt" in params


@pytest.mark.asyncio
async def test_add_message_signature_defaults_to_none():
    """New params default to None so existing callers don't break."""
    from projects.rp.db import add_message

    import inspect
    sig = inspect.signature(add_message)
    assert sig.parameters["system_prompt"].default is None
    assert sig.parameters["scene_state"].default is None
    assert sig.parameters["post_prompt"].default is None
