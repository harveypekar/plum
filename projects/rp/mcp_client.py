"""MCP client for calling tool servers from the RP pipeline."""
import asyncio
import json
import logging
import re
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_log = logging.getLogger(__name__)

# Tool call pattern the model uses: [TOOL: tool_name("arg")]
TOOL_CALL_RE = re.compile(r'\[TOOL:\s*(\w+)\(([^)]*)\)\]')

MAX_CONTENT_BYTES = 1_000_000  # 1MB safeguard per generation cycle


class MCPToolRouter:
    """Manages MCP server connections and routes tool calls."""

    def __init__(self):
        self._servers: dict[str, StdioServerParameters] = {}
        self._tools: dict[str, tuple[str, dict]] = {}  # tool_name -> (server_key, schema)
        self._ready = False

    def register_server(self, key: str, command: str, args: list[str] | None = None):
        self._servers[key] = StdioServerParameters(
            command=command, args=args or [],
        )

    async def discover_tools(self):
        """Connect to each server, list tools, build routing table."""
        for key, params in self._servers.items():
            try:
                result = await asyncio.wait_for(self._discover_from(key, params), timeout=15)
            except asyncio.TimeoutError:
                _log.warning("Timeout discovering tools from %s", key)
            except Exception as e:
                _log.warning("Failed to discover tools from %s: %s", key, e)
        self._ready = True

    async def _discover_from(self, key, params):
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                for tool in result.tools:
                    self._tools[tool.name] = (key, {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    })
                    _log.info("Registered tool: %s (from %s)", tool.name, key)

    def get_tool_descriptions(self) -> str:
        """Format tool descriptions for injection into the system prompt."""
        if not self._tools:
            return ""
        lines = ["You have access to these tools. To use one, write: [TOOL: tool_name(\"argument\")]",
                 "The result will be provided to you. Only use tools when you need factual information.",
                 "Available tools:"]
        for name, (_, schema) in self._tools.items():
            lines.append(f"- {name}: {schema['description']}")
        return "\n".join(lines)

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Call a tool on its MCP server and return the result."""
        if tool_name not in self._tools:
            return f"Unknown tool: {tool_name}"
        server_key, _ = self._tools[tool_name]
        params = self._servers[server_key]
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    text = "\n".join(c.text for c in result.content if hasattr(c, "text"))
                    return text[:MAX_CONTENT_BYTES]
        except Exception as e:
            _log.error("Tool call %s failed: %s", tool_name, e)
            return f"Tool error: {e}"

    def parse_tool_calls(self, text: str) -> list[tuple[str, dict, str]]:
        """Find [TOOL: name("arg")] patterns in text. Returns [(name, args, full_match)]."""
        results = []
        for m in TOOL_CALL_RE.finditer(text):
            name = m.group(1)
            raw_arg = m.group(2).strip().strip('"').strip("'")
            # Figure out the argument name from the tool schema
            if name in self._tools:
                _, schema = self._tools[name]
                props = schema.get("parameters", {}).get("properties", {})
                if props:
                    first_param = next(iter(props))
                    args = {first_param: raw_arg}
                else:
                    args = {"query": raw_arg}
            else:
                args = {"query": raw_arg}
            results.append((name, args, m.group(0)))
        return results

    @property
    def has_tools(self):
        return bool(self._tools)


# Singleton
_router = MCPToolRouter()


def get_router() -> MCPToolRouter:
    return _router
