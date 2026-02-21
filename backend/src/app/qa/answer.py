"""
Answer synthesis: takes retrieved facts and produces a grounded answer with citations.
"""
import logging

from app.build.models import AnswerResponse, Citation
from app.llm.json_utils import parse_json_with_repair
from app.llm.openai_client import llm_call
from app.llm.prompts import ANSWER_SYSTEM, answer_user

logger = logging.getLogger(__name__)

_SCHEMA_HINT = '{"answer_text":"","used_chunk_ids":[],"suggest_expand":false,"followup_pages":[]}'


async def synthesize_answer(
    question: str,
    facts: list[dict],
    history: list[dict] | None = None,
) -> AnswerResponse:
    """
    Call the LLM to synthesize a grounded answer from *facts*.
    Returns an AnswerResponse with citations mapped from the used chunk IDs.
    """
    user_msg = answer_user(question, facts, history=history)
    logger.info("Answer LLM user message (first 500 chars): %s", user_msg[:500])
    raw = await llm_call(
        system_prompt=ANSWER_SYSTEM,
        user_content=user_msg,
        json_mode=True,
        max_tokens=16384,
    )
    logger.info("Answer LLM raw response (first 300 chars): %s", raw[:300])
    parsed = await parse_json_with_repair(raw, _SCHEMA_HINT)

    if not parsed:
        return AnswerResponse(
            answer_text="I could not generate an answer. Please try rephrasing your question.",
            citations=[],
            used_entities=[],
            used_claim_ids=[],
            suggest_expand=True,
            followup_pages=[],
        )

    answer_text: str = parsed.get("answer_text", "")
    used_chunk_ids: list[str] = parsed.get("used_chunk_ids", [])
    suggest_expand: bool = bool(parsed.get("suggest_expand", False))
    followup_pages: list[str] = parsed.get("followup_pages", [])

    # Build citation index from facts
    chunk_to_citation: dict[str, Citation] = {}
    for fact in facts:
        for c in fact.get("citations", []):
            cid = c.get("chunk_id")
            if cid and cid not in chunk_to_citation:
                chunk_to_citation[cid] = Citation(
                    chunk_id=cid,
                    page_title=c.get("page_title") or "",
                    section=c.get("section") or "",
                    snippet=c.get("snippet") or "",
                    url=c.get("url") or "",
                )

    citations = [chunk_to_citation[cid] for cid in used_chunk_ids if cid in chunk_to_citation]

    # Collect used entities + claim IDs from facts whose chunks were cited
    used_chunk_set = set(used_chunk_ids)
    used_entities: list[str] = []
    used_claim_ids: list[str] = []
    for fact in facts:
        fact_chunks = {c.get("chunk_id") for c in fact.get("citations", [])}
        if fact_chunks & used_chunk_set:
            subj = fact.get("subject", "")
            if subj and subj not in used_entities:
                used_entities.append(subj)
            cid = fact.get("claim_id", "")
            if cid and cid not in used_claim_ids:
                used_claim_ids.append(cid)

    return AnswerResponse(
        answer_text=answer_text,
        citations=citations,
        used_entities=used_entities,
        used_claim_ids=used_claim_ids,
        suggest_expand=suggest_expand,
        followup_pages=followup_pages,
    )
