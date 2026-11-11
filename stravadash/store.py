"""SQLite storage for activities and parsed gym sets."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from stravadash.hevy_parser import ParsedExercise

SCHEMA = """
CREATE TABLE IF NOT EXISTS activities (
    id                   INTEGER PRIMARY KEY,
    name                 TEXT,
    sport_type           TEXT,
    start_date           TEXT,     -- UTC ISO-8601
    start_date_local     TEXT,     -- athlete's local time, ISO-8601
    distance_m           REAL,
    moving_time_s        INTEGER,
    elapsed_time_s       INTEGER,
    elevation_gain_m     REAL,
    average_speed_mps    REAL,
    max_speed_mps        REAL,
    average_heartrate    REAL,
    max_heartrate        REAL,
    kilojoules           REAL,
    calories             REAL,
    description          TEXT,
    detail_fetched       INTEGER NOT NULL DEFAULT 0,
    summary_json         TEXT
);
CREATE INDEX IF NOT EXISTS idx_activities_start ON activities(start_date);
CREATE INDEX IF NOT EXISTS idx_activities_sport ON activities(sport_type);

CREATE TABLE IF NOT EXISTS gym_sets (
    activity_id     INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    exercise_index  INTEGER NOT NULL,
    exercise        TEXT NOT NULL,
    set_index       INTEGER NOT NULL,
    set_type        TEXT NOT NULL,
    reps            INTEGER,
    weight          REAL,
    unit            TEXT,
    weight_kg       REAL,
    duration_s      INTEGER,
    distance_m      REAL,
    rpe             REAL,
    raw             TEXT,
    PRIMARY KEY (activity_id, exercise_index, set_index)
);
CREATE INDEX IF NOT EXISTS idx_gym_sets_exercise ON gym_sets(exercise);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

SUMMARY_FIELDS = {
    "name": "name",
    "sport_type": "sport_type",
    "start_date": "start_date",
    "start_date_local": "start_date_local",
    "distance": "distance_m",
    "moving_time": "moving_time_s",
    "elapsed_time": "elapsed_time_s",
    "total_elevation_gain": "elevation_gain_m",
    "average_speed": "average_speed_mps",
    "max_speed": "max_speed_mps",
    "average_heartrate": "average_heartrate",
    "max_heartrate": "max_heartrate",
    "kilojoules": "kilojoules",
}


class Store:
    def __init__(self, path: Path | str):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def transaction(self):
        with self.conn:
            yield self.conn

    # --- activities -----------------------------------------------------
    def upsert_summary(self, a: dict) -> None:
        cols = ["id", *SUMMARY_FIELDS.values(), "summary_json"]
        vals = [a["id"], *(a.get(k) for k in SUMMARY_FIELDS), json.dumps(a)]
        if vals[cols.index("sport_type")] is None:
            vals[cols.index("sport_type")] = a.get("type")
        updates = ", ".join(f"{c}=excluded.{c}" for c in cols[1:])
        self.conn.execute(
            f"INSERT INTO activities ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            vals,
        )

    def save_detail(self, detail: dict) -> None:
        self.upsert_summary(detail)
        self.conn.execute(
            "UPDATE activities SET description=?, calories=?, detail_fetched=1 WHERE id=?",
            (detail.get("description"), detail.get("calories"), detail["id"]),
        )

    def latest_start_epoch(self) -> int | None:
        row = self.conn.execute("SELECT MAX(start_date) FROM activities").fetchone()
        if not row or not row[0]:
            return None
        return int(datetime.fromisoformat(row[0].replace("Z", "+00:00")).timestamp())

    def ids_needing_detail(self, sport_types: set[str]) -> list[int]:
        q = ",".join("?" * len(sport_types))
        rows = self.conn.execute(
            f"SELECT id FROM activities WHERE detail_fetched=0 AND sport_type IN ({q}) ORDER BY start_date DESC",
            sorted(sport_types),
        )
        return [r[0] for r in rows]

    def activities_with_description(self):
        return self.conn.execute(
            "SELECT id, description FROM activities WHERE description IS NOT NULL AND description != ''"
        ).fetchall()

    # --- gym sets -------------------------------------------------------
    def replace_gym_sets(self, activity_id: int, exercises: list[ParsedExercise]) -> int:
        self.conn.execute("DELETE FROM gym_sets WHERE activity_id=?", (activity_id,))
        rows = [
            (activity_id, ei, ex.name, si, s.set_type, s.reps, s.weight, s.unit,
             s.weight_kg, s.duration_s, s.distance_m, s.rpe, s.raw)
            for ei, ex in enumerate(exercises)
            for si, s in enumerate(ex.sets)
        ]
        self.conn.executemany(
            "INSERT INTO gym_sets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
        )
        return len(rows)

    # --- meta -----------------------------------------------------------
    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    # --- reporting ------------------------------------------------------
    def counts_by_sport(self) -> list[tuple[str, int]]:
        return [tuple(r) for r in self.conn.execute(
            "SELECT sport_type, COUNT(*) FROM activities GROUP BY sport_type ORDER BY 2 DESC"
        )]

    def gym_summary(self) -> dict:
        r = self.conn.execute(
            "SELECT COUNT(DISTINCT activity_id), COUNT(DISTINCT exercise), COUNT(*) FROM gym_sets"
        ).fetchone()
        return {"workouts": r[0], "exercises": r[1], "sets": r[2]}
