from stravadash.client import DailyLimitReached
from stravadash.store import Store
from stravadash.sync import reparse, sync

GYM_DESC = "Leg Press (Machine)\nSet 1: 270 lbs x 12\nSet 2: 290 lbs x 10\n"


class FakeClient:
    def __init__(self, activities, details, fail_after=None):
        self.activities, self.details = activities, details
        self.detail_calls = 0
        self.fail_after = fail_after
        self.after_seen = []

    def list_activities(self, after=None):
        self.after_seen.append(after)
        yield from self.activities

    def get_activity(self, activity_id):
        if self.fail_after is not None and self.detail_calls >= self.fail_after:
            raise DailyLimitReached("limit")
        self.detail_calls += 1
        return self.details[activity_id]


def act(i, sport, date):
    return {"id": i, "name": f"a{i}", "sport_type": sport, "start_date": date,
            "start_date_local": date, "distance": 1000.0, "moving_time": 600}


def test_sync_fetches_details_only_for_gym(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    acts = [act(1, "Run", "2026-01-01T10:00:00Z"), act(2, "WeightTraining", "2026-01-02T10:00:00Z"),
            act(3, "Hike", "2026-01-03T10:00:00Z")]
    client = FakeClient(acts, {2: {**acts[1], "description": GYM_DESC}})
    stats = sync(store, client, log=lambda *_: None)
    assert stats == {"listed": 3, "details": 1, "sets": 2, "complete": True}
    assert client.detail_calls == 1
    assert store.gym_summary() == {"workouts": 1, "exercises": 1, "sets": 2}

    # second sync is incremental and doesn't refetch old gym sessions
    client2 = FakeClient([acts[2]], {})
    stats = sync(store, client2, log=lambda *_: None)
    assert client2.after_seen[0] is not None and stats["details"] == 0

    # a re-listed recent gym session is re-read so edited descriptions are picked up
    edited = {**acts[1], "description": GYM_DESC + "Set 3: 310 lbs x 8\n"}
    stats = sync(store, FakeClient([acts[1]], {2: edited}), log=lambda *_: None)
    assert stats["details"] == 1 and store.gym_summary()["sets"] == 3


def test_sync_resumes_after_daily_limit(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    acts = [act(i, "WeightTraining", f"2025-0{i}-01T10:00:00Z") for i in range(1, 4)]
    details = {a["id"]: {**a, "description": GYM_DESC} for a in acts}
    stats = sync(store, FakeClient(acts, details, fail_after=1), log=lambda *_: None)
    assert stats["complete"] is False and stats["details"] == 1
    assert store.get_meta("last_sync") is None
    stats = sync(store, FakeClient([], details), log=lambda *_: None)
    assert stats["details"] == 2 and stats["complete"]
    assert store.gym_summary()["workouts"] == 3


def test_reparse(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    a = act(9, "WeightTraining", "2026-02-01T10:00:00Z")
    with store.transaction():
        store.save_detail({**a, "description": GYM_DESC})
    assert reparse(store) == {"activities": 1, "sets": 2}
