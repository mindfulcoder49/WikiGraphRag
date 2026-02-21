"""
JSON parsing with one LLM repair attempt on failure.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences like ```json ... ```."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_json(text: str) -> dict | list:
    """Parse JSON, stripping markdown fences first."""
    clean = _strip_fences(text)
    return json.loads(clean)


async def parse_json_with_repair(
    text: str,
    schema_hint: str = "",
) -> dict | list | None:
    """
    Try to parse JSON from *text*.
    On failure, call LLM once to repair it, then try again.
    Returns None if both attempts fail.
    """
    # First attempt
    try:
        return parse_json(text)
    except json.JSONDecodeError:
        logger.warning("JSON parse failed; attempting LLM repair.")

    # Repair attempt
    try:
        from app.llm.openai_client import llm_call
        from app.llm.prompts import REPAIR_SYSTEM, repair_user

        repaired = await llm_call(
            system_prompt=REPAIR_SYSTEM,
            user_content=repair_user(text, schema_hint),
            json_mode=True,
            max_tokens=16000,
        )
        return parse_json(repaired)
    except Exception as exc:
        logger.error("JSON repair failed: %s", exc)
        return None
