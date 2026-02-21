"""
Wikipedia plain-text chunker.

Splits a Wikipedia extract into (section, paragraph) chunks with stable IDs.
Section headers are detected by the == ... == pattern Wikipedia uses in plain-text extracts.
"""
import hashlib
import re
from dataclasses import dataclass

from app.util.ids import make_chunk_id
from app.util.text import clean_wiki_text

_SECTION_RE = re.compile(r"^(={1,6})\s*(.+?)\s*\1\s*$")
MIN_CHUNK_CHARS = 40
MAX_CHUNK_CHARS = 1500


@dataclass
class Chunk:
    id: str
    page_id: str
    section: str
    paragraph_index: int
    text: str
    hash: str


def chunk_page(page_id: str, title: str, raw_text: str) -> list[Chunk]:
    """
    Split *raw_text* into Chunk objects.

    Strategy:
    1. Split on blank lines.
    2. Detect section header lines (== ... ==).
    3. Non-header, non-trivial paragraphs become chunks.
    """
    chunks: list[Chunk] = []
    current_section = "Introduction"
    para_idx = 0

    # Normalise line endings
    raw_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    # Split into blocks separated by one or more blank lines
    blocks = re.split(r"\n{2,}", raw_text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Check each line in the block for section headers
        lines = block.splitlines()
        section_header = None
        content_lines = []

        for line in lines:
            m = _SECTION_RE.match(line.strip())
            if m:
                section_header = m.group(2).strip()
            else:
                content_lines.append(line)

        if section_header:
            current_section = section_header

        text = clean_wiki_text("\n".join(content_lines).strip())

        if len(text) < MIN_CHUNK_CHARS:
            continue

        # Optionally split very long paragraphs
        sub_chunks = _split_long(text, MAX_CHUNK_CHARS)
        for sub in sub_chunks:
            chunk_id = make_chunk_id(page_id, current_section, para_idx)
            chunks.append(Chunk(
                id=chunk_id,
                page_id=page_id,
                section=current_section,
                paragraph_index=para_idx,
                text=sub,
                hash=hashlib.md5(sub.encode()).hexdigest(),
            ))
            para_idx += 1

    return chunks


def _split_long(text: str, max_chars: int) -> list[str]:
    """Split text that exceeds max_chars at sentence boundaries."""
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    parts: list[str] = []
    current = ""
    for sent in sentences:
        if current and len(current) + len(sent) + 1 > max_chars:
            parts.append(current.strip())
            current = sent
        else:
            current = (current + " " + sent).strip() if current else sent
    if current:
        parts.append(current.strip())
    return parts or [text[:max_chars]]
