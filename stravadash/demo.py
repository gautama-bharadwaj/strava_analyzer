"""Generate a realistic fake history so the dashboard can be tried without Strava."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from stravadash.hevy_parser import parse_description
from stravadash.store import Store

ROUTINES = {
    "Push": [("Bench Press (Barbell)", 135, 8), ("Incline Bench Press (Dumbbell)", 50, 10),
             ("Shoulder Press (Dumbbell)", 40, 10), ("Lateral Raise (Dumbbell)", 20, 14),
             ("Triceps Pushdown (Cable)", 50, 12)],
    "Pull": [("Lat Pulldown (Cable)", 120, 10), ("Seated Cable Row - V Grip (Cable)", 110, 10),
             ("Pull Up", 0, 6), ("Face Pull", 40, 15), ("Bicep Curl (Dumbbell)", 25, 12)],
    "Legs": [("Squat (Barbell)", 155, 6), ("Romanian Deadlift (Barbell)", 135, 8),
             ("Leg Press (Machine)", 250, 10), ("Seated Leg Curl (Machine)", 90, 12),
             ("Calf Raise (Machine)", 120, 15), ("Plank", 0, 0)],
}


def _description(routine: str, progress: float, rng: random.Random) -> str:
    lines = []
    for name, base, reps in ROUTINES[routine]:
        lines.append(name)
        if name == "Plank":
            lines.append(f"Set 1: {rng.choice([45, 60, 75, 90])}s")
        elif base == 0:
            for i in range(3):
                lines.append(f"Set {i + 1}: {max(1, int(reps + progress * 6) - i + rng.randint(-1, 1))} reps")
        else:
            work = round(base * (1 + 0.35 * progress) / 5) * 5
            lines.append(f"Set 1: {round(work * 0.6 / 5) * 5} lbs x 10 [Warm-up]")
            for i in range(3):
                tag = " [Failure]" if i == 2 and rng.random() < 0.2 else ""
                lines.append(f"Set {i + 2}: {work} lbs x {max(1, reps - i + rng.randint(-1, 1))}{tag}")
        lines.append("")
    return "\n".join(lines)


def populate(store: Store, today: date | None = None, seed: int = 7) -> int:
    rng = random.Random(seed)
    today = today or date.today()
    start = today - timedelta(days=3 * 365)
    aid, n, gym_count = 1, 0, 0
    order = ["Push", "Pull", "Legs"]
    d = start
    with store.transaction():
        while d <= today:
            progress = (d - start).days / (today - start).days
            busy = 0.25 + 0.45 * progress  # trains more often over time
            if rng.random() < busy * 0.6:
                routine = order[gym_count % 3]
                gym_count += 1
                desc = _description(routine, progress + rng.uniform(-0.03, 0.03), rng)
                when = datetime.combine(d, datetime.min.time()).replace(hour=18)
                act = {"id": aid, "name": f"{routine} day", "sport_type": "WeightTraining",
                       "start_date": when.isoformat() + "Z", "start_date_local": when.isoformat() + "Z",
                       "distance": 0, "moving_time": rng.randint(3000, 4500), "elapsed_time": 4800,
                       "total_elevation_gain": 0, "description": desc}
                store.save_detail(act)
                store.replace_gym_sets(aid, parse_description(desc))
                aid += 1
                n += 1
            if d >= today - timedelta(days=330) and rng.random() < 0.18:
                km = rng.choice([3, 5, 5, 6, 8, 10]) * rng.uniform(0.95, 1.1)
                pace = (6.4 - 0.9 * progress + rng.uniform(-0.2, 0.2)) * 60  # sec/km
                when = datetime.combine(d, datetime.min.time()).replace(hour=7)
                store.upsert_summary({"id": aid, "name": "Morning Run", "sport_type": "Run",
                                      "start_date": when.isoformat() + "Z", "start_date_local": when.isoformat() + "Z",
                                      "distance": km * 1000, "moving_time": int(km * pace), "elapsed_time": int(km * pace) + 60,
                                      "total_elevation_gain": rng.uniform(10, 80), "average_speed": 1000 / pace,
                                      "average_heartrate": 162 - 10 * progress + rng.uniform(-5, 5),
                                      "max_heartrate": 182 - 6 * progress + rng.uniform(-4, 4)})
                aid += 1
                n += 1
            if d.weekday() >= 5 and rng.random() < 0.3:
                km = rng.uniform(6, 22)
                when = datetime.combine(d, datetime.min.time()).replace(hour=9)
                store.upsert_summary({"id": aid, "name": rng.choice(["Mission Peak", "Mt Tam loop", "Ridge trail", "Canyon hike"]),
                                      "sport_type": "Hike", "start_date": when.isoformat() + "Z",
                                      "start_date_local": when.isoformat() + "Z", "distance": km * 1000,
                                      "moving_time": int(km * 900), "elapsed_time": int(km * 1100),
                                      "total_elevation_gain": km * rng.uniform(40, 110),
                                      "average_heartrate": rng.uniform(118, 138), "max_heartrate": rng.uniform(150, 170)})
                aid += 1
                n += 1
            if rng.random() < 0.06:
                sport, name, km, mins, climb = rng.choice([
                    ("Ride", "Bay trail ride", rng.uniform(20, 60), rng.randint(60, 180), rng.uniform(100, 700)),
                    ("Tennis", "Tennis", 0, rng.randint(60, 120), 0),
                    ("Swim", "Pool swim", rng.uniform(1, 2), rng.randint(30, 50), 0),
                    ("AlpineSki", "Tahoe", rng.uniform(20, 40), rng.randint(180, 300), 0),
                    ("StandUpPaddling", "SUP", rng.uniform(3, 8), rng.randint(45, 90), 0),
                ])
                when = datetime.combine(d, datetime.min.time()).replace(hour=11)
                store.upsert_summary({"id": aid, "name": name, "sport_type": sport, "start_date": when.isoformat() + "Z",
                                      "start_date_local": when.isoformat() + "Z", "distance": km * 1000,
                                      "moving_time": mins * 60, "elapsed_time": mins * 66, "total_elevation_gain": climb})
                aid += 1
                n += 1
            d += timedelta(days=1)
    return n
