"""
Graph tool implementations for the agentic Q&A loop.

Each tool function queries Neo4j and returns Python objects.
TOOL_SCHEMAS defines the OpenAI function schemas for these tools.
"""
import logging

from neo4j import AsyncDriver

logger = logging.getLogger(__name__)

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "name": "explore_entities",
        "description": (
            "Search for entities by name or keyword AND immediately retrieve all their "
            "facts in a single step. This is your PRIMARY exploration tool — always call "
            "this first with the key subjects in the question. Returns entity info plus "
            "all predicate-object facts with source chunk IDs for citations."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Name or keyword to search for (case-insensitive substring match).",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_neighbors",
        "description": (
            "Get entities directly related to a given entity via graph edges. "
            "Returns neighboring entity IDs, names, types, and relationship labels. "
            "Use this to discover related entities worth exploring further."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "The entity ID to get neighbors for.",
                }
            },
            "required": ["entity_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_entity_facts",
        "description": (
            "Retrieve all facts/claims stored about a specific entity. "
            "Use this on neighbor entity IDs returned by get_neighbors to fetch "
            "their facts after initial exploration."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "The entity ID returned by get_neighbors.",
                }
            },
            "required": ["entity_id"],
            "additionalProperties": False,
        },
    },
]


async def explore_entities(
    driver: AsyncDriver, query: str
) -> tuple[list[dict], list[dict]]:
    """
    Atomic search + fact-fetch: find entities matching *query* and immediately
    retrieve all their facts.

    Returns:
        tool_output  – compact list the LLM sees (entity info + facts)
        raw_facts    – full dicts for synthesize_answer
    """
    entities = await search_entities(driver, query)
    if not entities:
        return [], []

    tool_output: list[dict] = []
    all_raw_facts: list[dict] = []

    for entity in entities:
        entity_tool_out, entity_raw_facts = await get_entity_facts(driver, entity["id"])
        all_raw_facts.extend(entity_raw_facts)

        # If the entity has no extracted claims but does have a description,
        # include the description as a low-confidence synthetic fact so the
        # synthesizer has something to work with.
        if not entity_raw_facts and entity.get("description"):
            all_raw_facts.append(
                {
                    "subject": entity["name"],
                    "predicate": "described as",
                    "object_entity": None,
                    "object_text": entity["description"],
                    "confidence": 0.5,
                    "claim_id": f"desc_{entity['id']}",
                    "citations": [],
                }
            )

        tool_output.append(
            {
                "entity_id": entity["id"],
                "name": entity["name"],
                "type": entity["type"],
                "description": entity["description"],
                "facts": entity_tool_out,
            }
        )

    return tool_output, all_raw_facts


async def search_entities(driver: AsyncDriver, query: str) -> list[dict]:
    """
    Substring search on canonical_name (pre-lowercased, accent-stripped).
    Uses the same pattern as _resolve_entities in retriever.py which is
    known to work correctly with this Neo4j setup.
    """
    from app.util.text import canonical_name as _cname
    cname = _cname(query)
    rows: list[dict] = []
    async with driver.session() as s:
        result = await s.run(
            """
            MATCH (e:Entity)
            WHERE e.canonical_name CONTAINS $cname
            RETURN e.id AS id,
                   e.name AS name,
                   e.type AS type,
                   coalesce(e.description, '') AS description
            LIMIT 10
            """,
            cname=cname,
        )
        async for rec in result:
            rows.append({
                "id": rec["id"],
                "name": rec["name"],
                "type": rec["type"],
                "description": rec["description"][:150] if rec["description"] else "",
            })
    return rows


async def get_entity_facts(
    driver: AsyncDriver, entity_id: str
) -> tuple[list[dict], list[dict]]:
    """
    Fetch all facts about an entity (literal claims + relational claims).

    Returns:
        tool_output  – compact list the LLM sees (predicate, object, confidence, chunk_id)
        raw_facts    – full dicts matching synthesize_answer's expected schema
    """
    tool_output: list[dict] = []
    raw_facts: list[dict] = []

    async with driver.session() as s:
        # ── Literal claims (object_text is set) ───────────────────────────────
        result = await s.run(
            """
            MATCH (e:Entity {id: $eid})-[:HAS_CLAIM]->(cl:Claim)
            WHERE cl.object_text IS NOT NULL AND cl.object_text <> ''
            OPTIONAL MATCH (cl)-[:SUPPORTED_BY]->(ch:SourceChunk)
            OPTIONAL MATCH (ch)<-[:HAS_CHUNK]-(p:SourcePage)
            RETURN e.name         AS subject,
                   cl.id          AS claim_id,
                   cl.predicate   AS predicate,
                   cl.object_text AS object_val,
                   cl.confidence  AS confidence,
                   ch.id          AS chunk_id,
                   left(ch.text, 200) AS snippet,
                   ch.section     AS section,
                   p.title        AS page_title,
                   p.url          AS url
            LIMIT 15
            """,
            eid=entity_id,
        )
        async for rec in result:
            _add_fact(rec, object_entity=None, tool_output=tool_output, raw_facts=raw_facts)

        # ── Relational claims (RELATED edges) ─────────────────────────────────
        result = await s.run(
            """
            MATCH (e:Entity {id: $eid})-[r:RELATED]->(n:Entity)
            MATCH (cl:Claim {id: r.claim_id})
            OPTIONAL MATCH (cl)-[:SUPPORTED_BY]->(ch:SourceChunk)
            OPTIONAL MATCH (ch)<-[:HAS_CHUNK]-(p:SourcePage)
            RETURN e.name          AS subject,
                   cl.id           AS claim_id,
                   r.relation_type AS predicate,
                   n.name          AS object_val,
                   n.name          AS object_entity_name,
                   r.confidence    AS confidence,
                   ch.id           AS chunk_id,
                   left(ch.text, 200) AS snippet,
                   ch.section      AS section,
                   p.title         AS page_title,
                   p.url           AS url
            LIMIT 15
            """,
            eid=entity_id,
        )
        async for rec in result:
            _add_fact(
                rec,
                object_entity=rec["object_entity_name"],
                tool_output=tool_output,
                raw_facts=raw_facts,
            )

    return tool_output, raw_facts


def _add_fact(
    rec: dict,
    object_entity: str | None,
    tool_output: list[dict],
    raw_facts: list[dict],
) -> None:
    citation = None
    if rec["chunk_id"]:
        citation = {
            "chunk_id": rec["chunk_id"],
            "page_title": rec["page_title"] or "",
            "section": rec["section"] or "",
            "snippet": rec["snippet"] or "",
            "url": rec["url"] or "",
        }

    raw_facts.append({
        "subject": rec["subject"],
        "predicate": rec["predicate"],
        "object_entity": object_entity,
        "object_text": rec["object_val"] if object_entity is None else None,
        "confidence": rec["confidence"],
        "claim_id": rec["claim_id"],
        "citations": [citation] if citation else [],
    })

    tool_output.append({
        "predicate": rec["predicate"],
        "object": rec["object_val"] or "",
        "confidence": rec["confidence"],
        "chunk_id": rec["chunk_id"],
    })


async def get_neighbors(driver: AsyncDriver, entity_id: str) -> list[dict]:
    """Return entities directly related to the given entity."""
    async with driver.session() as s:
        result = await s.run(
            """
            MATCH (e:Entity {id: $eid})-[r:RELATED]-(n:Entity)
            RETURN n.id          AS id,
                   n.name        AS name,
                   n.type        AS type,
                   r.relation_type AS relation,
                   CASE WHEN startNode(r).id = $eid
                        THEN 'outgoing' ELSE 'incoming' END AS direction
            LIMIT 20
            """,
            eid=entity_id,
        )
        return await result.data()
