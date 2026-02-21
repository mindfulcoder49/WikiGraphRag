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
    Extract internal Wikipedia links from the article BODY only.

    Strategy:
    1. Fetch raw wikitext via the revisions API.
    2. Truncate at terminal sections (See also, References, etc.) so navbox
       links at the bottom of articles are never seen.
    3. Strip all {{template}} blocks (removes navboxes, infoboxes, sidebars).
    4. Extract [[wikilinks]] from the remaining body text, tracking which
       section each link appears in.
    5. Return subsection links first (more topically specific), then intro
       links, deduped and capped at *limit*.
    """
    import re

    # Sections after which no useful links appear
    _TERMINAL = re.compile(
        r'\n={1,6}\s*(?:See also|Notes|References|Sources|'
        r'Further reading|External links|Bibliography|Footnotes)'
        r'\s*={1,6}',
        re.IGNORECASE,
    )
    # Wikilink: [[Target]] or [[Target|Display]] — skip File/Category/etc.
    _LINK = re.compile(r'\[\[([^|\]#\n][^|\]\n]*?)(?:\|[^\]\n]*)?\]\]')
    # Section headings
    _SECTION = re.compile(r'^(={2,6})\s*(.+?)\s*\1\s*$', re.MULTILINE)

    def _strip_templates(text: str) -> str:
        """Remove all {{ }} template blocks, handling arbitrary nesting."""
        out: list[str] = []
        depth = 0
        i = 0
        while i < len(text):
            if text[i:i+2] == '{{':
                depth += 1
                i += 2
            elif text[i:i+2] == '}}':
                if depth:
                    depth -= 1
                i += 2
            elif depth == 0:
                out.append(text[i])
                i += 1
            else:
                i += 1
        return ''.join(out)

    def _fetch():
        data = _api_get({
            "action": "query",
            "prop": "revisions",
            "titles": title,
            "rvprop": "content",
            "rvslots": "main",
            "rvlimit": 1,
        })
        wikitext = ""
        for page in data.get("query", {}).get("pages", {}).values():
            revs = page.get("revisions", [])
            if revs:
                wikitext = revs[0].get("slots", {}).get("main", {}).get("*", "")
            break

        if not wikitext:
            return []

        # 1. Cut off at terminal sections
        m = _TERMINAL.search(wikitext)
        if m:
            wikitext = wikitext[:m.start()]

        # 2. Strip templates (navboxes, infoboxes, sidebars)
        wikitext = _strip_templates(wikitext)

        # 3. Remove <ref> tags
        wikitext = re.sub(r'<ref[^>]*>.*?</ref>', '', wikitext, flags=re.DOTALL)
        wikitext = re.sub(r'<ref[^/]*/>', '', wikitext)

        # 4. Split into intro + named sections
        sections: list[tuple[str, str]] = []
        last_pos = 0
        last_name = "__intro__"
        for sm in _SECTION.finditer(wikitext):
            sections.append((last_name, wikitext[last_pos:sm.start()]))
            last_name = sm.group(2).strip()
            last_pos = sm.end()
        sections.append((last_name, wikitext[last_pos:]))

        # 5. Extract links, subsection links first
        seen: set[str] = set()
        intro_links: list[str] = []
        body_links: list[str] = []

        for section_name, section_text in sections:
            for lm in _LINK.finditer(section_text):
                target = lm.group(1).strip()
                if ':' in target:          # skip File:, Category:, etc.
                    continue
                key = target.lower()
                if not target or key in seen:
                    continue
                seen.add(key)
                if section_name == "__intro__":
                    intro_links.append(target)
                else:
                    body_links.append(target)

        # Subsection links are more topically specific — surface them first
        return (body_links + intro_links)[:limit]

    return await asyncio.get_event_loop().run_in_executor(None, _fetch)
