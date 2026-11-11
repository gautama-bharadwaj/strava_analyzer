import json
import re
from datetime import date

from stravadash import auth
from stravadash.config import Settings
from stravadash.demo import populate
from stravadash.export import export_site
from stravadash.store import Store

TODAY = date(2026, 11, 11)


def test_export_is_static_and_public(tmp_path):
    db = tmp_path / "db.sqlite"
    populate(Store(db), today=TODAY)
    index = export_site(db, tmp_path / "site", public=True, today=TODAY)
    html = index.read_text()
    payload = json.loads(re.search(r"const DATA = (\{.*?\});\n", html, re.S).group(1))
    assert payload["static"] and payload["imperial"]["units"]["distance"] == "mi"
    assert payload["metric"]["units"]["distance"] == "km"
    assert payload["imperial"]["histories"]["Bench Press (Barbell)"]
    assert "Mission Peak" not in html and "/static/" not in html
    assert (tmp_path / "site" / "static" / "chart.umd.js").exists()
    assert (tmp_path / "site" / ".nojekyll").exists()


def test_location_fields_never_stored(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    with store.transaction():
        store.upsert_summary({"id": 1, "name": "Run", "sport_type": "Run", "start_date": "2026-11-01T07:00:00Z",
                              "start_date_local": "2026-11-01T07:00:00Z", "start_latlng": [37.5, -122.0],
                              "map": {"summary_polyline": "abc"}})
    raw = store.conn.execute("SELECT summary_json FROM activities").fetchone()[0]
    assert "latlng" not in raw and "polyline" not in raw


def test_existing_rows_are_scrubbed(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    with store.transaction():
        store.conn.execute("INSERT INTO activities (id, summary_json) VALUES (1, ?)",
                           (json.dumps({"id": 1, "map": {"summary_polyline": "abc"}, "end_latlng": [1, 2]}),))
    store.close()
    raw = Store(tmp_path / "db.sqlite").conn.execute("SELECT summary_json FROM activities").fetchone()[0]
    assert json.loads(raw) == {"id": 1}


def test_refresh_token_from_env(tmp_path, monkeypatch):
    settings = Settings(client_id="1", client_secret="s", data_dir=tmp_path, auth_port=0)
    calls = {}

    def fake_exchange(s, **data):
        calls.update(data)
        return {"access_token": "new"}

    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "rt")
    monkeypatch.setattr(auth, "_exchange", fake_exchange)
    assert auth.get_access_token(settings) == "new"
    assert calls == {"grant_type": "refresh_token", "refresh_token": "rt"}
