"""
Stable, deterministic ID generation.
"""
import hashlib
import uuid


def make_build_id() -> str:
    return str(uuid.uuid4())


def make_claim_id() -> str:
    return str(uuid.uuid4())


def make_page_id(url: str) -> str:
    return "page_" + hashlib.sha1(url.encode()).hexdigest()[:16]


def make_chunk_id(page_id: str, section: str, paragraph_index: int) -> str:
    key = f"{page_id}::{section}::{paragraph_index}"
    return "chunk_" + hashlib.sha1(key.encode()).hexdigest()[:16]


def make_entity_id(canonical_name: str) -> str:
    return "ent_" + hashlib.sha1(canonical_name.encode()).hexdigest()[:16]
