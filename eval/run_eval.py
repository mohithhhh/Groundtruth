"""Phase 5 ablation: answers every question in eval/questions.yaml three ways
and scores each answer against expected values computed fresh from
BigQuery (or the budget optimizer), never typed by hand.

  gemini_alone        Gemini with the same model ID, no tools, no data.
  agents_unverified   The Penumbra agent with its tools, narrative shown as
                      the model wrote it (every claim's text dropped in, no checks).
  penumbra            The same agent run, after the deterministic verifier.

The last two share one agent run per question, so the difference between
them is exactly what the verifier changes (see docs/DECISIONS.md).

Scores per answer:
  facts_correct / facts_expected  expected ward names and figures the answer states
  unsupported_figures             numbers in the answer that match no value in any
                                  tool result of that run (for Gemini alone: every
                                  number), ignoring numbers copied from the question
                                  and bare years
  latency_s, cost_usd             Gemini tokens at list price + BigQuery bytes billed

Run:
    source .venv/bin/activate
    GOOGLE_GENAI_USE_ENTERPRISE=1 GOOGLE_CLOUD_PROJECT=penumbra-509416 \\
      GOOGLE_CLOUD_LOCATION=us-central1 MODEL_ID=gemini-2.5-flash BQ_DATASET=penumbra \\
      python eval/run_eval.py [--only question_id ...]
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Gemini 2.5 Flash list price, USD per 1M tokens, paid tier, text, output
# including thinking tokens. Checked 2026-09-25 at
# https://ai.google.dev/gemini-api/docs/pricing (the Vertex AI pricing page
# did not render for the check; Vertex list prices for this model match).
PRICE_INPUT_PER_M = 0.30
PRICE_OUTPUT_PER_M = 2.50
# BigQuery on-demand analysis, USD per TiB (US multi-region list price).
PRICE_BQ_PER_TIB = 6.25

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "penumbra-509416")
DATASET = os.environ.get("BQ_DATASET", "penumbra")
MODEL_ID = os.environ.get("MODEL_ID", "gemini-2.5-flash")
TIMEOUT_S = 45  # same as POST /api/ask

GEMINI_ALONE_INSTRUCTION = (
    "You help city planners understand heat risk across Bengaluru's 369 wards "
    "(2025 ward delimitation, five corporations: Central, East, North, South, West). "
    "Answer the question directly and concisely with specific ward names and figures."
)

# ---------------------------------------------------------------- scoring

_MULTIPLIERS = {"%": 0.01, "crore": 1e7, "lakh": 1e5, "lakhs": 1e5, "million": 1e6, "billion": 1e9}
_FIGURE_RE = re.compile(
    r"(?<![\w.])[-−]?(\d+(?:,\d{2,3})*(?:\.\d+)?)\s?(%|crore|lakhs?|million|billion)?",
    re.IGNORECASE,
)


def figures(text: str) -> list[dict]:
    """Every number in the text, as the value(s) it could stand for: a
    displayed number x with d decimals stands for anything within half a
    unit of its last digit. "63%" also reads as 0.63; "12.3 lakh" as
    1,230,000. Signs are ignored ("cooled by 0.5" states -0.5)."""
    out = []
    for m in _FIGURE_RE.finditer(text):
        digits = m.group(1).replace(",", "")
        x = float(digits)
        half = 0.5 * 10 ** -(len(digits.split(".")[1]) if "." in digits else 0)
        suffix = (m.group(2) or "").lower()
        readings = [(x, half)]
        if suffix:
            mult = _MULTIPLIERS[suffix]
            readings = [(x * mult, half * mult)] + ([(x, half)] if suffix == "%" else [])
        out.append({"text": m.group(0).strip(), "readings": readings, "is_year": not suffix and "." not in digits and 1990 <= x <= 2035})
    return out


def matches(fig: dict, v: float, abs_tol: float | None = None) -> bool:
    v = abs(v)
    for x, half in fig["readings"]:
        if abs_tol is not None and abs(x - v) <= abs_tol + 1e-9:
            return True
        if abs(x - v) <= half + 1e-9 and (v == 0 or abs(x - v) / v <= 0.05):
            return True  # correctly rounded to the precision it was shown at
        if abs_tol is None and v != 0 and abs(x - v) / v <= 0.005:
            return True
    return False


def score_facts(text: str, rows: list[dict], expect: list[dict]) -> dict:
    lowered = text.lower()
    figs = figures(text)
    missing = []
    total = 0
    for check in expect:
        for row in rows:
            value = row[check["column"]]
            total += 1
            if check["kind"] == "entity":
                ok = str(value).lower() in lowered
            else:
                ok = value is not None and any(matches(f, float(value), check.get("abs_tol")) for f in figs)
            if not ok:
                missing.append({"column": check["column"], "expected": value})
    return {"facts_expected": total, "facts_correct": total - len(missing), "missing": missing}


def numeric_leaves(obj) -> list[float]:
    if isinstance(obj, bool) or obj is None:
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, str):  # e.g. a unit such as "1,000 sq m of roof coated"
        return [x for f in figures(obj) for x, _ in f["readings"]]
    if isinstance(obj, dict):
        return [x for v in obj.values() for x in numeric_leaves(v)]
    if isinstance(obj, (list, tuple)):
        return [x for v in obj for x in numeric_leaves(v)]
    return []


def unsupported_figures(text: str, question: str, tool_values: list[float]) -> list[str]:
    in_question = figures(question)
    out = []
    for f in figures(text):
        if f["is_year"]:
            continue
        if any(q["text"] == f["text"] for q in in_question):
            continue
        if any(matches(f, v) for v in tool_values):
            continue
        out.append(f["text"])
    return out


def render_unverified(narrative: str, claims: list[dict]) -> str:
    """What the reader would see with no verifier: every claim's text
    dropped into its placeholder, stray numbers left as written."""
    by_id = {c["id"]: c["text"] for c in claims}
    return re.sub(r"\{(c\d+)\}", lambda m: by_id.get(m.group(1), ""), narrative)


# ---------------------------------------------------------------- runs

def cost_usd(usage: dict, bytes_billed: int = 0) -> float:
    tokens_out = usage.get("candidates_token_count", 0) + usage.get("thoughts_token_count", 0)
    return (usage.get("prompt_token_count", 0) * PRICE_INPUT_PER_M + tokens_out * PRICE_OUTPUT_PER_M) / 1e6 \
        + bytes_billed / 2**40 * PRICE_BQ_PER_TIB


def expected_rows(q: dict) -> list[dict]:
    from google.cloud import bigquery

    if "expected_sql" in q:
        client = bigquery.Client(project=PROJECT)
        sql = q["expected_sql"].replace("{T}", f"{PROJECT}.{DATASET}")
        return [dict(r) for r in client.query(sql).result()]

    from server.optimizer.plan import run_plan
    from server.store import ToolResultStore

    p = q["expected_plan"]
    plan = run_plan(ToolResultStore(), "bengaluru", p["corporation"], p["budget_inr"])
    return [plan["data"]["comparison"]]


def run_gemini_alone(client, question: str) -> dict:
    from google.genai import types

    from server.agents.run import add_usage

    t0 = time.time()
    usage: dict = {}
    try:
        resp = client.models.generate_content(
            model=MODEL_ID, contents=question,
            config=types.GenerateContentConfig(system_instruction=GEMINI_ALONE_INSTRUCTION),
        )
        text, error = resp.text or "", None
        if resp.usage_metadata:
            add_usage(usage, resp.usage_metadata)
    except Exception as e:  # recorded, not hidden: a failed call scores zero
        text, error = "", f"{type(e).__name__}: {e}"
    return {"text": text, "error": error, "latency_s": time.time() - t0, "usage": usage, "tool_values": []}


async def run_agent(question: str) -> dict:
    from server.agents.orchestrator import build_orchestrator
    from server.agents.run import run_agent_for_final_answer
    from server.store import ToolResultStore
    from server.tools import bq
    from server.verify.checker import verify_answer

    store = ToolResultStore()
    usage: dict = {}
    bytes_before = bq.stats["bytes_billed"]
    t0 = time.time()
    answer, error = None, None
    try:
        answer = await asyncio.wait_for(
            run_agent_for_final_answer(build_orchestrator(store), question, usage=usage), timeout=TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        error = f"timeout after {TIMEOUT_S} s"
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    agent_s = time.time() - t0

    entries = list(store._results.values())
    tool_values = numeric_leaves([[e["data"], e["params"]] for e in entries])
    base = {
        "error": error, "usage": usage, "bytes_billed": bq.stats["bytes_billed"] - bytes_before,
        "tool_values": tool_values, "tool_calls": [e["tool_name"] for e in entries],
    }
    if answer is None:
        return {
            "agents_unverified": {**base, "text": "", "latency_s": agent_s},
            "penumbra": {**base, "text": "", "latency_s": agent_s, "verification": None},
        }

    t1 = time.time()
    verified = verify_answer(answer["narrative"], answer["claims"], store.get)
    verify_s = time.time() - t1
    return {
        "agents_unverified": {**base, "text": render_unverified(answer["narrative"], answer["claims"]), "latency_s": agent_s,
                              "raw_answer": answer},
        "penumbra": {**base, "text": verified.narrative, "latency_s": agent_s + verify_s,
                     "verification": verified.as_dict()},
    }


CONFIGS = ("gemini_alone", "agents_unverified", "penumbra")


def summarize(records: list[dict]) -> dict:
    out = {}
    for c in CONFIGS:
        rs = [r["configs"][c] for r in records]
        n = len(rs)
        latencies = sorted(x["latency_s"] for x in rs)
        facts_exp = sum(x["facts_expected"] for x in rs)
        out[c] = {
            "questions": n,
            "fully_correct": sum(x["facts_correct"] == x["facts_expected"] for x in rs),
            "facts_correct": sum(x["facts_correct"] for x in rs),
            "facts_expected": facts_exp,
            "answers_with_unsupported_figures": sum(bool(x["unsupported_figures"]) for x in rs),
            "unsupported_figures": sum(len(x["unsupported_figures"]) for x in rs),
            "errors": sum(bool(x["error"]) for x in rs),
            "latency_median_s": round(latencies[n // 2] if n % 2 else (latencies[n // 2 - 1] + latencies[n // 2]) / 2, 2),
            "latency_max_s": round(latencies[-1], 2),
            "cost_usd_mean": round(sum(x["cost_usd"] for x in rs) / n, 5),
        }
    by_cat: dict = {}
    for r in records:
        for c in CONFIGS:
            b = by_cat.setdefault(r["category"], {}).setdefault(c, {"questions": 0, "fully_correct": 0})
            b["questions"] += 1
            b["fully_correct"] += r["configs"][c]["facts_correct"] == r["configs"][c]["facts_expected"]
    out["by_category"] = by_cat
    return out


async def main(only: list[str]) -> None:
    from google import genai

    with open(os.path.join(HERE, "questions.yaml")) as f:
        questions = yaml.safe_load(f)["questions"]
    if only:
        questions = [q for q in questions if q["id"] in only]

    client = genai.Client(vertexai=True, project=PROJECT, location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"))
    records = []
    for q in questions:
        rows = expected_rows(q)
        configs = {"gemini_alone": run_gemini_alone(client, q["question"]), **(await run_agent(q["question"]))}
        for name, r in configs.items():
            r.update(score_facts(r["text"], rows, q["expect"]))
            r["unsupported_figures"] = unsupported_figures(r["text"], q["question"], r["tool_values"])
            r["cost_usd"] = cost_usd(r["usage"], r.get("bytes_billed", 0))
            r["latency_s"] = round(r["latency_s"], 3)
        records.append({"id": q["id"], "category": q["category"], "question": q["question"],
                        "expected": rows, "configs": configs})
        print(f"{q['id']:<32}" + "  ".join(
            f"{c}={configs[c]['facts_correct']}/{configs[c]['facts_expected']} u{len(configs[c]['unsupported_figures'])}"
            for c in CONFIGS), flush=True)

    now = datetime.now(timezone.utc)
    run = {
        "generated_at": now.isoformat(),
        "generated_by": "eval/run_eval.py",
        "model_id": MODEL_ID,
        "prices": {"input_usd_per_m": PRICE_INPUT_PER_M, "output_usd_per_m": PRICE_OUTPUT_PER_M, "bigquery_usd_per_tib": PRICE_BQ_PER_TIB},
        "summary": summarize(records),
        "questions": records,
    }
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    path = os.path.join(HERE, "results", f"run_{now.strftime('%Y%m%dT%H%M%SZ')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=1, default=str)
    if not only:  # only a full run becomes the result the Method page shows
        with open(os.path.join(HERE, "results", "latest.json"), "w", encoding="utf-8") as f:
            json.dump(run, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps(run["summary"], indent=1))
    print(f"Wrote {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=[])
    asyncio.run(main(ap.parse_args().only))
