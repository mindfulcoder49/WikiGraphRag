"""
Text utility helpers.
"""
import re
import unicodedata


def canonical_name(name: str) -> str:
    """Normalize entity name for deduplication: lowercase, strip, collapse whitespace."""
    name = name.strip().lower()
    name = re.sub(r"\s+", " ", name)
    # Remove diacritics
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return name


def truncate(text: str, max_chars: int = 300) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


def clean_wiki_text(text: str) -> str:
    """Remove common Wikipedia markup artifacts from plain-text extracts."""
    # Remove citation markers like [1], [citation needed]
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\[citation needed\]", "", text, flags=re.IGNORECASE)
    # Remove excessive whitespace
    text = re.sub(r" {2,}", " ", text)
    return text.strip()
