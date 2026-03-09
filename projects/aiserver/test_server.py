import httpx
import pytest
import json


BASE = "http://localhost:8080"


@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "ollama_connected" in data


@pytest.mark.asyncio
async def test_defaults():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE}/defaults")
        assert resp.status_code == 200
        data = resp.json()
        assert "default_model" in data
        assert "aliases" in data
        assert "default_options" in data


@pytest.mark.asyncio
async def test_generate_stream():
    async with httpx.AsyncClient(timeout=30.0) as client:
        req = {"prompt": "Say hello in one word.", "model": "q06"}
        async with client.stream("POST", f"{BASE}/generate", json=req) as resp:
            assert resp.status_code == 200
            chunks = []
            async for line in resp.aiter_lines():
                if line:
                    chunks.append(json.loads(line))
            assert len(chunks) > 0
            assert chunks[-1]["done"] is True


@pytest.mark.asyncio
async def test_stats():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_requests" in data
        assert "active_streams" in data
