"""Budget optimizer: plain Python, no model or LLM (CLAUDE.md is explicit
about this). Maximizes population-weighted modeled cooling (person-C) per
rupee under a budget and a per-ward spending cap. Also computes the naive
comparison: fund the hottest wards first, from the same catalog.

Simplifications, stated rather than hidden (see docs/DECISIONS.md):
- Each (ward, intervention) pair may be purchased up to MAX_UNITS_PER_PAIR
  times; every unit contributes the same modeled cooling (no diminishing
  returns beyond that cap, and beyond the per-ward spending cap).
- Only interventions with a quantified effect_mid_c (see
  server/tools/interventions.py -- tree canopy, lake/wetland buffer, pocket
  parks) contribute to person-C. Cool roofs and permeable paving can still
  be funded (real assumed cost) but contribute 0 modeled person-C here,
  since the cooling model has no covariate for their mechanism.
"""

MAX_UNITS_PER_PAIR = 5
DEFAULT_PER_WARD_CAP_FRACTION = 0.15


def _expand_candidates(ward: dict) -> list[dict]:
    """One entry per purchasable unit slot for this ward's applicable,
    quantified interventions."""
    items = []
    for iv in ward["interventions"]:
        if iv.get("effect_mid_c") is None:
            continue
        person_c = abs(iv["effect_mid_c"]) * ward["population"]
        cost = iv["cost_inr_per_unit"]
        if cost <= 0:
            continue
        for _ in range(MAX_UNITS_PER_PAIR):
            items.append({
                "ward_key": ward["ward_key"],
                "intervention_id": iv["intervention_id"],
                "cost_inr": cost,
                "person_c": person_c,
                "benefit_per_rupee": person_c / cost,
            })
    return items


def _greedy_allocate(ordered_items: list[dict], budget_inr: float, per_ward_cap: float, wards_by_key: dict) -> dict:
    remaining_budget = budget_inr
    ward_spend: dict[str, float] = {}
    picks: dict[tuple[str, str], dict] = {}

    for item in ordered_items:
        cost = item["cost_inr"]
        ward = item["ward_key"]
        spent_so_far = ward_spend.get(ward, 0.0)
        if cost > remaining_budget or spent_so_far + cost > per_ward_cap:
            continue
        remaining_budget -= cost
        ward_spend[ward] = spent_so_far + cost
        key = (ward, item["intervention_id"])
        if key not in picks:
            picks[key] = {"ward_key": ward, "intervention_id": item["intervention_id"], "units": 0, "cost_inr": 0.0, "person_c": 0.0}
        picks[key]["units"] += 1
        picks[key]["cost_inr"] += cost
        picks[key]["person_c"] += item["person_c"]

    allocation = sorted(picks.values(), key=lambda p: -p["person_c"])
    covered_wards = {p["ward_key"] for p in allocation}
    return {
        "allocation": allocation,
        "total_cost_inr": budget_inr - remaining_budget,
        "total_person_c": sum(p["person_c"] for p in allocation),
        "wards_covered": len(covered_wards),
        "people_covered": sum(wards_by_key[wk]["population"] for wk in covered_wards),
        "remaining_budget_inr": remaining_budget,
    }


def optimize(wards: list[dict], budget_inr: float, per_ward_cap_fraction: float = DEFAULT_PER_WARD_CAP_FRACTION) -> dict:
    """Greedy, ordered by benefit-per-rupee across every ward and intervention."""
    wards_by_key = {w["ward_key"]: w for w in wards}
    per_ward_cap = budget_inr * per_ward_cap_fraction
    items = sorted((c for w in wards for c in _expand_candidates(w)), key=lambda x: -x["benefit_per_rupee"])
    return _greedy_allocate(items, budget_inr, per_ward_cap, wards_by_key)


def naive_allocate(wards: list[dict], budget_inr: float, per_ward_cap_fraction: float = DEFAULT_PER_WARD_CAP_FRACTION) -> dict:
    """Naive baseline: fund the hottest wards first (by rank, 1 = hottest),
    spending each ward's own best-value options before moving to the next
    hottest ward -- the point of comparison is ward *order*, not
    cost-effectiveness across wards."""
    wards_by_key = {w["ward_key"]: w for w in wards}
    per_ward_cap = budget_inr * per_ward_cap_fraction
    items = []
    for ward in sorted(wards, key=lambda w: w["rank"]):
        items.extend(sorted(_expand_candidates(ward), key=lambda x: -x["benefit_per_rupee"]))
    return _greedy_allocate(items, budget_inr, per_ward_cap, wards_by_key)
