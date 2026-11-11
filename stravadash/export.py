"""Static export: one self-contained folder that any static host can serve."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import date
from pathlib import Path

from flask import Flask, render_template

from stravadash import analysis

PACKAGE = Path(__file__).parent


def export_site(db_path: Path, out: Path, public: bool = True, weekly_target: int = 3, today: date | None = None) -> Path:
    """Write index.html + static/ to `out`, with both unit systems and all exercise histories embedded."""
    payload: dict = {"static": True}
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        sets = analysis.load_sets(conn)
        weight_unit = analysis.detect_weight_unit(sets)
        for system in ("imperial", "metric"):
            data = analysis.build(conn, today=today, system=system, weekly_target=weekly_target)
            if public:
                data = analysis.redact(data)
            units = analysis.Units.for_system(system, weight_unit)
            data["histories"] = {name: analysis.exercise_history(sets, name, units) for name in sorted(set(sets["exercise"]))}
            payload[system] = data

    out.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__, template_folder=str(PACKAGE / "templates"))
    with app.app_context():
        html = render_template("index.html", data_json=json.dumps(payload, default=str, separators=(",", ":")))
    (out / "index.html").write_text(html)
    shutil.copytree(PACKAGE / "static", out / "static", dirs_exist_ok=True)
    (out / ".nojekyll").write_text("")
    return out / "index.html"
