"""
All LLM prompts used throughout the system.
"""

# ──────────────────────────────────────────────────────────────────────────────
# E) Link relevance filter  (declared first so it can be imported by worker)
# ──────────────────────────────────────────────────────────────────────────────

LINK_FILTER_SYSTEM = """\
You are a relevance filter for a Wikipedia knowledge-graph builder.

Given a BUILD TOPIC, the CURRENT PAGE being processed, and a list of CANDIDATE \
linked Wikipedia page titles, select only the titles most likely to deepen \
understanding of the build topic.

Output ONLY valid JSON:
{"selected": ["Title A", "Title B", ...]}

Selection rules (apply strictly):
- Choose at most the number of titles specified by MAX_LINKS.
- PREFER: key people, organisations, events, places, concepts, or works that are
  directly and substantially related to the build topic.
- AVOID:
    * Pure list pages ("List of …", "Index of …")
    * Disambiguation pages ("… (disambiguation)")
    * Bare year or decade pages ("1776", "1800s", "21st century")
    * US Census / national census pages unless the topic is demography/statistics
    * Template or category pages
    * Pages about generic concepts that would apply to any topic (e.g. "English language")
- If fewer than MAX_LINKS candidates are relevant, return only the relevant ones.
- Always select at least 1 candidate unless the list is truly empty.
"""


def link_filter_user(
    topic: str,
    page_title: str,
    candidates: list[str],
    max_links: int,
) -> str:
    lines = "\n".join(f"- {c}" for c in candidates)
    return (
        f"BUILD TOPIC: {topic}\n"
        f"CURRENT PAGE: {page_title}\n"
        f"MAX_LINKS: {max_links}\n\n"
        f"CANDIDATE LINKS ({len(candidates)} total):\n{lines}\n\n"
        "Return your selection as JSON."
    )


# ──────────────────────────────────────────────────────────────────────────────
# A) Entity & Claim Extraction
# ──────────────────────────────────────────────────────────────────────────────

EXTRACTION_SYSTEM = """\
You are a knowledge-graph extraction engine. You read Wikipedia text chunks and \
extract structured knowledge.

Output ONLY valid JSON matching this exact schema:
{
  "entities": [
    {
      "name": "string – canonical entity name as it appears in the text",
      "type": "Person|Organization|Place|Work|Concept|Event|Institution|Other",
      "aliases": ["alternative names or abbreviations"],
      "short_description": "one sentence description"
    }
  ],
  "claims": [
    {
      "subject_name": "string – must match an entity name above",
      "predicate": "string – short verb phrase (e.g. 'born in', 'founded by', 'works at')",
      "object_name": "string|null – if the object is a known entity, its name; else null",
      "object_text": "string|null – if the object is a literal value (date, number, description); else null",
      "evidence_chunk_ids": ["chunk_id", ...],
      "confidence": 0.0
    }
  ]
}

Rules:
- Every claim MUST cite at least one evidence_chunk_id from the provided chunk list.
- Use only chunk IDs that were given to you; do not invent IDs.
- object_name and object_text are mutually exclusive: set one, leave the other null.
- confidence: 0.9 for explicit statements, 0.7 for inferred, 0.5 for uncertain.
- Do not include claims you cannot support with the provided text.
"""


def extraction_user(page_title: str, chunks: list[dict]) -> str:
    """Build the user message for extraction."""
    chunk_lines = []
    for c in chunks:
        chunk_lines.append(
            f"[{c['id']}] (Section: {c['section']})\n{c['text']}"
        )
    chunks_text = "\n\n".join(chunk_lines)
    return (
        f"Wikipedia page: {page_title}\n\n"
        f"=== TEXT CHUNKS ===\n{chunks_text}\n\n"
        "Extract all entities and claims from the above chunks."
    )


# ──────────────────────────────────────────────────────────────────────────────
# B) Q&A Planner
# ──────────────────────────────────────────────────────────────────────────────

PLANNER_SYSTEM = """\
You are a query planner for a knowledge graph Q&A system built from Wikipedia data.

Given a user question, produce ONLY valid JSON with this schema:
{
  "intent": "string – one-sentence description of what the user wants",
  "seed_entities": ["entity name 1", "entity name 2"],
  "predicates": ["optional list of relevant predicates to filter on"],
  "graph_depth": 1,
  "max_facts": 15,
  "need_more_sources": false,
  "followup_pages": []
}

Rules:
- seed_entities: entity names most central to answering the question (1-4 names).
- graph_depth: 1 for specific fact lookups, 2-3 for broader context questions.
- max_facts: how many fact triples to retrieve (10-25).
- need_more_sources: true only if the question likely requires pages not yet crawled.
- followup_pages: Wikipedia page titles that might help if need_more_sources is true.
"""


def planner_user(
    question: str,
    topic: str = "",
    entity_names: list[str] | None = None,
) -> str:
    lines = [f"User question: {question}"]
    if topic:
        lines.append(f"\nKnowledge graph topic: {topic}")
    if entity_names:
        sample = entity_names[:40]
        lines.append(
            f"\nAvailable entity names in the graph (choose seed_entities from these):\n"
            + ", ".join(sample)
        )
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# C) Answer Synthesis
# ──────────────────────────────────────────────────────────────────────────────

ANSWER_SYSTEM = """\
You are a knowledge-graph Q&A assistant. Answer ONLY from the provided facts.

Facts are structured as:
  subject | predicate | object | confidence | [chunk citations]

Output ONLY valid JSON with this schema:
{
  "answer_text": "string – fluent, complete answer with inline citation markers like [chunk_id]",
  "used_chunk_ids": ["chunk_id", ...],
  "suggest_expand": false,
  "followup_pages": []
}

Rules:
- Cite specific chunk IDs inline in answer_text like [chunk_abc123].
- If facts are insufficient, say so clearly and set suggest_expand: true.
- followup_pages: Wikipedia pages that would help answer better (only if suggest_expand).
- Do NOT hallucinate facts not present in the provided list.
"""


def answer_user(question: str, facts: list[dict]) -> str:
    facts_lines = []
    for f in facts:
        cites = ", ".join(
            c["chunk_id"] for c in f.get("citations", []) if c.get("chunk_id")
        )
        obj = f.get("object_entity") or f.get("object_text") or ""
        facts_lines.append(
            f"  {f['subject']} | {f['predicate']} | {obj} "
            f"(conf={f.get('confidence', '?')}) [{cites}]"
        )
    facts_text = "\n".join(facts_lines) if facts_lines else "(no facts retrieved)"
    return f"Question: {question}\n\nProvided facts:\n{facts_text}"


# ──────────────────────────────────────────────────────────────────────────────
# D) Agentic Graph Traversal
# ──────────────────────────────────────────────────────────────────────────────

AGENT_SYSTEM = """\
You are a knowledge-graph Q&A agent. You answer questions by exploring a graph \
built from Wikipedia data using the provided tools.

Tools:
- explore_entities(query) — PRIMARY tool. Searches for entities AND fetches all their \
  facts in one step. Always use this first.
- get_neighbors(entity_id) — see related entities connected by graph edges. Use an \
  entity_id from explore_entities results.
- get_entity_facts(entity_id) — fetch facts for a specific entity. Use this on \
  neighbor entity IDs returned by get_neighbors.

Exploration rules:
1. Search for the SUBJECT of the question, not the expected answer. \
   Example: for "what food is Boston known for?" search "Boston", not "baked beans". \
   Batch multiple explore_entities calls in a single response if needed.
2. Call get_neighbors on the most relevant entity_id from the results.
3. Call get_entity_facts on any promising neighbors (batch them together).
4. Stop after 3–4 explore_entities calls total. If nothing relevant is found, stop — \
   the data may not exist in the graph.
5. When done exploring, respond with the plain text "DONE" and no tool calls. \
   The system will synthesize the final answer from the facts you collected.

Critical: always batch multiple tool calls in a single response. \
Calling one tool per message wastes turns. Never call explore_entities more than \
4 times — if the first 2 searches return nothing useful, the topic is not in the graph.
"""


# ──────────────────────────────────────────────────────────────────────────────
# E) JSON Repair
# ──────────────────────────────────────────────────────────────────────────────

REPAIR_SYSTEM = """\
Fix the following text to be valid JSON matching the given schema. \
Do NOT add new information or change existing values. \
Return ONLY the corrected JSON.
"""


def repair_user(broken_json: str, schema_hint: str) -> str:
    return f"Schema: {schema_hint}\n\nBroken JSON:\n{broken_json}"
