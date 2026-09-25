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
    assert result.template == "Ward {c1} warmed by ."
    assert result.narrative == "Ward Bellandur warmed by ."


def test_fully_verified_footer_matches_no_removals():
    claims = [{"id": "c1", "text": "Bellandur", "kind": "entity", "tool_result_id": TOOL_RESULT_ID, "path": "data[0].ward_name"}]
    result = verify_answer("Ward {c1}.", claims, lookup)
    assert result.as_dict() == {"verified": 1, "total": 1, "removed": []}
