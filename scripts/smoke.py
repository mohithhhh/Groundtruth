"""Smoke test for a deployed Penumbra: the pages load, the map's data and
worker are served, and one question, one source, one plan and one brief
work end to end on real data. Standard library only.

Run:
    python scripts/smoke.py https://penumbra-app-891315005311.us-central1.run.app
"""

import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://penumbra-app-891315005311.us-central1.run.app").rstrip("/")
QUESTION = "Which five wards in the East corporation warmed most since the baseline year?"
failures = []


def fetch(path, body=None, timeout=60):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json"} if body is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("content-type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("content-type", ""), e.read()


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}{f'  ({detail})' if detail else ''}")
    if not ok:
        failures.append(name)


status, _, body = fetch("/api/health")
check("health", status == 200 and json.loads(body).get("status") == "ok")

for page in ("/", "/ask", "/plan", "/method"):
    status, ctype, body = fetch(page)
    check(f"page {page}", status == 200 and "text/html" in ctype and b'id="root"' in body)

status, _, body = fetch("/data/wards.geojson")
check("ward polygons", status == 200 and len(json.loads(body)["features"]) == 369)

status, _, body = fetch("/data/results.json")
evaluation = json.loads(body).get("evaluation") if status == 200 else None
check("results file with evaluation", evaluation is not None)

status, _, _ = fetch("/assets/does-not-exist.js")
check("missing asset is a 404, not the app", status == 404)

status, _, body = fetch("/api/wards?year=2025")
wards = json.loads(body) if status == 200 else []
check("ward list", len(wards) == 369, f"{len(wards)} wards")

t0 = time.time()
status, _, body = fetch("/api/ask", {"question": QUESTION}, timeout=90)
ask = json.loads(body) if status == 200 else {}
v = ask.get("verification", {})
check("ask: every figure verified", status == 200 and v.get("total", 0) > 0 and v.get("verified") == v.get("total"),
      f"{v.get('verified')} of {v.get('total')} in {time.time() - t0:.1f} s")

if ask.get("claims"):
    # The source row is written to BigQuery asynchronously after the answer.
    for _ in range(10):
        status, _, body = fetch(f"/api/sources/{ask['claims'][0]['tool_result_id']}")
        if status == 200:
            break
        time.sleep(2)
    check("source of the first figure", status == 200 and "tool_name" in json.loads(body))

status, _, body = fetch("/api/plan", {"budget_inr": 500_000_000, "corporation": "East"}, timeout=90)
plan = json.loads(body) if status == 200 else {}
c = plan.get("comparison", {})
check("plan with naive comparison", status == 200 and c.get("optimized_total_person_c", 0) > 0 and "naive_total_person_c" in c)

if wards:
    status, _, body = fetch(f"/api/brief/{wards[0]['ward_key']}?lang=kn")
    check("ward brief in Kannada", status == 200 and json.loads(body).get("lang") == "kn")

print(f"\n{len(failures)} failed" if failures else "\nAll checks passed")
sys.exit(1 if failures else 0)
