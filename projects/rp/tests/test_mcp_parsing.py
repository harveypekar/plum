from projects.rp.mcp_client import TOOL_CALL_RE, MCPToolRouter


class TestToolCallRegex:
    def test_simple_match(self):
        m = TOOL_CALL_RE.search('[TOOL: search("hello")]')
        assert m
        assert m.group(1) == "search"
        assert m.group(2) == '"hello"'

    def test_single_quotes(self):
        m = TOOL_CALL_RE.search("[TOOL: search('hello')]")
        assert m
        assert m.group(1) == "search"

    def test_no_quotes(self):
        m = TOOL_CALL_RE.search("[TOOL: lookup(42)]")
        assert m
        assert m.group(2) == "42"

    def test_tool_in_text(self):
        text = "Let me check that. [TOOL: search(\"weather\")] Here's what I found."
        m = TOOL_CALL_RE.search(text)
        assert m
        assert m.group(1) == "search"

    def test_multiple_tools(self):
        text = '[TOOL: search("a")] and [TOOL: lookup("b")]'
        matches = list(TOOL_CALL_RE.finditer(text))
        assert len(matches) == 2
        assert matches[0].group(1) == "search"
        assert matches[1].group(1) == "lookup"

    def test_no_match(self):
        assert TOOL_CALL_RE.search("no tools here") is None

    def test_empty_arg(self):
        m = TOOL_CALL_RE.search('[TOOL: search()]')
        assert m
        assert m.group(2) == ""

    def test_space_after_colon(self):
        m = TOOL_CALL_RE.search('[TOOL:  search("x")]')
        assert m


class TestParseToolCalls:
    def setup_method(self):
        self.router = MCPToolRouter()
        self.router._tools["search"] = ("test_server", {
            "name": "search",
            "description": "Search for things",
            "parameters": {"properties": {"query": {"type": "string"}}},
        })

    def test_parses_known_tool(self):
        results = self.router.parse_tool_calls('[TOOL: search("hello world")]')
        assert len(results) == 1
        name, args, full = results[0]
        assert name == "search"
        assert args == {"query": "hello world"}

    def test_parses_unknown_tool_defaults_to_query(self):
        results = self.router.parse_tool_calls('[TOOL: unknown("test")]')
        assert len(results) == 1
        assert results[0][1] == {"query": "test"}

    def test_strips_quotes_from_arg(self):
        results = self.router.parse_tool_calls('[TOOL: search("quoted")]')
        assert results[0][1]["query"] == "quoted"

    def test_returns_full_match_string(self):
        text = '[TOOL: search("x")]'
        results = self.router.parse_tool_calls(text)
        assert results[0][2] == text

    def test_no_tools_returns_empty(self):
        assert self.router.parse_tool_calls("plain text") == []

    def test_uses_first_param_from_schema(self):
        self.router._tools["custom"] = ("srv", {
            "name": "custom",
            "description": "Custom tool",
            "parameters": {"properties": {"url": {"type": "string"}, "depth": {"type": "int"}}},
        })
        results = self.router.parse_tool_calls('[TOOL: custom("example.com")]')
        assert results[0][1] == {"url": "example.com"}


class TestToolDescriptions:
    def test_no_tools_returns_empty(self):
        r = MCPToolRouter()
        assert r.get_tool_descriptions() == ""

    def test_has_tools_returns_formatted(self):
        r = MCPToolRouter()
        r._tools["search"] = ("srv", {"name": "search", "description": "Find stuff", "parameters": {}})
        desc = r.get_tool_descriptions()
        assert "search" in desc
        assert "Find stuff" in desc
        assert "[TOOL:" in desc
