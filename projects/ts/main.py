"""Terminal server with styled text support.

Manual
======

Components:
    Color       -- Enum of 8 standard ANSI colors (BLACK, RED, GREEN, etc.)
    Span        -- A piece of text with optional fg/bg color
    StyledText  -- Chainable builder for colored text
    Server      -- Async TCP server that accepts terminal connections
    Terminal    -- Client that connects to a server, sends input, displays output

StyledText usage:
    msg = (StyledText()
        .add("Error: ", fg=Color.RED)
        .add("file not found", fg=Color.WHITE, bg=Color.RED))
    print(msg.render())        # prints with ANSI color codes
    print(msg.plain())         # prints without colors
    data = msg.to_dict()       # serialize to list of dicts (for JSON)
    msg2 = StyledText.from_dict(data)  # deserialize back

Server usage:
    server = Server(host="localhost", port=4040)

    async def handle(server, client_id: int, text: str):
        await server.send(client_id, StyledText().add(f"You said: {text}", fg=Color.GREEN))

    server.on_message = handle     # signature: async (server, client_id, text) -> None
    await server.start()                        # begins accepting connections
    await server.send(client_id, styled_text)   # send to one client
    await server.broadcast(styled_text)         # send to all clients
    await server.stop()

Terminal usage:
    term = Terminal()
    await term.connect("localhost", 4040)
    await term.send("hello")       # send a string to the server
    await term.input_loop()        # read stdin lines and send them (blocking)
    await term.disconnect()

Protocol (newline-delimited JSON over TCP):
    Client -> Server:  {"type": "input", "text": "..."}
    Server -> Client:  {"type": "output", "spans": [{"text": "...", "fg": "RED", "bg": "BLUE"}, ...]}
    Server -> Client:  {"type": "stream_start"}
    Server -> Client:  {"type": "stream_chunk", "spans": [...]}
    Server -> Client:  {"type": "stream_end"}

Streaming:
    For LLM responses, the server sends stream_start, then one stream_chunk per
    token (printed inline without newline), then stream_end (prints a newline).

    async def handle(server, client_id, text):
        await server.stream_start(client_id)
        async for token in ollama.generate_stream(text):
            await server.stream_chunk(client_id, StyledText().add(token))
        await server.stream_end(client_id)

    server.on_message = handle

Running the demo:
    python main.py
    Starts a server on port 4040 and connects a terminal to it.
    Type a prompt and see Ollama's response stream in real-time.
"""

import asyncio
import json
import sys
import urllib.request
from dataclasses import dataclass
from enum import Enum


class Color(Enum):
    """Standard ANSI terminal colors (codes 0-7)."""
    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    WHITE = 7


@dataclass
class Span:
    """A segment of text with optional foreground/background color."""
    text: str
    fg: Color | None = None
    bg: Color | None = None


class StyledText:
    """Text composed of colored spans. Chainable builder, ANSI rendering, JSON round-trip."""

    def __init__(self):
        self.spans: list[Span] = []

    def add(self, text: str, *, fg: Color | None = None, bg: Color | None = None) -> "StyledText":
        """Append a styled span. Returns self for chaining."""
        self.spans.append(Span(text, fg, bg))
        return self

    def render(self) -> str:
        """Render to a string with ANSI escape codes."""
        parts = []
        for s in self.spans:
            codes = []
            if s.fg is not None:
                codes.append(str(30 + s.fg.value))
            if s.bg is not None:
                codes.append(str(40 + s.bg.value))
            if codes:
                parts.append(f"\033[{';'.join(codes)}m{s.text}\033[0m")
            else:
                parts.append(s.text)
        return "".join(parts)

    def plain(self) -> str:
        """Return the text content without any ANSI codes."""
        return "".join(s.text for s in self.spans)

    def to_dict(self) -> list[dict]:
        result = []
        for s in self.spans:
            d: dict = {"text": s.text}
            if s.fg is not None:
                d["fg"] = s.fg.name
            if s.bg is not None:
                d["bg"] = s.bg.name
            result.append(d)
        return result

    @classmethod
    def from_dict(cls, data: list[dict]) -> "StyledText":
        st = cls()
        for d in data:
            fg = Color[d["fg"]] if "fg" in d else None
            bg = Color[d["bg"]] if "bg" in d else None
            st.spans.append(Span(d["text"], fg, bg))
        return st

    def __str__(self) -> str:
        return self.render()

    def __repr__(self) -> str:
        return f"StyledText({self.spans!r})"


# -- Protocol helpers --


async def _send(writer: asyncio.StreamWriter, msg: dict):
    writer.write((json.dumps(msg) + "\n").encode())
    await writer.drain()


async def _recv(reader: asyncio.StreamReader) -> dict | None:
    line = await reader.readline()
    if not line:
        return None
    return json.loads(line.decode())


class Server:
    """Async TCP server. Set on_message to handle incoming strings from terminals."""

    def __init__(self, host: str = "localhost", port: int = 0):
        self.host = host
        self.port = port
        # async (client_id: int, text: str) -> StyledText | None
        self.on_message = None
        self._clients: dict[int, asyncio.StreamWriter] = {}
        self._server: asyncio.Server | None = None
        self._next_id = 0

    async def start(self):
        self._server = await asyncio.start_server(
            self._on_connect, self.host, self.port
        )
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def send(self, client_id: int, styled: StyledText):
        """Send styled text to a specific terminal."""
        writer = self._clients.get(client_id)
        if writer:
            await _send(writer, {"type": "output", "spans": styled.to_dict()})

    async def stream_start(self, client_id: int):
        """Signal the start of a streaming response."""
        writer = self._clients.get(client_id)
        if writer:
            await _send(writer, {"type": "stream_start"})

    async def stream_chunk(self, client_id: int, styled: StyledText):
        """Send one chunk of a streaming response (printed inline, no newline)."""
        writer = self._clients.get(client_id)
        if writer:
            await _send(writer, {"type": "stream_chunk", "spans": styled.to_dict()})

    async def stream_end(self, client_id: int):
        """Signal the end of a streaming response."""
        writer = self._clients.get(client_id)
        if writer:
            await _send(writer, {"type": "stream_end"})

    async def broadcast(self, styled: StyledText):
        """Send styled text to all connected terminals."""
        for cid in list(self._clients):
            await self.send(cid, styled)

    async def _on_connect(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        cid = self._next_id
        self._next_id += 1
        self._clients[cid] = writer
        try:
            while (msg := await _recv(reader)) is not None:
                if msg.get("type") == "input" and self.on_message:
                    # Handler signature: async (server, client_id, text) -> None
                    await self.on_message(self, cid, msg["text"])
        finally:
            self._clients.pop(cid, None)
            writer.close()


class Terminal:
    """Terminal client. Connects to a server, sends strings, prints styled responses."""

    def __init__(self):
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._recv_task: asyncio.Task | None = None

    async def connect(self, host: str, port: int):
        self._reader, self._writer = await asyncio.open_connection(host, port)
        self._recv_task = asyncio.create_task(self._recv_loop())

    async def disconnect(self):
        if self._recv_task:
            self._recv_task.cancel()
        if self._writer:
            self._writer.close()

    async def send(self, text: str):
        """Send a string to the server."""
        if self._writer:
            await _send(self._writer, {"type": "input", "text": text})

    async def _recv_loop(self):
        while self._reader:
            msg = await _recv(self._reader)
            if msg is None:
                break
            mtype = msg.get("type")
            if mtype == "output":
                styled = StyledText.from_dict(msg["spans"])
                print(styled.render())
            elif mtype == "stream_chunk":
                styled = StyledText.from_dict(msg["spans"])
                print(styled.render(), end="", flush=True)
            elif mtype == "stream_end":
                print()  # newline after stream completes

    async def input_loop(self):
        """Read lines from stdin and send to server. Blocks until EOF/^C."""
        loop = asyncio.get_event_loop()
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            await self.send(line.strip())


# -- Ollama client --


class OllamaClient:
    """Sends prompts to a local Ollama instance."""

    def __init__(self, model: str = "qwen", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    async def generate_stream(self, prompt: str):
        """Async generator yielding response tokens as they arrive."""
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def _read_stream():
            with urllib.request.urlopen(req, timeout=120) as resp:
                for line in resp:
                    data = json.loads(line.decode())
                    token = data.get("response", "")
                    if token:
                        loop.call_soon_threadsafe(queue.put_nowait, token)
                    if data.get("done"):
                        break
            loop.call_soon_threadsafe(queue.put_nowait, None)

        asyncio.get_event_loop().run_in_executor(None, _read_stream)

        while True:
            token = await queue.get()
            if token is None:
                break
            yield token

    async def generate(self, prompt: str) -> str:
        """Send prompt, wait for complete response."""
        tokens = []
        async for token in self.generate_stream(prompt):
            tokens.append(token)
        return "".join(tokens)


# -- Demo --


async def main():
    server = Server(port=4040)
    ollama = OllamaClient()

    async def handle(server: Server, client_id: int, text: str):
        await server.stream_start(client_id)
        await server.stream_chunk(
            client_id, StyledText().add("ollama> ", fg=Color.GREEN)
        )
        async for token in ollama.generate_stream(text):
            await server.stream_chunk(client_id, StyledText().add(token))
        await server.stream_end(client_id)

    server.on_message = handle
    await server.start()
    print(f"Listening on {server.host}:{server.port}")

    terminal = Terminal()
    await terminal.connect(server.host, server.port)
    print("Connected. Type a prompt (Ctrl+C to quit):")

    try:
        await terminal.input_loop()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        await terminal.disconnect()
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
