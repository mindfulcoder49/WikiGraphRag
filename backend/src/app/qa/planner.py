"""
Q&A planner: converts a natural-language question into a structured retrieval plan.
"""
import logging

from app.llm.json_utils import parse_json_with_repair
from app.llm.openai_client import llm_call
from app.llm.prompts import PLANNER_SYSTEM, planner_user

logger = logging.getLogger(__name__)

_SCHEMA_HINT = (
    '{"intent":"","seed_entities":[],"predicates":[],'
    '"graph_depth":1,"max_facts":15,"need_more_sources":false,"followup_pages":[]}'
)


async def plan_query(
    question: str,
    topic: str = "",
    entity_names: list[str] | None = None,
) -> dict:
    """
    Returns a plan dict with keys:
    - intent, seed_entities, predicates, graph_depth, max_facts,
      need_more_sources, followup_pages
    """
    raw = await llm_call(
        system_prompt=PLANNER_SYSTEM,
        user_content=planner_user(question, topic=topic, entity_names=entity_names),
        json_mode=True,
        max_tokens=512,
    )
    plan = await parse_json_with_repair(raw, _SCHEMA_HINT)
    if not plan:
        logger.warning("Planner returned invalid JSON; using defaults.")
        plan = {
            "intent": question,
            "seed_entities": [],
            "predicates": [],
            "graph_depth": 2,
            "max_facts": 15,
            "need_more_sources": False,
            "followup_pages": [],
        }
    return plan  # type: ignore[return-value]
