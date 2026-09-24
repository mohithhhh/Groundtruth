import json
import uuid

from google.adk.agents.llm_agent import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types


async def run_agent_for_final_answer(agent: Agent, question: str, session_id: str | None = None) -> dict:
    """Runs the agent to completion and returns its structured output_schema
    response as a dict. Raises ValueError if the model never produced a
    final structured response."""
    session_id = session_id or str(uuid.uuid4())
    user_id = "penumbra-user"
    runner = InMemoryRunner(agent=agent, app_name="penumbra")
    await runner.session_service.create_session(app_name="penumbra", user_id=user_id, session_id=session_id)

    message = types.Content(role="user", parts=[types.Part(text=question)])
    final_text = None
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            text = event.content.parts[0].text
            if text:
                final_text = text

    if final_text is None:
        raise ValueError("agent produced no final response")
    return json.loads(final_text)
