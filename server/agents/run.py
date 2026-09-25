import json
import uuid

from google.adk.agents.llm_agent import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types


async def run_agent_for_final_answer(agent: Agent, question: str, session_id: str | None = None, usage: dict | None = None) -> dict:
    """Runs the agent to completion and returns its structured output_schema
    response as a dict. Raises ValueError if the model never produced a
    final structured response. If `usage` is given, Gemini token counts for
    every model call are added into it (the eval uses this for cost)."""
    session_id = session_id or str(uuid.uuid4())
    user_id = "groundtruth-user"
    runner = InMemoryRunner(agent=agent, app_name="groundtruth")
    await runner.session_service.create_session(app_name="groundtruth", user_id=user_id, session_id=session_id)

    message = types.Content(role="user", parts=[types.Part(text=question)])
    final_text = None
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
        if usage is not None and event.usage_metadata:
            add_usage(usage, event.usage_metadata)
        if event.is_final_response() and event.content and event.content.parts:
            text = event.content.parts[0].text
            if text:
                final_text = text

    if final_text is None:
        raise ValueError("agent produced no final response")
    return json.loads(final_text)


def add_usage(usage: dict, meta) -> None:
    usage["model_calls"] = usage.get("model_calls", 0) + 1
    for field in ("prompt_token_count", "candidates_token_count", "thoughts_token_count"):
        usage[field] = usage.get(field, 0) + (getattr(meta, field, None) or 0)
