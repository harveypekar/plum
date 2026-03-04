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
import re
import sqlite3
import subprocess
import sys
import time
import urllib.request
import uuid
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

    def __init__(self, model: str = "qwen3:8b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    async def generate_stream(self, prompt: str, system: str | None = None,
                              num_predict: int | None = None, think: bool = False):
        """Async generator yielding (token, is_thinking) tuples as they arrive."""
        body: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }
        if system:
            body["system"] = system
        if num_predict is not None:
            body["options"] = {"num_predict": num_predict}
        if think:
            body["think"] = True
        payload = json.dumps(body).encode()
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
                    thinking = data.get("thinking", "")
                    token = data.get("response", "")
                    if thinking:
                        loop.call_soon_threadsafe(queue.put_nowait, (thinking, True))
                    if token:
                        loop.call_soon_threadsafe(queue.put_nowait, (token, False))
                    if data.get("done"):
                        break
            loop.call_soon_threadsafe(queue.put_nowait, None)

        asyncio.get_event_loop().run_in_executor(None, _read_stream)

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    async def generate(self, prompt: str, system: str | None = None, num_predict: int | None = None) -> str:
        """Send prompt, wait for complete response (thinking tokens discarded)."""
        tokens = []
        async for text, is_thinking in self.generate_stream(prompt, system=system, num_predict=num_predict):
            if not is_thinking:
                tokens.append(text)
        return "".join(tokens)

    def count_tokens(self, text: str) -> int:
        """Estimate token count (~4 chars per token)."""
        return len(text) // 4


MODEL_MAP = {
    "q06":    "qwen3:0.6b",
    "q17":    "qwen3:1.7b",
    "q4":     "qwen3:4b",
    "q8":     "qwen3:8b",
    "q25":    "qwen2.5:7b-instruct-q3_K_M",
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus":   "claude-opus-4-6",
}


def _git_commit() -> str:
    """Return the current short git commit hash, or 'unknown'."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


class Log:
    """SQLite log with session tracking."""

    def __init__(self, db_path: str = "sqlite.db"):
        self.conn = sqlite3.connect(db_path)
        self.session_id = uuid.uuid4().hex[:12]
        self.commit = _git_commit()
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"  # auto-incrementing row id
            "  timestamp TEXT DEFAULT (datetime('now')),"  # UTC, set automatically
            "  session TEXT,"  # groups messages from one run of the app
            "  category TEXT,"  # server, client, ollama, db, app, ts_game, ts_game_turn
            "  severity TEXT,"  # 'info', 'warn', 'error'
            "  content TEXT,"  # the log message
            "  [commit] TEXT"  # git short hash the code is running from
            ")"
        )
        self.conn.commit()

    def log(self, content: str, category: str = "app", severity: str = "info"):
        self.conn.execute(
            "INSERT INTO messages (session, category, severity, content, [commit]) VALUES (?, ?, ?, ?, ?)",
            (self.session_id, category, severity, content, self.commit),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()


# -- Demo --


async def main():
    with open("ts_settings.json") as f:
        settings = json.load(f)

    nickname = settings.get("model", "q8")
    model_id = MODEL_MAP.get(nickname, nickname)  # fallback: use raw name

    server = Server(port=4040)
    ollama = OllamaClient(model=model_id)
    log = Log()
    print(f"Model: {nickname} -> {model_id}")

    # Load prompt template and rules docstring once at startup
    with open("prompt.md") as f:
        prompt_template = f.read()
    import ast
    with open("ts_game.py") as f:
        rules_text = ast.get_docstring(ast.parse(f.read())) or ""

    # Start a game
    from ts_game import (TwilightStruggle, COUNTRIES, NEIGHBORS, Side, Phase,
                         ActionType, Action, card_by_id, controls_country,
                         CHINA_CARD_ID, CHINA_CARD_OPS, SPACE_RACE_TRACK,
                         influence_cost, can_place_influence, pass_china_card)
    import ts_ui
    game = TwilightStruggle(seed=42)
    game.reset(seed=42)
    last_move = ""

    def format_game_state() -> str:
        gs = game.state
        side = gs.phasing_player
        side_name = "US" if side == Side.US else "USSR"
        hand = gs.us_hand if side == Side.US else gs.ussr_hand

        # Line 1-2: global state
        l1 = f"T{gs.turn} AR{gs.action_round} DEFCON:{gs.defcon} VP:{gs.vp:+d} MilOps:{gs.mil_ops[Side.US]}/{gs.mil_ops[Side.USSR]}"
        l2 = f"Space:{gs.space_race[Side.US]}/{gs.space_race[Side.USSR]} China:{'US' if gs.china_card_holder==Side.US else 'USSR'}{'*' if gs.china_card_face_up else ''}"

        # Line 3: hand — YOU MUST PICK FROM THESE CARDS
        card_names = [card_by_id(c).name for c in hand]
        l3 = f"YOUR CARDS ({side_name}): {', '.join(card_names)}"

        # Lines 4+: map — only countries with influence, compact
        map_lines = []
        for c in COUNTRIES:
            us_inf = gs.influence[c.id][Side.US]
            ussr_inf = gs.influence[c.id][Side.USSR]
            if us_inf == 0 and ussr_inf == 0:
                continue
            ctrl = ""
            if controls_country(gs, c.id, Side.US):
                ctrl = " [US]"
            elif controls_country(gs, c.id, Side.USSR):
                ctrl = " [USSR]"
            bg = "*" if c.battleground else ""
            map_lines.append(f"  {c.name}{bg}({c.stability}) {us_inf}/{ussr_inf}{ctrl}")

        return "\n".join([l1, l2, l3] + map_lines)

    _country_by_name = {c.name: c for c in COUNTRIES}

    def parse_play(response: str) -> dict | None:
        """Parse first /play command from LLM response. Returns dict or None."""
        m = re.search(r'/play\s+(\w+)(.*?)(?=/play|$)', response, re.DOTALL)
        if not m:
            return None
        cmd = m.group(1)
        rest = m.group(2)
        args = re.findall(r'"([^"]+)"', rest)
        if cmd == "influence" and len(args) >= 2:
            return {"type": "influence", "card": args[0], "countries": args[1:]}
        elif cmd == "coup" and len(args) >= 2:
            return {"type": "coup", "card": args[0], "country": args[1]}
        elif cmd == "space" and len(args) >= 1:
            return {"type": "space", "card": args[0]}
        elif cmd == "scoring":
            return {"type": "scoring"}
        return None

    def find_card_id(name: str, hand: list[int]) -> int | None:
        """Find card ID in hand by name (fuzzy: case-insensitive contains)."""
        if name.lower() == "china card":
            return CHINA_CARD_ID
        name_lower = name.lower()
        for cid in hand:
            if card_by_id(cid).name.lower() == name_lower:
                return cid
        # Fuzzy fallback: partial match
        for cid in hand:
            if name_lower in card_by_id(cid).name.lower():
                return cid
        return None

    def execute_play(play: dict) -> str | None:
        """Execute a /play command against the game engine. Returns error or None."""
        gs = game.state
        side = gs.phasing_player
        hand = gs.us_hand if side == Side.US else gs.ussr_hand

        if play["type"] == "scoring":
            # Find scoring card in hand
            scoring_id = next((c for c in hand if card_by_id(c).scoring), None)
            if scoring_id is None:
                return "No scoring card in hand"
            game.step(Action(ActionType.PLAY_SCORING, card_id=scoring_id))
            return None

        card_name = play.get("card", "")
        cid = find_card_id(card_name, hand)
        is_china = cid == CHINA_CARD_ID
        if cid is None and not is_china:
            return f"Card not found: {card_name}"

        if play["type"] == "influence":
            ops = CHINA_CARD_OPS if is_china else card_by_id(cid).ops
            # Step 1: play card for influence
            game.step(Action(ActionType.PLAY_OPS_INFLUENCE, card_id=cid))
            if gs.game_over:
                return None
            # Step 2: place influence in each listed country
            for country_name in play["countries"]:
                if gs.phase != Phase.OPS_INFLUENCE:
                    break
                c = _country_by_name.get(country_name)
                if c is None:
                    continue  # skip unknown country
                if not can_place_influence(gs, c.id, side):
                    continue  # skip illegal placement
                cost = influence_cost(gs, c.id, side)
                if cost > gs.ops_remaining:
                    continue  # not enough ops
                game.step(Action(ActionType.PLACE_INFLUENCE, country_id=c.id))
                if gs.game_over:
                    return None
            # Done placing — finish if still in influence phase
            if gs.phase == Phase.OPS_INFLUENCE:
                game.step(Action(ActionType.DONE_PLACING))
            return None

        elif play["type"] == "coup":
            country_name = play["country"]
            c = _country_by_name.get(country_name)
            if c is None:
                return f"Country not found: {country_name}"
            game.step(Action(ActionType.PLAY_OPS_COUP, card_id=cid, country_id=c.id))
            return None

        elif play["type"] == "space":
            game.step(Action(ActionType.PLAY_OPS_SPACE, card_id=cid))
            return None

        return f"Unknown play type: {play['type']}"

    async def prompt_llm(server: Server, client_id: int, error_msg: str | None = None):
        """Send one prompt to the LLM with native thinking enabled."""
        gs = game.state
        side_name = "US" if gs.phasing_player == Side.US else "USSR"
        side_color = Color.GREEN if side_name == "US" else Color.RED

        system = rules_text
        game_state_text = format_game_state()
        prompt = (prompt_template
                  .replace("/rules", "")
                  .replace("/gameState", game_state_text)
                  .replace("/side", side_name))
        if error_msg:
            prompt += f"\n\n[FAILED] Your previous move was invalid: {error_msg}. Try again. Pick a card from YOUR CARDS only."

        log.log(f"prompting {side_name}", category="ollama")
        screen = ts_ui.render(game.state, last_move=last_move, model=nickname)
        await server.send(client_id, StyledText().add(screen))
        await server.stream_start(client_id)
        think_clr = ts_ui.THINK_US if side_name == "US" else ts_ui.THINK_USSR
        use_think = settings.get("think", False)
        was_thinking = False
        chunks = []
        think_count = 0
        t_start = time.monotonic()
        t_resp_start = None
        async for text, is_thinking in ollama.generate_stream(prompt, system=system, think=use_think):
            if is_thinking:
                think_count += 1
                if not was_thinking:
                    await server.stream_chunk(client_id, StyledText().add(f"{think_clr}[think] {ts_ui.RESET}"))
                    was_thinking = True
                await server.stream_chunk(client_id, StyledText().add(f"{think_clr}{text}{ts_ui.RESET}"))
            else:
                if was_thinking:
                    await server.stream_chunk(client_id, StyledText().add(f"\n{side_name}> ", fg=side_color))
                    was_thinking = False
                if t_resp_start is None:
                    t_resp_start = time.monotonic()
                chunks.append(text)
                await server.stream_chunk(client_id, StyledText().add(text))
        t_end = time.monotonic()
        await server.stream_end(client_id)

        # Performance metrics
        total_s = t_end - t_start
        resp_count = len(chunks)
        resp_s = t_end - t_resp_start if t_resp_start else 0
        tps = resp_count / resp_s if resp_s > 0.001 else 0
        perf = f"{resp_count} tok \u00b7 {tps:.1f} t/s \u00b7 {total_s:.1f}s"
        if think_count:
            perf += f" ({think_count} think tok)"
        await server.send(client_id, StyledText().add(f"{ts_ui.PERF_CLR}[perf] {perf}{ts_ui.RESET}"))
        log.log(f"perf: {perf}", category="ollama")

        response = "".join(chunks)
        log.log(f"{side_name} response: {response}", category="ollama")
        return response

    async def handle(server: Server, client_id: int, text: str):
        """User types anything to start/continue the game loop."""
        nonlocal last_move
        gs = game.state

        # Auto-handle headline: pick random card for both sides
        if gs.phase == Phase.HEADLINE:
            import random as _rng
            for _ in range(2):  # USSR then US
                actions = game.legal_actions()
                if actions:
                    pick = _rng.choice(actions)
                    side_name = "US" if gs.phasing_player == Side.US else "USSR"
                    card_name = card_by_id(pick.card_id).name if pick.card_id else "?"
                    await server.send(client_id,
                        StyledText().add(f"[headline] {side_name} plays {card_name}", fg=Color.YELLOW))
                    game.step(pick)
                    if gs.game_over:
                        await server.send(client_id,
                            StyledText().add(f"Game over! Winner: {gs.winner.name if gs.winner else 'Draw'}", fg=Color.CYAN))
                        return

        # Game loop: prompt LLM, parse /play, execute, repeat for other side
        MAX_RETRIES = 10
        while not gs.game_over and gs.phase == Phase.ACTION_ROUND:
            side_name = "US" if gs.phasing_player == Side.US else "USSR"
            success = False
            last_error = None
            for attempt in range(1, MAX_RETRIES + 1):
                response = await prompt_llm(server, client_id, error_msg=last_error)
                play = parse_play(response)
                if play is None:
                    last_error = "No /play command found in your response"
                    await server.send(client_id,
                        StyledText().add(f"[retry {attempt}/{MAX_RETRIES}] {last_error}", fg=Color.RED))
                    continue

                err = execute_play(play)
                if err:
                    last_error = err
                    await server.send(client_id,
                        StyledText().add(f"[retry {attempt}/{MAX_RETRIES}] {err}", fg=Color.RED))
                    continue

                last_move = f"{side_name}: {play['type']} \"{play.get('card', '')}\""
                await server.send(client_id,
                    StyledText().add(f"[move] {side_name}: {play}", fg=Color.YELLOW))
                success = True
                break

            if not success:
                await server.send(client_id,
                    StyledText().add(f"[failed] {side_name} failed after {MAX_RETRIES} attempts. Type anything to retry.", fg=Color.RED))
                return

            if gs.game_over:
                await server.send(client_id,
                    StyledText().add(f"Game over! Winner: {gs.winner.name if gs.winner else 'Draw'}", fg=Color.CYAN))
                return

            if gs.phase != Phase.ACTION_ROUND:
                break

        # If game advanced to headline (new turn), let user trigger next round
        if not gs.game_over:
            phase_name = gs.phase.value
            await server.send(client_id,
                StyledText().add(f"[state] Phase: {phase_name}. Type anything to continue.", fg=Color.CYAN))

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
        log.close()


if __name__ == "__main__":
    asyncio.run(main())
