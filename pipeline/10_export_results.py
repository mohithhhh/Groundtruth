"""Phase 4: export the numbers the Method page shows, straight from the
tables and scripts that produced them, into web/public/data/results.json.

The Method page renders only from this file -- no figure on it is typed by
hand (CLAUDE.md Section 10). Each section records which script produced it.
The evaluation/ablation section is null until Phase 5 runs it, and the page
says so rather than showing placeholders.

Run (after pipeline 01-09 and model/cooling_model.py):
    source .venv/bin/activate
    python pipeline/10_export_results.py
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")
from server.optimizer.allocator import naive_allocate, optimize  # noqa: E402
from server.store import ToolResultStore  # noqa: E402
from server.tools.interventions import bulk_recommend_interventions  # noqa: E402

PROJECT = "penumbra-509416"
DATASET = "penumbra"
T = f"{PROJECT}.{DATASET}"
OUT = "web/public/data/results.json"
PLAN_CORPORATION = "East"
PLAN_BUDGET_INR = 500_000_000


def bq(sql: str) -> list[dict]:
    out = subprocess.run(
        ["bq", "--quiet", "query", "--use_legacy_sql=false", "--max_rows=1000", "--format=json", sql],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def num(v):
    return None if v is None else float(v)


def main():
    coverage = bq(f"""
    SELECT year, COUNT(*) AS wards, MIN(lst_mean_c) AS lst_min, AVG(lst_mean_c) AS lst_avg,
      MAX(lst_mean_c) AS lst_max, MIN(valid_pixel_frac) AS min_valid_pixel_frac
    FROM `{T}.ward_metrics` GROUP BY year ORDER BY year
    """)

    weights = bq(f"""
    SELECT DISTINCT weight_heat, weight_green, weight_built, weight_exposure FROM `{T}.ward_risk`
    """)[0]

    effects = bq(f"""
    SELECT intervention, unit_change, effect_low_c, effect_mid_c, effect_high_c,
      held_out_r2, held_out_rmse_c, n_samples, model_type, fitted_date, usable, note
    FROM `{T}.effect_model` ORDER BY intervention
    """)

    with open("pipeline/07_validate_risk.sql") as f:
        # Drop comment lines: a leading "--" argument is parsed by bq as a flag.
        sql = "\n".join(line for line in f if not line.lstrip().startswith("--"))
    sensitivity = bq(sql)

    extremes_sql = """
    SELECT r.rank, w.ward_key, w.ward_name, w.corporation, m.lst_mean_c, m.ndvi_mean, r.composite_risk
    FROM `{T}.ward_risk` AS r
    JOIN `{T}.wards_clean` AS w USING (ward_key)
    JOIN `{T}.ward_metrics` AS m ON m.ward_key = r.ward_key AND m.year = r.year
    WHERE r.year = 2025 ORDER BY r.rank {order} LIMIT 10
    """
    hottest = bq(extremes_sql.format(T=T, order="ASC"))
    coolest = bq(extremes_sql.format(T=T, order="DESC"))

    store = ToolResultStore(max_calls=4)
    wards = bulk_recommend_interventions(store, "bengaluru", PLAN_CORPORATION, 2025)["data"]["wards"]
    opt = optimize(wards, PLAN_BUDGET_INR)
    naive = naive_allocate(wards, PLAN_BUDGET_INR)

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "pipeline/10_export_results.py",
        "coverage": {
            "source": "pipeline/03_zonal_stats.sql -> ward_metrics",
            "years": [
                {"year": int(r["year"]), "wards": int(r["wards"]), "lst_min_c": num(r["lst_min"]),
                 "lst_avg_c": num(r["lst_avg"]), "lst_max_c": num(r["lst_max"]),
                 "min_valid_pixel_frac": num(r["min_valid_pixel_frac"])}
                for r in coverage
            ],
        },
        "risk_weights": {
            "source": "pipeline/06_risk.sql -> ward_risk",
            "heat": num(weights["weight_heat"]), "green": num(weights["weight_green"]),
            "built": num(weights["weight_built"]), "exposure": num(weights["weight_exposure"]),
        },
        "cooling_model": {
            "source": "model/cooling_model.py -> effect_model",
            "held_out_r2": num(effects[0]["held_out_r2"]),
            "held_out_rmse_c": num(effects[0]["held_out_rmse_c"]),
            "n_samples": int(effects[0]["n_samples"]),
            "model_type": effects[0]["model_type"],
            "fitted_date": effects[0]["fitted_date"],
            "effects": [
                {"intervention": e["intervention"], "unit_change": num(e["unit_change"]),
                 "low_c": num(e["effect_low_c"]), "mid_c": num(e["effect_mid_c"]), "high_c": num(e["effect_high_c"]),
                 "usable": e["usable"] in (True, "true"), "note": e["note"]}
                for e in effects
            ],
        },
        "weight_sensitivity": {
            "source": "pipeline/07_validate_risk.sql",
            "rows": [{"perturbation": r["label"], "spearman_rho": num(r["spearman_rho"])} for r in sensitivity],
        },
        "ranking_extremes": {
            "source": "pipeline/06_risk.sql -> ward_risk, year 2025",
            "hottest": [{k: (num(v) if k in ("lst_mean_c", "ndvi_mean", "composite_risk") else v) for k, v in r.items()} for r in hottest],
            "coolest": [{k: (num(v) if k in ("lst_mean_c", "ndvi_mean", "composite_risk") else v) for k, v in r.items()} for r in coolest],
        },
        "plan_comparison": {
            "source": "server/optimizer/allocator.py via server/tools/interventions.py",
            "corporation": PLAN_CORPORATION,
            "budget_inr": PLAN_BUDGET_INR,
            "optimized": {k: opt[k] for k in ("total_person_c", "people_covered", "wards_covered", "total_cost_inr")},
            "naive": {k: naive[k] for k in ("total_person_c", "people_covered", "wards_covered", "total_cost_inr")},
        },
        # Phase 5 fills this from eval/run_eval.py. Until then the Method page
        # states that the ablation has not been run.
        "evaluation": None,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
