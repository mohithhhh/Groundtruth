import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_eval import figures, numeric_leaves, render_unverified, score_facts, unsupported_figures  # noqa: E402


def test_rounded_and_scaled_figures_match():
    rows = [{"lst": 31.24, "pop": 1234567, "frac": 0.634, "name": "Vijinapura"}]
    expect = [{"column": "lst", "kind": "number", "abs_tol": 0.05}, {"column": "pop", "kind": "number"},
              {"column": "frac", "kind": "number"}, {"column": "name", "kind": "entity"}]
    text = "Vijinapura is 31.2 °C, home to 12.3 lakh people, 63% built up."
    assert score_facts(text, rows, expect)["facts_correct"] == 4


def test_wrong_and_too_coarse_figures_fail():
    rows = [{"lst": 31.24, "ndvi": 0.24}]
    expect = [{"column": "lst", "kind": "number", "abs_tol": 0.05}, {"column": "ndvi", "kind": "number", "abs_tol": 0.005}]
    assert score_facts("It is 31.4 °C with NDVI 0.2.", rows, expect)["facts_correct"] == 0


def test_unsupported_ignores_years_and_question_numbers():
    text = "Between 2016 and 2025 the top 5 wards warmed 1.9 °C and 7.7 °C."
    assert unsupported_figures(text, "Which 5 wards warmed most?", [1.87]) == ["7.7"]
    assert figures("cooled by −0.5")[0]["readings"][0][0] == 0.5
    assert unsupported_figures("Per 1,000 sq m.", "?", numeric_leaves({"unit": "1,000 sq m"})) == []


def test_unverified_render_keeps_everything():
    claims = [{"id": "c1", "text": "3.1 °C"}]
    assert render_unverified("Warmed {c1}, about 4 more.", claims) == "Warmed 3.1 °C, about 4 more."
