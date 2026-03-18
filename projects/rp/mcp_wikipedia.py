"""MCP server that exposes Wikipedia search and article retrieval."""
import wikipediaapi
from mcp.server.fastmcp import FastMCP

MAX_BYTES = 1_000_000  # 1MB safeguard

mcp = FastMCP("wikipedia")
wiki = wikipediaapi.Wikipedia(
    user_agent="plum-rp/0.1 (https://github.com/harveypekar/plum)",
    language="en",
)


@mcp.tool()
def wiki_summary(title: str) -> str:
    """Get the summary (first section) of a Wikipedia article by exact title."""
    page = wiki.page(title)
    if not page.exists():
        return f"No Wikipedia article found for '{title}'."
    text = page.summary[:MAX_BYTES]
    return text


@mcp.tool()
def wiki_section(title: str, section: str) -> str:
    """Get a specific section of a Wikipedia article. Use wiki_summary first to see available sections."""
    page = wiki.page(title)
    if not page.exists():
        return f"No Wikipedia article found for '{title}'."
    sec = _find_section(page.sections, section)
    if not sec:
        available = [s.title for s in page.sections]
        return f"Section '{section}' not found. Available: {', '.join(available)}"
    text = sec.text[:MAX_BYTES]
    return text


@mcp.tool()
def wiki_search(query: str) -> str:
    """Search Wikipedia and return the summary of the best matching article."""
    import requests
    resp = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "opensearch",
            "search": query,
            "limit": 5,
            "format": "json",
        },
        headers={"User-Agent": "plum-rp/0.1"},
        timeout=10,
    )
    data = resp.json()
    titles = data[1] if len(data) > 1 else []
    if not titles:
        return f"No Wikipedia results for '{query}'."
    # Return summary of first match
    page = wiki.page(titles[0])
    if not page.exists():
        return f"Found title '{titles[0]}' but page doesn't exist."
    result = f"## {page.title}\n\n{page.summary[:MAX_BYTES]}"
    if len(titles) > 1:
        result += f"\n\nOther matches: {', '.join(titles[1:])}"
    return result


def _find_section(sections, target: str):
    """Recursively search sections by title (case-insensitive)."""
    for s in sections:
        if s.title.lower() == target.lower():
            return s
        found = _find_section(s.sections, target)
        if found:
            return found
    return None


if __name__ == "__main__":
    mcp.run(transport="stdio")
