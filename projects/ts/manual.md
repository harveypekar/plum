# Terminal Server

Async TCP server with styled text and Ollama streaming. No dependencies beyond Python stdlib.

## Quick Start

```
python main.py
```

Starts a server on port 4040 and connects a terminal. Type a prompt, see Ollama's response stream token-by-token.

Requires Ollama running locally (`ollama serve`).

## Components

| Class | Purpose |
|-------|---------|
| `Color` | Enum of 8 ANSI colors: BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE |
| `Span` | Dataclass: `text` + optional `fg`/`bg` Color |
| `StyledText` | Chainable builder over spans with ANSI rendering and JSON round-trip |
| `Server` | Async TCP server, accepts terminal connections, dispatches messages |
| `Terminal` | Connects to server, sends strings, prints styled/streamed responses |
| `OllamaClient` | Sends prompts to local Ollama, streams tokens as an async generator |

## StyledText

Build colored text by chaining `.add()` calls:

```python
msg = (StyledText()
    .add("Error: ", fg=Color.RED)
    .add("file not found", fg=Color.WHITE, bg=Color.RED)
    .add(" (see log)"))
```

Methods:

| Method | Returns |
|--------|---------|
| `.add(text, *, fg=None, bg=None)` | `self` (for chaining) |
| `.render()` | String with ANSI escape codes |
| `.plain()` | Plain text, no ANSI |
| `.to_dict()` | `list[dict]` for JSON serialization |
| `StyledText.from_dict(data)` | New StyledText from deserialized dicts |

## Server

```python
server = Server(host="localhost", port=4040)

async def handle(server, client_id: int, text: str):
    await server.send(client_id, StyledText().add("echo: " + text))

server.on_message = handle
await server.start()
# ... later ...
await server.stop()
```

Handler signature: `async (server: Server, client_id: int, text: str) -> None`

The handler receives the server instance so it can call send/stream methods directly.

### Server Methods

| Method | Description |
|--------|-------------|
| `start()` | Begin accepting connections |
| `stop()` | Close the server |
| `send(client_id, styled)` | Send a complete styled message |
| `broadcast(styled)` | Send to all connected terminals |
| `stream_start(client_id)` | Signal start of streaming response |
| `stream_chunk(client_id, styled)` | Send one inline chunk (no newline) |
| `stream_end(client_id)` | Signal end of stream (terminal prints newline) |

## Terminal

```python
term = Terminal()
await term.connect("localhost", 4040)
await term.send("hello")
await term.input_loop()   # blocks, reads stdin lines
await term.disconnect()
```

The terminal handles all message types automatically:
- `output` — prints with newline
- `stream_chunk` — prints inline (no newline, flushed)
- `stream_end` — prints newline

## OllamaClient

```python
ollama = OllamaClient(model="qwen", base_url="http://localhost:11434")

# Streaming (token by token):
async for token in ollama.generate_stream("Why is the sky blue?"):
    print(token, end="", flush=True)

# Complete response:
response = await ollama.generate("Why is the sky blue?")
```

## Protocol

Newline-delimited JSON over TCP. Each message is one JSON object followed by `\n`.

### Client to Server

```json
{"type": "input", "text": "user's message"}
```

### Server to Client

Complete message:
```json
{"type": "output", "spans": [{"text": "hello", "fg": "GREEN", "bg": "BLUE"}]}
```

Streaming (3-frame sequence):
```json
{"type": "stream_start"}
{"type": "stream_chunk", "spans": [{"text": "token"}]}
{"type": "stream_chunk", "spans": [{"text": " by"}]}
{"type": "stream_chunk", "spans": [{"text": " token"}]}
{"type": "stream_end"}
```

Span fields: `text` (required), `fg` (optional Color name), `bg` (optional Color name).

## Streaming Pattern

Wire an Ollama streaming response through to the terminal:

```python
async def handle(server, client_id, text):
    await server.stream_start(client_id)
    await server.stream_chunk(client_id, StyledText().add("ollama> ", fg=Color.GREEN))
    async for token in ollama.generate_stream(text):
        await server.stream_chunk(client_id, StyledText().add(token))
    await server.stream_end(client_id)
```

## Files

| File | Purpose |
|------|---------|
| `main.py` | All components + demo entry point |
| `server.py` | (empty, reserved for future extraction) |
| `tests.py` | (empty, reserved for tests) |
