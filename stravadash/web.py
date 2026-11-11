"""Local web dashboard: `stravadash serve`."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from flask import Flask, abort, jsonify, render_template

from stravadash import analysis


def create_app(db_path: Path, units: str = "imperial", weekly_target: int = 3, today: date | None = None) -> Flask:
    app = Flask(__name__)

    def connect():
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    def build():
        with connect() as conn:
            return analysis.build(conn, today=today, system=units, weekly_target=weekly_target)

    @app.get("/")
    def index():
        data = build()
        return render_template("index.html", data=data, data_json=json.dumps(data, default=str))

    @app.get("/api/summary")
    def summary():
        return jsonify(build())

    @app.get("/api/exercise/<path:name>")
    def exercise(name: str):
        with connect() as conn:
            sets = analysis.load_sets(conn)
            unit = analysis.detect_weight_unit(sets)
        if name not in set(sets["exercise"]):
            abort(404)
        u = analysis.Units.for_system(units, unit)
        return jsonify({"exercise": name, "unit": u.weight, "history": analysis.exercise_history(sets, name, u)})

    return app
