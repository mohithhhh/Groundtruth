from server.optimizer.allocator import naive_allocate, optimize

# Ward A: hottest (rank 1), huge population, but expensive/low-yield intervention.
# Ward B: coolest (rank 2), tiny population, but a cheap/high-yield intervention.
WARDS = [
    {
        "ward_key": "A", "rank": 1, "population": 100_000,
        "interventions": [
            {"intervention_id": "expensive", "cost_inr_per_unit": 1_000_000, "effect_mid_c": -0.1},
        ],
    },
    {
        "ward_key": "B", "rank": 2, "population": 1_000,
        "interventions": [
            {"intervention_id": "cheap", "cost_inr_per_unit": 1_000, "effect_mid_c": -5.0},
        ],
    },
]


def test_optimizer_picks_higher_benefit_per_rupee_regardless_of_rank():
    # A: benefit/rupee = (0.1 * 100_000) / 1_000_000 = 0.01
    # B: benefit/rupee = (5.0 * 1_000) / 1_000 = 5.0  -- much better
    result = optimize(WARDS, budget_inr=2_000, per_ward_cap_fraction=1.0)
    picked_wards = {p["ward_key"] for p in result["allocation"]}
    assert picked_wards == {"B"}
    assert result["total_person_c"] == 5.0 * 1_000 * 2  # 2 units afforded


def test_naive_allocate_funds_hottest_ward_first_even_if_worse_value():
    result = naive_allocate(WARDS, budget_inr=2_000, per_ward_cap_fraction=1.0)
    # Ward A is rank 1 (hottest) but its intervention costs 1,000,000 --
    # unaffordable at all with a 2,000 budget, so naive falls through to B.
    picked_wards = {p["ward_key"] for p in result["allocation"]}
    assert picked_wards == {"B"}


def test_naive_prefers_hot_ward_when_affordable():
    wards = [
        {"ward_key": "HOT", "rank": 1, "population": 1000, "interventions": [
            {"intervention_id": "x", "cost_inr_per_unit": 100, "effect_mid_c": -0.01},
        ]},
        {"ward_key": "COOL", "rank": 2, "population": 1000, "interventions": [
            {"intervention_id": "x", "cost_inr_per_unit": 100, "effect_mid_c": -10.0},
        ]},
    ]
    naive = naive_allocate(wards, budget_inr=100, per_ward_cap_fraction=1.0)
    optimized = optimize(wards, budget_inr=100, per_ward_cap_fraction=1.0)
    assert {p["ward_key"] for p in naive["allocation"]} == {"HOT"}
    assert {p["ward_key"] for p in optimized["allocation"]} == {"COOL"}
    assert optimized["total_person_c"] > naive["total_person_c"]


def test_per_ward_cap_spreads_budget_across_wards():
    wards = [
        {"ward_key": w, "rank": i + 1, "population": 1000, "interventions": [
            {"intervention_id": "x", "cost_inr_per_unit": 100, "effect_mid_c": -1.0},
        ]}
        for i, w in enumerate(["A", "B", "C"])
    ]
    # Cap each ward at 20% of a 1000 budget = 200 -> 2 units each -> spread across all 3.
    result = optimize(wards, budget_inr=1000, per_ward_cap_fraction=0.2)
    assert result["wards_covered"] == 3
    assert all(p["units"] <= 2 for p in result["allocation"])


def test_unquantified_interventions_are_excluded_from_optimization():
    wards = [{"ward_key": "A", "rank": 1, "population": 1000, "interventions": [
        {"intervention_id": "cool_roofs", "cost_inr_per_unit": 100, "effect_mid_c": None},
    ]}]
    result = optimize(wards, budget_inr=1000)
    assert result["allocation"] == []
    assert result["total_person_c"] == 0


def test_people_covered_counts_ward_population_once_per_ward():
    result = optimize(WARDS, budget_inr=2_000, per_ward_cap_fraction=1.0)
    assert result["people_covered"] == 1_000  # only ward B was funded
