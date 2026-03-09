# aiserver — Design Document

Date: 2026-03-09

## Overview

A FastAPI-based HTTP server wrapping Ollama for LLM inference. Provides a clean REST API with model aliases, configurable defaults, NDJSON streaming, and a web UI for monitoring and interactive prompt testing.

## Goals

- Extract and improve the OllamaClient from `projects/ts/main.py` into a standalone, reusable server
- Provide a unified API that any project in the monorepo can use for LLM inference
- Offer a web dashboard for real-time monitoring and a playground for prompt testing

## Architecture

Thin proxy over Ollama's `/api/generate` endpoint. FastAPI handles routing and validation, httpx handles async communication with Ollama.

```
┌────────────┐     ┌──────────────────┐     ┌──────────┐
│  Clients   │────►│  aiserver        │────►│  Ollama  │
│  (ts, etc) │◄────│  (FastAPI+httpx) │◄────│          │
└────────────┘     └───────┬──────────┘     └──────────┘
                           │
                   ┌───────▼──────────┐
                   │  Web UI          │
                   │  (dashboard +    │
                   │   playground)    │
                   └──────────────────┘
```

## Project Structure

```
projects/aiserver/
├── main.py              # FastAPI app, entry point, uvicorn runner
├── ollama.py            # OllamaClient (async, streaming via httpx)
├── config.py            # Model aliases, parameter defaults, settings loader
├── config.json          # Configuration file
├── models.py            # Pydantic request/response schemas
├── requirements.txt     # fastapi, uvicorn, httpx
└── static/
    ├── index.html       # Dashboard view
    ├── playground.html  # Prompt playground view
    ├── dashboard.js     # Dashboard logic (WebSocket)
    └── playground.js    # Playground logic (NDJSON streaming)
```

## API Endpoints

### `POST /generate`

Main inference endpoint. Streams NDJSON response.

Request:
```json
{
  "prompt": "Explain quantum computing",
  "model": "q8",
  "system": "You are a helpful assistant.",
  "options": {
    "temperature": 0.7,
    "num_predict": 512,
    "top_p": 0.9,
    "top_k": 40,
    "think": false
  }
}
```

- `prompt` — required
- `model` — optional, falls back to server default
- `system` — optional
- `options` — optional, each field falls back to configured defaults

Response (NDJSON stream):
```json
{"token": "Quantum", "done": false}
{"token": " computing", "done": false}
{"token": "", "done": true, "total_tokens": 84, "tokens_per_second": 42.1}
```

### `GET /defaults`

Returns current defaults and available model aliases.

```json
{
  "default_model": "q8",
  "aliases": {
    "q8": "qwen3:8b",
    "q4": "qwen3:4b"
  },
  "default_options": {
    "temperature": 0.7,
    "num_predict": 1024,
    "top_p": 0.9,
    "top_k": 40,
    "think": false
  }
}
```

### `GET /health`

Health check. Verifies Ollama connectivity.

### `GET /stats`

Aggregate statistics snapshot (requests/hour, avg tokens/sec).

### `WS /ws/dashboard`

WebSocket endpoint pushing real-time events to connected dashboards:
- Request log entries (prompt, model, tokens, latency)
- Active streaming sessions
- Ollama status changes

## Configuration

`config.json` in the aiserver directory:

```json
{
  "ollama_url": "http://localhost:11434",
  "host": "0.0.0.0",
  "port": 8080,
  "default_model": "q8",
  "aliases": {
    "q06": "qwen3:0.6b",
    "q17": "qwen3:1.7b",
    "q4": "qwen3:4b",
    "q8": "qwen3:8b"
  },
  "default_options": {
    "temperature": 0.7,
    "num_predict": 1024,
    "top_p": 0.9,
    "top_k": 40,
    "think": false
  }
}
```

Model resolution order:
1. If the requested model matches an alias key, resolve to the alias value
2. Otherwise, pass the model name directly to Ollama

Options resolution: per-request options override defaults. Missing fields fall back to `default_options`.

## OllamaClient

Extracted from `projects/ts/main.py` with improvements:

- Fully async using httpx (replaces urllib.request + thread + asyncio.Queue)
- Async generator for streaming: `async for token in client.generate_stream(...)`
- Thinking support preserved — yields `{"token": "...", "thinking": true/false, "done": false}`
- Token counting kept as `len(text) // 4` estimate
- Clear error handling for Ollama connection failures and model-not-found

## Web UI

Served by FastAPI as static files. Vanilla HTML/JS, no build step.

### Dashboard (`index.html`)
- Real-time updates via WebSocket (`/ws/dashboard`)
- Ollama status and available models
- Live request log (prompt, model, tokens, latency)
- Active streaming sessions
- Aggregate stats (requests/hour, avg tokens/sec)

### Playground (`playground.html`)
- Single-turn prompt tester
- Model selector (aliases + raw names)
- Parameter controls (temperature, num_predict, top_p, top_k, think)
- Prompt input with streamed NDJSON response rendered live

## Impact on ts Project

The ts project's inline `OllamaClient` in `main.py` will be replaced with an import from aiserver. The ts project will depend on aiserver's `ollama.py` module.

## Future Work (GitHub Issues)

- **TCP support**: JSON-delimited messages over TCP for persistent/streaming connections
- **Full service layer**: Request queuing, rate limiting, logging/metrics, job-based API
