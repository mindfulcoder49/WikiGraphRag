"""
Agentic Graph RAG Q&A.

The LLM explores the Neo4j graph via tool calls (explore_entities,
get_neighbors, get_entity_facts), accumulating raw facts as it goes.
Once it stops calling tools, synthesize_answer turns the collected
facts into a grounded, cited AnswerResponse.
"""
import json
import logging

from neo4j import AsyncDriver

from app.build.models import AnswerResponse
from app.llm.openai_client import run_agent_loop
from app.llm.prompts import AGENT_SYSTEM
from app.qa.answer import synthesize_answer
from app.qa.graph_tools import (
    TOOL_SCHEMAS,
    explore_entities,
    get_entity_facts,
    get_neighbors,
)

logger = logging.getLogger(__name__)


async def answer_question(
    driver: AsyncDriver,
    build_id: str,
    question: str,
    history: list[dict] | None = None,
) -> AnswerResponse:
    """
    Entry point for agentic Graph RAG Q&A.

    1. Run an agent loop: LLM calls graph tools to explore and collect facts.
    2. Pass the collected facts to synthesize_answer for a grounded response.

    *history* is a list of prior {"role": "user"|"assistant", "content": str}
    dicts that are prepended as context so the agent can resolve references
    like "it" or "they" from earlier in the conversation.
    """
    collected_facts: list[dict] = []

    async def execute_tool(name: str, args: dict) -> str:
        logger.info("Agent tool: %s(%s)", name, args)

        if name == "explore_entities":
            tool_out, raw_facts = await explore_entities(driver, args.get("query", ""))
            collected_facts.extend(raw_facts)
            logger.info(
                "explore_entities('%s') → %d entities, %d facts (total collected: %d)",
                args.get("query", ""),
                len(tool_out),
                len(raw_facts),
                len(collected_facts),
            )
            return json.dumps(tool_out)

        if name == "get_entity_facts":
            tool_out, raw_facts = await get_entity_facts(
                driver, args.get("entity_id", "")
            )
            collected_facts.extend(raw_facts)
            logger.info(
                "get_entity_facts → %d facts (total collected: %d)",
                len(raw_facts),
                len(collected_facts),
            )
            return json.dumps(tool_out)

        if name == "get_neighbors":
            results = await get_neighbors(driver, args.get("entity_id", ""))
            logger.info("get_neighbors → %d neighbors", len(results))
            return json.dumps(results)

        return json.dumps({"error": f"Unknown tool: {name}"})

    # Build the initial agent message, prepending conversation history so the
    # agent can resolve references (e.g. "it", "they") from prior turns.
    if history:
        history_lines = "\n".join(
            f"{m['role'].capitalize()}: {m['content']}" for m in history
        )
        initial_message = (
            f"Prior conversation:\n{history_lines}\n\n"
            f"Current question: {question}"
        )
    else:
        initial_message = question

    await run_agent_loop(
        system_prompt=AGENT_SYSTEM,
        initial_message=initial_message,
        tools=TOOL_SCHEMAS,
        tool_executor=execute_tool,
        max_turns=12,
    )

    logger.info("Agent finished. Total facts collected: %d", len(collected_facts))
    return await synthesize_answer(question, collected_facts, history=history)
