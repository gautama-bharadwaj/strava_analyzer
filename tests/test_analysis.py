from datetime import date

import pytest

from stravadash import analysis
from stravadash.demo import populate
from stravadash.hevy_parser import parse_description
from stravadash.store import Store

TODAY = date(2026, 11, 11)  # a Wednesday


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    store = Store(tmp_path_factory.mktemp("d") / "db.sqlite")
    populate(store, today=TODAY)
    return analysis.build(store.conn, today=TODAY)


def gym(store, i, day, desc):
    store.save_detail({"id": i, "name": "Gym", "sport_type": "WeightTraining", "start_date": f"{day}T18:00:00Z",
                       "start_date_local": f"{day}T18:00:00Z", "description": desc})
    store.replace_gym_sets(i, parse_description(desc))


def test_epley():
    assert analysis.epley_1rm(100, 1) == 100
    assert analysis.epley_1rm(100, 10) == pytest.approx(133.33, abs=0.01)


def test_build_shapes(demo):
    assert demo["units"]["weight"] == "lb"
    assert len(demo["weekly"]["weeks"]) == 26 == len(demo["weekly"]["sessions"])
    assert demo["exercises"][0]["sessions"] > 50
    assert demo["runs"]["count"] > 10 and demo["hikes"]["count"] > 10
    assert {h["kind"] for h in demo["highlights"]} <= {"win", "nudge", "info"}
    assert demo["highlights"]


def test_progress_and_prs(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    with store.transaction():
        gym(store, 1, "2026-06-01", "Bench Press (Barbell)\nSet 1: 95 lbs x 10 [Warm-up]\nSet 2: 135 lbs x 5\n")
        gym(store, 2, "2026-10-20", "Bench Press (Barbell)\nSet 1: 155 lbs x 5\nSet 2: 145 lbs x 8\n")
        gym(store, 3, "2026-11-10", "Bench Press (Barbell)\nSet 1: 150 lbs x 5\nPlank\nSet 1: 60s\n")
    data = analysis.build(store.conn, today=TODAY)
    bench = next(e for e in data["exercises"] if e["exercise"] == "Bench Press (Barbell)")
    assert bench["best_set"] == "145 lb x 8"  # 145x8 (e1RM 183.7) beats 155x5 (180.8)
    assert bench["change_pct"] > 0  # vs June
    prs = data["recent_prs"]
    assert [p["day"] for p in prs] == ["2026-10-20"]  # Nov 10 wasn't a PR; June is outside 30 days
    plank = next(e for e in data["exercises"] if e["exercise"] == "Plank")
    assert plank["best_duration_s"] == 60
    assert data["consistency"]["this_week"] == 1 and data["consistency"]["days_since_gym"] == 1


def test_streaks(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    days = ["2026-10-27", "2026-10-29", "2026-10-31", "2026-11-03", "2026-11-05", "2026-11-07", "2026-11-10"]
    with store.transaction():
        for i, d in enumerate(days):
            gym(store, i + 1, d, "Squat (Barbell)\nSet 1: 185 lbs x 5\n")
    c = analysis.build(store.conn, today=TODAY, weekly_target=3)["consistency"]
    assert c["current_streak_weeks"] == 2 and c["longest_streak_weeks"] == 2 and c["this_week"] == 1


def test_empty_database(tmp_path):
    data = analysis.build(Store(tmp_path / "db.sqlite").conn, today=TODAY)
    assert data["exercises"] == [] and data["runs"] == {"count": 0}


def test_metric_units(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    with store.transaction():
        store.upsert_summary({"id": 1, "name": "Run", "sport_type": "Run", "start_date": "2026-11-01T07:00:00Z",
                              "start_date_local": "2026-11-01T07:00:00Z", "distance": 10000, "moving_time": 3000})
    mi = analysis.build(store.conn, today=TODAY)["runs"]
    km = analysis.build(store.conn, today=TODAY, system="metric")["runs"]
    assert km["total_dist"] == 10.0 and mi["total_dist"] == 6.2
    assert km["runs"][0]["pace_s"] == 300  # 5:00 /km


def test_units_query_param(tmp_path):
    from stravadash.web import create_app
    db = tmp_path / "db.sqlite"
    populate(Store(db), today=TODAY)
    client = create_app(db, today=TODAY).test_client()
    assert client.get("/api/summary?units=metric").get_json()["units"]["distance"] == "km"
    assert client.get("/api/summary").get_json()["units"]["distance"] == "mi"
    assert client.get("/?units=metric").status_code == 200
