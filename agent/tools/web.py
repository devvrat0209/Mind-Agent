import httpx
from .base import tool

@tool(
    name="web_search",
    description="Search the web for information. Returns titles, URLs, snippets. Good for news, facts, docs, research.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "count": {"type": "integer", "description": "Number of results (1-10)", "default": 5}
        },
        "required": ["query"]
    }
)
def web_search(query: str, count: int = 5) -> str:
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=count):
                results.append(f"Title: {r.get('title')}\nURL: {r.get('href')}\nSnippet: {r.get('body')}\n")
        if not results:
            return f"No results for '{query}'"
        return f"Web search results for '{query}':\n\n" + "\n---\n".join(results)
    except ImportError:
        # Fallback: try simple search via httpx if duckduckgo not available
        return f"DuckDuckGo search not installed, but query was: {query}. Please install duckduckgo-search or use fetch_page for known URL."
    except Exception as e:
        return f"Web search error: {e}"

@tool(
    name="fetch_page",
    description="Fetch content of a webpage URL. Returns text content (markdown) of the page.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "max_chars": {"type": "integer", "description": "Max chars to return", "default": 8000}
        },
        "required": ["url"]
    }
)
def fetch_page(url: str, max_chars: int = 8000) -> str:
    try:
        headers = {"User-Agent": "AURA-Agent/0.1 (Research Bot)"}
        with httpx.Client(follow_redirects=True, timeout=15, headers=headers) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content = resp.text
            
            # Try to extract readable text
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text(separator='\n')
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                text = "\n".join(lines)
            except:
                text = content
                
            if len(text) > max_chars:
                text = text[:max_chars] + f"...[truncated {len(text)-max_chars} chars]"
            return f"Content from {url}:\n\n{text}"
    except Exception as e:
        return f"Failed to fetch {url}: {e}"
