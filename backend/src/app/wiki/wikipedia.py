"""
MediaWiki API client.

All network calls go through _session (requests.Session) with proper User-Agent.
Rate limiting is handled by the caller (asyncio.sleep in worker).
"""
import asyncio
import logging
from urllib.parse import quote

import requests

from app.config import settings

logger = logging.getLogger(__name__)

WIKI_API = "https://en.wikipedia.org/w/api.php"

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": settings.wikipedia_user_agent})
    return _session


def _api_get(params: dict) -> dict:
    params["format"] = "json"
    r = _get_session().get(WIKI_API, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


# ──────────────────────────────────────────────────────────────────────────────
# Public async wrappers (run blocking I/O in thread pool)
# ──────────────────────────────────────────────────────────────────────────────

async def search_topic(topic: str) -> tuple[str, str] | None:
    """
    Search Wikipedia for *topic* and return (page_title, page_url).
    Returns None if nothing found.
    """
    def _search():
        data = _api_get({
            "action": "query",
            "list": "search",
            "srsearch": topic,
            "srlimit": 1,
            "srnamespace": 0,
        })
        hits = data.get("query", {}).get("search", [])
        if not hits:
            return None
        title = hits[0]["title"]
        url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
        return title, url

    return await asyncio.get_event_loop().run_in_executor(None, _search)


async def fetch_page_content(title: str) -> str:
    """
    Fetch plain-text extract for *title*.
    Returns the raw plain-text string (may be empty if page not found).
    """
    def _fetch():
        data = _api_get({
            "action": "query",
            "prop": "extracts",
            "titles": title,
            "explaintext": True,
            "exsectionformat": "wiki",  # section headers appear as == ... ==
        })
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            if "extract" in page:
                return page["extract"]
        return ""

    return await asyncio.get_event_loop().run_in_executor(None, _fetch)


async def fetch_page_links(title: str, limit: int = 60) -> list[str]:
    """
    Fetch internal Wikipedia links (main namespace only) from *title*.
    Returns a list of page titles.
    """
    def _fetch():
        titles: list[str] = []
        params = {
            "action": "query",
            "prop": "links",
            "titles": title,
            "pllimit": min(limit, 500),
            "plnamespace": 0,
        }
        while True:
            data = _api_get(params)
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                for link in page.get("links", []):
                    titles.append(link["title"])
            cont = data.get("continue")
            if not cont or len(titles) >= limit:
                break
            params.update(cont)
        return titles[:limit]

    return await asyncio.get_event_loop().run_in_executor(None, _fetch)
