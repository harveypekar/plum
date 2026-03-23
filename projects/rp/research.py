"""Two-model research dispatch: use a tool-capable model to look up facts for RP."""
import logging
from .mcp_client import get_router

_log = logging.getLogger(__name__)

RESEARCH_MODEL = "qwen3:8b"

DISPATCH_SYSTEM = (
    "You are a research assistant for a roleplay chat. "
    "The user will show you the latest message from a conversation. "
    "If it references real-world topics, people, places, history, or factual claims "
    "that would benefit from a quick Wikipedia lookup, use your tools. "
    "If the message is purely fictional/emotional with no factual content, reply NONE. "
    "Do NOT look up fictional characters or roleplay scenarios."
)


def get_tools_schema() -> list[dict]:
    """Convert MCP tool schemas to Ollama native tool format."""
    router = get_router()
    if not router.has_tools:
        return []
    tools = []
    for name, (_, schema) in router._tools.items():
        tools.append({
            "type": "function",
            "function": {
                "name": schema["name"],
                "description": schema["description"],
                "parameters": schema.get("parameters", {}),
            },
        })
    return tools


async def research_dispatch(ollama, user_message: str) -> str | None:
    """Check if user message needs factual research; if so, call tools and return results.

    Returns a research context string to inject into the RP prompt, or None.
    """
    router = get_router()
    if not router.has_tools:
        return None

    tools = get_tools_schema()
    if not tools:
        return None

    messages = [
        {"role": "system", "content": DISPATCH_SYSTEM},
        {"role": "user", "content": user_message},
    ]

    # Phase 1: ask the tool model if research is needed
    try:
        response = await ollama.chat(
            model=RESEARCH_MODEL,
            messages=messages,
            tools=tools,
            think=False,
        )
    except Exception as e:
        _log.warning("Research dispatch failed: %s", e)
        return None

    msg = response.get("message", {})
    tool_calls = msg.get("tool_calls")

    # No tool calls = no research needed
    if not tool_calls:
        content = msg.get("content", "").strip()
        if content.upper() == "NONE" or not content:
            return None
        # Model replied with text instead of tool call — ignore
        return None

    # Phase 2: execute tool calls via MCP
    results = []
    for tc in tool_calls:
        func = tc.get("function", {})
        name = func.get("name", "")
        args = func.get("arguments", {})
        _log.info("Research tool call: %s(%s)", name, args)

        result = await router.call_tool(name, args)
        results.append(f"[{name}]: {result}")

        # Add tool call and result to messages for potential follow-up
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [tc],
        })
        messages.append({
            "role": "tool",
            "content": result,
        })

    if not results:
        return None

    # Phase 3: ask tool model to summarize the research concisely
    messages.append({
        "role": "user",
        "content": "Summarize the key facts in 2-3 bullet points. Be concise and factual.",
    })
    try:
        summary_resp = await ollama.chat(
            model=RESEARCH_MODEL,
            messages=messages,
            think=False,
        )
        summary = summary_resp.get("message", {}).get("content", "").strip()
    except Exception:
        # Fall back to raw results
        summary = "\n".join(results)

    _log.info("Research results: %s", summary[:200])
    return summary
