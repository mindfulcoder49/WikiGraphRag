"""
Graph retriever: resolve entity names → fetch neighborhood → collect facts + citations.
"""
import logging

from neo4j import AsyncDriver

from app.util.text import canonical_name

logger = logging.getLogger(__name__)


async def retrieve_facts(
    driver: AsyncDriver, build_id: str, plan: dict, raw_question: str = ""
) -> list[dict]:
    """
    Returns a list of fact dicts:
    {
      subject, predicate, object_entity|object_text, confidence,
      claim_id, citations: [{chunk_id, page_title, section, snippet, url}]
    }
    """
    seed_names: list[str] = plan.get("seed_entities", [])
    max_facts: int = plan.get("max_facts", 15)
    depth: int = plan.get("graph_depth", 1)
    predicates: list[str] = plan.get("predicates", [])

    # 1. Resolve seed entity names to IDs
    seed_ids = await _resolve_entities(driver, build_id, seed_names) if seed_names else []
    logger.info("Q&A seed_names=%s → seed_ids=%s", seed_names, seed_ids)

    # Fallback: keyword search when planner produced no names or names didn't resolve
    if not seed_ids:
        logger.warning("Seed entity resolution failed; trying keyword search on question.")
        fallback_q = plan.get("intent", "") or raw_question or " ".join(seed_names)
        seed_ids = await _keyword_entity_search(driver, build_id, fallback_q)
        logger.info("Q&A keyword fallback → seed_ids=%s", seed_ids)

    if not seed_ids:
        logger.warning("No entities found for seeds: %s — cannot retrieve facts.", seed_names)
        return []

    # 2. Fetch RELATED edges in neighborhood
    facts = await _fetch_relational_facts(driver, seed_ids, depth, max_facts, predicates)
    logger.info("Q&A relational facts: %d", len(facts))

    # 3. Also fetch literal claims (object_text) from seed entities
    literal_facts = await _fetch_literal_claims(driver, seed_ids, max_facts - len(facts))
    logger.info("Q&A literal facts: %d", len(literal_facts))
    facts.extend(literal_facts)

    logger.info("Q&A total facts returned: %d", len(facts[:max_facts]))
    return facts[:max_facts]


async def _resolve_entities(driver: AsyncDriver, build_id: str, names: list[str]) -> list[str]:
    """Find Entity IDs that match any of the seed names (canonical match)."""
    ids: list[str] = []
    async with driver.session() as s:
        for name in names:
            cname = canonical_name(name)
            # Try exact canonical match first
            result = await s.run(
                """
                MATCH (e:Entity)
                WHERE e.canonical_name = $cname
                RETURN e.id AS id LIMIT 1
                """,
                cname=cname,
            )
            rec = await result.single()
            if rec:
                ids.append(rec["id"])
                continue

            # Fallback: substring match on canonical_name
            result = await s.run(
                """
                MATCH (e:Entity)
                WHERE e.canonical_name CONTAINS $cname
                RETURN e.id AS id LIMIT 3
                """,
                cname=cname,
            )
            recs = await result.data()
            ids.extend(r["id"] for r in recs)

    return list(dict.fromkeys(ids))  # deduplicate, preserve order


async def _keyword_entity_search(
    driver: AsyncDriver, build_id: str, question: str, limit: int = 5
) -> list[str]:
    """
    Last-resort fallback: find entities in this build whose name contains
    any significant word from the question. Returns entity IDs.
    """
    # Split question into words, drop short stop-words
    stop = {"a", "an", "the", "is", "are", "was", "were", "of", "in", "on",
            "at", "to", "for", "and", "or", "what", "who", "when", "where",
            "how", "why", "does", "did", "do", "has", "have", "had", "with",
            "from", "by", "about", "s"}
    words = [w for w in question.lower().split() if len(w) > 2 and w not in stop]
    if not words:
        return []

    ids: list[str] = []
    async with driver.session() as s:
        for word in words[:5]:  # cap to avoid too many queries
            result = await s.run(
                """
                MATCH (b:Build {id: $build_id})-[:HAS_PAGE]->(p:SourcePage)
                OPTIONAL MATCH (p)-[:HAS_CHUNK]->(ch:SourceChunk)<-[:MENTIONED_IN]-(e:Entity)
                WITH DISTINCT e
                WHERE e IS NOT NULL AND toLower(e.name) CONTAINS $word
                RETURN e.id AS id LIMIT $limit
                """,
                build_id=build_id,
                word=word,
                limit=limit,
            )
            recs = await result.data()
            ids.extend(r["id"] for r in recs)

    return list(dict.fromkeys(ids))[:limit]


async def _fetch_relational_facts(
    driver: AsyncDriver,
    seed_ids: list[str],
    depth: int,
    max_facts: int,
    predicates: list[str],
) -> list[dict]:
    facts: list[dict] = []
    async with driver.session() as s:
        # Up to `depth` hops through RELATED edges
        # Predicate filter is applied AFTER UNWIND (r is bound after unwind)
        predicate_filter = ""
        params: dict = {"seed_ids": seed_ids, "limit": max_facts}
        if predicates:
            predicate_filter = "WHERE r.relation_type IN $predicates"
            params["predicates"] = predicates

        query = f"""
        MATCH path = (seed:Entity)-[:RELATED*1..{depth}]->(neighbor:Entity)
        WHERE seed.id IN $seed_ids
        WITH relationships(path) AS rels
        UNWIND rels AS r
        WITH r, startNode(r) AS src, endNode(r) AS dst
        {predicate_filter}
        MATCH (cl:Claim {{id: r.claim_id}})
        OPTIONAL MATCH (cl)-[:SUPPORTED_BY]->(ch:SourceChunk)
        OPTIONAL MATCH (ch)<-[:HAS_CHUNK]-(p:SourcePage)
        RETURN src.name AS subject,
               r.relation_type AS predicate,
               dst.name AS object_entity,
               NULL AS object_text,
               r.confidence AS confidence,
               r.claim_id AS claim_id,
               collect(DISTINCT {{
                 chunk_id: ch.id,
                 section: ch.section,
                 snippet: left(ch.text, 250),
                 page_title: p.title,
                 url: p.url
               }}) AS citations
        LIMIT $limit
        """
        result = await s.run(query, **params)
        async for rec in result:
            facts.append({
                "subject": rec["subject"],
                "predicate": rec["predicate"],
                "object_entity": rec["object_entity"],
                "object_text": rec["object_text"],
                "confidence": rec["confidence"],
                "claim_id": rec["claim_id"],
                "citations": [c for c in rec["citations"] if c.get("chunk_id")],
            })
    return facts


async def _fetch_literal_claims(
    driver: AsyncDriver, seed_ids: list[str], limit: int
) -> list[dict]:
    """Fetch HAS_CLAIM relationships where object_text is set (non-relational claims)."""
    if limit <= 0:
        return []
    facts: list[dict] = []
    async with driver.session() as s:
        result = await s.run(
            """
            MATCH (e:Entity)-[:HAS_CLAIM]->(cl:Claim)
            WHERE e.id IN $seed_ids AND cl.object_text IS NOT NULL AND cl.object_text <> ''
            OPTIONAL MATCH (cl)-[:SUPPORTED_BY]->(ch:SourceChunk)
            OPTIONAL MATCH (ch)<-[:HAS_CHUNK]-(p:SourcePage)
            RETURN e.name AS subject,
                   cl.predicate AS predicate,
                   cl.object_text AS object_text,
                   NULL AS object_entity,
                   cl.confidence AS confidence,
                   cl.id AS claim_id,
                   collect(DISTINCT {
                     chunk_id: ch.id,
                     section: ch.section,
                     snippet: left(ch.text, 250),
                     page_title: p.title,
                     url: p.url
                   }) AS citations
            LIMIT $limit
            """,
            seed_ids=seed_ids,
            limit=limit,
        )
        async for rec in result:
            facts.append({
                "subject": rec["subject"],
                "predicate": rec["predicate"],
                "object_entity": rec["object_entity"],
                "object_text": rec["object_text"],
                "confidence": rec["confidence"],
                "claim_id": rec["claim_id"],
                "citations": [c for c in rec["citations"] if c.get("chunk_id")],
            })
    return facts
