"""Integration tests against the real BigQuery tables Phase 1 built --
no mocking, since the point is to catch exactly the kind of bug found
during manual testing (valid_pixel_frac > 1.0, see docs/DECISIONS.md).
"""

import pytest

from server.store import ToolResultStore
from server.tools import wards

KNOWN_WARD = "ward_369_final.317"  # Padarayanapura


@pytest.fixture
def store():
    return ToolResultStore()


def test_get_ward_metrics_known_ward(store):
    result = wards.get_ward_metrics(store, "bengaluru", KNOWN_WARD, 2025)
    assert result["tool_result_id"]
    data = result["data"]
    assert data["ward_name"] == "Padarayanapura"
    assert 0 <= data["valid_pixel_frac"] <= 1.02


def test_get_ward_metrics_unknown_ward_returns_none(store):
    result = wards.get_ward_metrics(store, "bengaluru", "not_a_real_ward", 2025)
    assert result["data"] is None


def test_find_ward_tolerates_typo(store):
    result = wards.find_ward(store, "bengaluru", "padrayanapura")
    assert result["data"][0]["ward_key"] == KNOWN_WARD


def test_rank_wards_rejects_unknown_metric(store):
    with pytest.raises(ValueError):
        wards.rank_wards(store, "bengaluru", "not_a_real_metric", 5, 2025)


def test_rank_wards_respects_corporation_filter(store):
    result = wards.rank_wards(store, "bengaluru", "delta_lst_c", 5, 2025, corporation="East")
    assert len(result["data"]) == 5
    assert all(row["corporation"] == "East" for row in result["data"])


def test_compare_years_computes_change(store):
    result = wards.compare_years(store, "bengaluru", [KNOWN_WARD], "lst_mean_c", 2016, 2025)
    row = result["data"][0]
    assert row["change"] == pytest.approx(row["value_b"] - row["value_a"])


def test_corporation_summary_ward_count(store):
    result = wards.corporation_summary(store, "bengaluru", "East", 2025)
    assert result["data"]["ward_count"] == 50


def test_nearby_facilities_counts_match_list(store):
    result = wards.nearby_facilities(store, "bengaluru", KNOWN_WARD)
    data = result["data"]
    assert data["counts"]["hospital"] == sum(1 for f in data["facilities"] if f["type"] == "hospital")
    assert data["counts"]["school"] == sum(1 for f in data["facilities"] if f["type"] == "school")
