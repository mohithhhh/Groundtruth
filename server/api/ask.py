import asyncio
import re
import time
import uuid
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from server.agents.orchestrator import build_orchestrator
from server.agents.run import run_agent_for_final_answer
from server.store import ToolResultStore
from server.verify.checker import verify_answer

router = APIRouter()

REQUEST_TIMEOUT_SECONDS = 45
RATE_LIMIT_PER_MINUTE = 10

# ponytail: in-memory sliding window, resets on restart/per-instance. A real
# multi-instance deployment would need a shared store (e.g. Firestore/Redis)
# to make this hold across Cloud Run instances -- fine for a hackathon demo.
_request_log: dict[str, deque] = defaultdict(deque)

# Below-ward-level questions have no tool that can ground them; refusing up
# front is more honest than letting the agent try and the Verifier strip
# everything out silently.
_SUB_WARD_PATTERN = re.compile(
    r"\b(street|road|avenue|lane|house no|building|apartment|flat no|plot|survey number|"
    r"pin ?code|door no)\b",
    re.IGNORECASE,
)


class AskRequest(BaseModel):
    question: str
    city_id: str = "bengaluru"
    session_id: str | None = None


def _check_rate_limit(client_ip: str) -> None:
    now = time.time()
    window = _request_log[client_ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Too many questions this minute. Wait a moment and try again.")
    window.append(now)


@router.post("/ask")
async def ask(request: Request, body: AskRequest):
    _check_rate_limit(request.client.host if request.client else "unknown")

    if _SUB_WARD_PATTERN.search(body.question):
        raise HTTPException(
            status_code=400,
            detail="Penumbra answers at ward level and above -- it can't make claims about a specific street, building, or address.",
        )

    start_time = time.time()
    store = ToolResultStore()
    orchestrator = build_orchestrator(store)
    session_id = body.session_id or str(uuid.uuid4())

    try:
        answer = await asyncio.wait_for(
            run_agent_for_final_answer(orchestrator, body.question, session_id),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Penumbra took longer than 45 seconds. Try a narrower question, such as one corporation.",
        )
    except ValueError:  # the model ended without a structured answer
        raise HTTPException(
            status_code=502,
            detail="Penumbra could not finish an answer to that question. Ask it again, or make it narrower, such as one ward or corporation.",
        )

    trace = store.trace(start_time, answered_at=time.time())
    verify_start = time.time()
    result = verify_answer(answer["narrative"], answer["claims"], store.get)
    trace.append({
        "step": len(trace) + 1,
        "description": f"Checked {result.total} figures",
        "duration_s": round(time.time() - verify_start, 3),
    })

    return {
        "narrative": result.narrative,
        "narrative_template": result.template,
        "claims": result.verified_claims,
        "verification": result.as_dict(),
        "highlight_ward_keys": answer.get("highlight_ward_keys", []),
        "trace": trace,
        "session_id": session_id,
    }
