"""
OpenAI Responses API client.

All LLM calls are server-side only. The API key is NEVER sent to the browser.
Calls are run in a thread-pool executor so they don't block the asyncio event loop.
A semaphore caps concurrent LLM calls.
"""
import asyncio
import logging

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None
_semaphore: asyncio.Semaphore | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.llm_max_concurrent)
    return _semaphore


async def llm_call(
    system_prompt: str,
    user_content: str,
    json_mode: bool = False,
    max_tokens: int | None = None,
) -> str:
    """
    Call the OpenAI Responses API.

    Args:
        system_prompt: Developer/system instructions (passed as `instructions`).
        user_content:  User message (passed as `input`).
        json_mode:     If True, appends JSON-only instruction to system_prompt.
        max_tokens:    Override default max output tokens.

    Returns:
        The model's text output.
    """
    if max_tokens is None:
        max_tokens = settings.llm_max_tokens

    instructions = system_prompt
    if json_mode:
        instructions += (
            "\n\nCRITICAL: Respond with ONLY valid JSON. "
            "No markdown code fences, no commentary, no trailing text."
        )

    # The Responses API requires the word "json" to appear somewhere in the
    # input (user) message when text.format.type=json_object is requested.
    # Appending a short suffix satisfies this requirement without changing the
    # semantics of the prompt.
    input_text = user_content
    if json_mode and "json" not in user_content.lower():
        input_text = user_content + "\n\nReturn your answer as JSON."

    sem = _get_semaphore()
    client = _get_client()

    async with sem:
        loop = asyncio.get_event_loop()

        def _call():
            kwargs: dict = {
                "model": settings.openai_model,
                "instructions": instructions,
                "input": input_text,
                "max_output_tokens": max_tokens,
            }
            # Request structured JSON output when supported
            if json_mode:
                kwargs["text"] = {"format": {"type": "json_object"}}

            try:
                response = client.responses.create(**kwargs)
            except Exception as exc:
                # If json_object format not supported (e.g. model doesn't support it),
                # fall back without the format hint and rely on prompt engineering.
                if json_mode and "text" in kwargs:
                    logger.warning("json_object format unsupported, falling back: %s", exc)
                    kwargs.pop("text")
                    response = client.responses.create(**kwargs)
                else:
                    raise

            return response.output_text

        return await loop.run_in_executor(None, _call)


async def run_agent_loop(
    system_prompt: str,
    initial_message: str,
    tools: list[dict],
    tool_executor,  # async (name: str, args: dict) -> str
    max_turns: int = 8,
) -> str:
    """
    Multi-turn tool-calling agent loop using the Responses API.

    Uses previous_response_id to chain turns — the API carries the full
    conversation history, so we only send the new tool results each turn.
    Returns the model's final text output once it stops calling tools.
    """
    import json as _json

    sem = _get_semaphore()
    client = _get_client()
    prev_response_id: str | None = None

    # Turn 0: initial user message
    current_input: str | list = initial_message

    for _turn in range(max_turns):
        async with sem:
            loop = asyncio.get_event_loop()
            _inp = current_input
            _prev = prev_response_id

            def _call(_i=_inp, _p=_prev):
                kwargs: dict = {
                    "model": settings.openai_model,
                    "instructions": system_prompt,
                    "input": _i,
                    "tools": tools,
                }
                if _p:
                    kwargs["previous_response_id"] = _p
                return client.responses.create(**kwargs)

            response = await loop.run_in_executor(None, _call)

        prev_response_id = response.id

        fn_calls = [
            o for o in response.output
            if getattr(o, "type", None) == "function_call"
        ]

        if not fn_calls:
            return response.output_text or ""

        # Execute each tool call; next input is just the tool results
        tool_results: list[dict] = []
        for fc in fn_calls:
            try:
                result = await tool_executor(fc.name, _json.loads(fc.arguments))
                result_str = result if isinstance(result, str) else _json.dumps(result, default=str)
            except Exception as exc:
                logger.error("Tool %s(%s) raised: %s", fc.name, fc.arguments, exc, exc_info=True)
                result_str = _json.dumps({"error": str(exc)})
            tool_results.append({
                "type": "function_call_output",
                "call_id": fc.call_id,
                "output": result_str,
            })

        current_input = tool_results

    # Max turns reached — one final call without tools to get closing text
    logger.info("Agent loop: max_turns=%d reached, requesting final response.", max_turns)
    async with sem:
        loop = asyncio.get_event_loop()
        _inp = current_input
        _prev = prev_response_id

        def _final(_i=_inp, _p=_prev):
            kwargs: dict = {
                "model": settings.openai_model,
                "instructions": system_prompt,
                "input": _i,
            }
            if _p:
                kwargs["previous_response_id"] = _p
            return client.responses.create(**kwargs)

        response = await loop.run_in_executor(None, _final)

    logger.info("Agent loop: final response received.")
    return response.output_text or ""
