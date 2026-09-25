from server.verify.checker import verify_answer

TOOL_RESULT_ID = "tr-1"
ENTRY = {
    "tool_name": "rank_wards",
    "data": [{"ward_name": "Bellandur", "value": 3.1}],
}


def lookup(tool_result_id):
    return ENTRY if tool_result_id == TOOL_RESULT_ID else None


def test_pass_entity_and_number():
    narrative = "Ward {c1} warmed the most, by {c2}."
    claims = [
        {"id": "c1", "text": "Bellandur", "kind": "entity", "tool_result_id": TOOL_RESULT_ID, "path": "data[0].ward_name"},
        {"id": "c2", "text": "3.1 °C", "kind": "number", "value": 3.1, "unit": "°C", "tool_result_id": TOOL_RESULT_ID, "path": "data[0].value"},
    ]
    result = verify_answer(narrative, claims, lookup)
    assert result.verified == 2
    assert result.total == 2
    assert result.removed == []
    assert "Bellandur" in result.narrative
    assert "3.1" in result.narrative


def test_number_within_celsius_tolerance_still_passes():
    claims = [{"id": "c1", "text": "3.12 °C", "kind": "number", "value": 3.12, "unit": "°C", "tool_result_id": TOOL_RESULT_ID, "path": "data[0].value"}]
    result = verify_answer("Change: {c1}.", claims, lookup)
    assert result.verified == 1


def test_number_outside_tolerance_fails():
    claims = [{"id": "c1", "text": "9.9 °C", "kind": "number", "value": 9.9, "unit": "°C", "tool_result_id": TOOL_RESULT_ID, "path": "data[0].value"}]
    result = verify_answer("Change: {c1}.", claims, lookup)
    assert result.verified == 0
    assert result.total == 1
    assert result.removed[0]["id"] == "c1"
    assert "{c1}" not in result.narrative


def test_missing_path_fails():
    claims = [{"id": "c1", "text": "x", "kind": "entity", "tool_result_id": TOOL_RESULT_ID, "path": "data[0].nonexistent_field"}]
    result = verify_answer("Value: {c1}.", claims, lookup)
    assert result.verified == 0
    assert "could not resolve" in result.removed[0]["reason"]


def test_unit_mismatch_fails():
    # Claimed 3.1 percent but tool result path holds a plain number meant as Celsius --
    # unit affects tolerance choice, so a Celsius-tolerance value misdeclared as % uses
    # the tighter relative tolerance and should fail if the values don't match closely.
    claims = [{"id": "c1", "text": "50%", "kind": "number", "value": 50.0, "unit": "%", "tool_result_id": TOOL_RESULT_ID, "path": "data[0].value"}]
    result = verify_answer("Share: {c1}.", claims, lookup)
    assert result.verified == 0
    assert result.removed[0]["id"] == "c1"


def test_unknown_tool_result_id_fails():
    claims = [{"id": "c1", "text": "x", "kind": "entity", "tool_result_id": "does-not-exist", "path": "data[0].ward_name"}]
    result = verify_answer("Ward: {c1}.", claims, lookup)
    assert result.verified == 0
    assert result.removed[0]["reason"] == "unknown tool_result_id"


def test_placeholder_with_no_matching_claim_fails():
    result = verify_answer("Ward {c1} and {c2}.", [
        {"id": "c1", "text": "Bellandur", "kind": "entity", "tool_result_id": TOOL_RESULT_ID, "path": "data[0].ward_name"},
    ], lookup)
    assert result.verified == 1
    assert result.total == 2
    assert any(r["id"] == "c2" for r in result.removed)


def test_stray_number_outside_placeholder_is_flagged():
    claims = [{"id": "c1", "text": "Bellandur", "kind": "entity", "tool_result_id": TOOL_RESULT_ID, "path": "data[0].ward_name"}]
    result = verify_answer("Ward {c1} warmed by 3.1 degrees.", claims, lookup)
    assert result.verified == 1
    stray = [r for r in result.removed if r["id"] is None]
    assert len(stray) == 1
    assert "3.1" in stray[0]["reason"]
    assert result.narrative == "Ward Bellandur warmed by degrees."


def test_stray_number_with_unit_and_grouping_is_cut():
    result = verify_answer("It has 1,23,456 people and warmed 0.8 °C.", [], lookup)
    assert len(result.removed) == 2
    assert result.narrative == "It has people and warmed."


def test_number_claim_with_missing_value_fails_cleanly():
    # Regression: a live run crashed the whole request with TypeError when
    # the model returned kind='number' without setting value (Optional in
    # the schema, so nothing forced it) -- must fail the claim, not crash.
    claims = [{"id": "c1", "text": "3.1 °C", "kind": "number", "value": None, "unit": "°C", "tool_result_id": TOOL_RESULT_ID, "path": "data[0].value"}]
    result = verify_answer("Change: {c1}.", claims, lookup)
    assert result.verified == 0
    assert result.removed[0]["id"] == "c1"


def test_gemini_function_response_prefix_is_normalized():
    entry = {"tool_name": "rank_wards", "data": [{"ward_name": "Bellandur"}]}

    def lookup_ranked(tool_result_id):
        return entry if tool_result_id == TOOL_RESULT_ID else None

    claims = [{"id": "c1", "text": "Bellandur", "kind": "entity", "tool_result_id": TOOL_RESULT_ID, "path": "rank_wards_response.data[0].ward_name"}]
    result = verify_answer("Top ward: {c1}.", claims, lookup_ranked)
    assert result.verified == 1


def test_template_keeps_verified_tokens_and_drops_failed_ones():
    claims = [
        {"id": "c1", "text": "Bellandur", "kind": "entity", "tool_result_id": TOOL_RESULT_ID, "path": "data[0].ward_name"},
        {"id": "c2", "text": "9.9 °C", "kind": "number", "value": 9.9, "unit": "°C", "tool_result_id": TOOL_RESULT_ID, "path": "data[0].value"},
    ]
    result = verify_answer("Ward {c1} warmed by {c2}.", claims, lookup)
    assert result.template == "Ward {c1} warmed by."
    assert result.narrative == "Ward Bellandur warmed by."


def test_fully_verified_footer_matches_no_removals():
    claims = [{"id": "c1", "text": "Bellandur", "kind": "entity", "tool_result_id": TOOL_RESULT_ID, "path": "data[0].ward_name"}]
    result = verify_answer("Ward {c1}.", claims, lookup)
    assert result.as_dict() == {"verified": 1, "total": 1, "removed": []}


def test_failed_claim_takes_its_trailing_unit_and_any_response_prefix_resolves():
    entry = {"tool_name": "budget_plan", "data": {"total": 12.0}}
    claims = [
        {"id": "c1", "text": "12", "kind": "number", "value": 12.0, "unit": "person-°C", "tool_result_id": "t", "path": "plan_budget_response.data.total"},
        {"id": "c2", "text": "31.7", "kind": "number", "value": 31.7, "unit": "°C", "tool_result_id": "missing", "path": "data.x"},
    ]
    result = verify_answer("Plan gives {c1} person-°C; ward is {c2}°C.", claims, lambda i: entry if i == "t" else None)
    assert result.verified == 1
    assert result.narrative == "Plan gives 12 person-°C; ward is."


def test_year_resolves_from_call_params_and_missing_data_level_is_tolerated():
    entry = {"tool_name": "rank_wards", "params": {"year": 2025}, "data": {"comparison": {"people": 231552}}}
    claims = [
        {"id": "c1", "text": "2025", "kind": "number", "value": 2025, "unit": "year", "tool_result_id": "t", "path": "data[0].year"},
        {"id": "c2", "text": "231,552", "kind": "number", "value": 231552, "unit": "people", "tool_result_id": "t", "path": "comparison.people"},
        {"id": "c3", "text": "2016", "kind": "number", "value": 2016, "unit": "year", "tool_result_id": "t", "path": "year"},
    ]
    result = verify_answer("In {c1}, {c2} people; not {c3}.", claims, lambda i: entry)
    assert result.verified == 2
    assert result.removed[0]["id"] == "c3"


def test_crore_claim_is_scaled_and_still_exact():
    entry = {"tool_name": "budget_plan", "data": {"budget_inr": 500000000.0, "spent": 499500000}}
    ok = {"id": "c1", "text": "50", "kind": "number", "value": 50, "unit": "crore rupees", "tool_result_id": "t", "path": "data.budget_inr"}
    bad = {**ok, "id": "c2", "path": "data.spent"}
    result = verify_answer("{c1} and {c2}", [ok, bad], lambda i: entry)
    assert [c["id"] for c in result.verified_claims] == ["c1"]
