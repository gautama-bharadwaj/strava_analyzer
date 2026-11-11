"""Turn the SQLite store into the numbers the dashboard shows.

Everything here is a pure function of the data plus a `today` date, so it is
easy to test and could later be exported to static JSON for hosting.
Weights are reported in the unit you log in (detected from Hevy, lb by
default); distances follow `units` ("imperial" -> mi/ft, "metric" -> km/m).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from stravadash.muscles import muscle_group

KG_TO_LB = 2.2046226218
RUN_TYPES = {"Run", "TrailRun", "VirtualRun"}
HIKE_TYPES = {"Hike", "Walk"}
GYM_TYPES = {"WeightTraining", "Workout", "Crossfit", "HighIntensityIntervalTraining"}


@dataclass(frozen=True)
class Units:
    weight: str = "lb"
    distance: str = "mi"
    elevation: str = "ft"

    @classmethod
    def for_system(cls, system: str, weight: str = "lb") -> "Units":
        if system == "metric":
            return cls(weight=weight, distance="km", elevation="m")
        return cls(weight=weight, distance="mi", elevation="ft")

    def dist(self, meters):
        return meters / (1609.344 if self.distance == "mi" else 1000.0)

    def elev(self, meters):
        return meters * (3.28084 if self.elevation == "ft" else 1.0)

    def wt(self, kg):
        return kg * (KG_TO_LB if self.weight == "lb" else 1.0)


def epley_1rm(weight: float, reps: int) -> float:
    """Estimated one-rep max. Only meaningful for sets of roughly 1-12 reps."""
    if reps <= 0:
        return 0.0
    return weight if reps == 1 else weight * (1 + reps / 30)


# --- loading ---------------------------------------------------------------

def load_activities(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(
        "SELECT id, name, sport_type, start_date_local, distance_m, moving_time_s, elapsed_time_s, "
        "elevation_gain_m, average_speed_mps, average_heartrate FROM activities",
        conn,
    )
    df["date"] = pd.to_datetime(df["start_date_local"].str[:19], errors="coerce")
    df["day"] = df["date"].dt.date
    for c in ("distance_m", "moving_time_s", "elevation_gain_m"):
        df[c] = df[c].fillna(0)
    return df.sort_values("date").reset_index(drop=True)


def load_sets(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(
        "SELECT s.*, a.start_date_local, a.name AS workout FROM gym_sets s JOIN activities a ON a.id = s.activity_id",
        conn,
    )
    df["date"] = pd.to_datetime(df["start_date_local"].str[:19], errors="coerce")
    df["day"] = df["date"].dt.date
    df["muscle_group"] = df["exercise"].map(muscle_group)
    return df


def detect_weight_unit(sets: pd.DataFrame) -> str:
    units = sets["unit"].dropna()
    return "kg" if len(units) and (units == "kg").mean() > 0.5 else "lb"


# --- helpers -----------------------------------------------------------------

def _week_start(d) -> date:
    d = pd.Timestamp(d).date()
    return d - timedelta(days=d.weekday())


def _pct(new: float, old: float) -> float | None:
    if not old:
        return None
    return round(float((new - old) / old * 100), 1)


def _working_sets(sets: pd.DataFrame, units: Units) -> pd.DataFrame:
    """Non-warm-up sets with a positive load and reps, with weight/volume/e1RM in display units."""
    ws = sets[(sets["set_type"] != "warmup") & (sets["weight_kg"].fillna(0) > 0) & (sets["reps"].fillna(0) > 0)].copy()
    ws["w"] = units.wt(ws["weight_kg"]).round(1)
    ws["volume"] = ws["w"] * ws["reps"]
    capped = ws["reps"].clip(upper=12)
    ws["e1rm"] = [round(epley_1rm(w, r), 1) for w, r in zip(ws["w"], capped)]
    return ws


# --- gym ---------------------------------------------------------------------

def exercise_table(sets: pd.DataFrame, units: Units, today: date) -> list[dict]:
    """One row per exercise: sessions, bests, and progress over the last 90 days."""
    ws = _working_sets(sets, units)
    rows = []
    for name, g in ws.groupby("exercise"):
        per_session = g.groupby("day").agg(e1rm=("e1rm", "max"), top=("w", "max"), volume=("volume", "sum"))
        recent = per_session[per_session.index >= today - timedelta(days=90)]
        before = per_session[per_session.index < today - timedelta(days=90)]
        best_set = g.loc[g["e1rm"].idxmax()]
        rows.append({
            "exercise": name,
            "muscle_group": muscle_group(name),
            "sessions": int(sets.loc[sets["exercise"] == name, "day"].nunique()),
            "first": str(per_session.index.min()),
            "last": str(per_session.index.max()),
            "best_e1rm": float(per_session["e1rm"].max()),
            "best_weight": float(per_session["top"].max()),
            "best_set": f"{best_set['w']:g} {units.weight} x {int(best_set['reps'])}",
            "best_set_day": str(best_set["day"]),
            "recent_e1rm": float(recent["e1rm"].max()) if len(recent) else None,
            "change_pct": _pct(recent["e1rm"].max(), before["e1rm"].max()) if len(recent) and len(before) else None,
            "first_e1rm": float(per_session["e1rm"].iloc[0]),
            "all_time_change_pct": _pct(per_session["e1rm"].max(), per_session["e1rm"].iloc[0]),
        })
    rows.sort(key=lambda r: (-r["sessions"], r["exercise"]))
    # Bodyweight / timed exercises still count as sessions.
    weighted = {r["exercise"] for r in rows}
    for name, g in sets[~sets["exercise"].isin(weighted)].groupby("exercise"):
        rows.append({
            "exercise": name, "muscle_group": muscle_group(name), "sessions": int(g["day"].nunique()),
            "first": str(g["day"].min()), "last": str(g["day"].max()),
            "best_reps": int(g["reps"].max()) if g["reps"].notna().any() else None,
            "best_duration_s": int(g["duration_s"].max()) if g["duration_s"].notna().any() else None,
        })
    return rows


def exercise_history(sets: pd.DataFrame, exercise: str, units: Units) -> list[dict]:
    ws = _working_sets(sets[sets["exercise"] == exercise], units)
    if ws.empty:
        g = sets[sets["exercise"] == exercise]
        return [{"day": str(d), "reps": int(x["reps"].sum()) if x["reps"].notna().any() else None,
                 "duration_s": int(x["duration_s"].sum()) if x["duration_s"].notna().any() else None}
                for d, x in g.groupby("day")]
    out = []
    for d, x in ws.groupby("day"):
        top = x.loc[x["e1rm"].idxmax()]
        out.append({"day": str(d), "e1rm": float(x["e1rm"].max()), "top_weight": float(x["w"].max()),
                    "top_set": f"{top['w']:g} x {int(top['reps'])}", "volume": float(x["volume"].sum()),
                    "sets": int(len(x))})
    return out


def personal_records(sets: pd.DataFrame, units: Units, since: date) -> list[dict]:
    """Sessions since `since` where an exercise beat its previous best estimated 1RM."""
    ws = _working_sets(sets, units)
    prs = []
    for name, g in ws.groupby("exercise"):
        daily = g.groupby("day")["e1rm"].max().sort_index()
        prev_best = daily.cummax().shift(1)
        hits = daily[(daily > prev_best) & (daily.index >= since)]
        for d, v in hits.items():
            prs.append({"day": str(d), "exercise": name, "e1rm": float(v), "previous": float(prev_best[d]),
                        "gain_pct": _pct(v, prev_best[d])})
    return sorted(prs, key=lambda p: p["day"], reverse=True)


def weekly_gym(acts: pd.DataFrame, sets: pd.DataFrame, units: Units, weeks: int, today: date) -> dict:
    start = _week_start(today) - timedelta(weeks=weeks - 1)
    week_index = [start + timedelta(weeks=i) for i in range(weeks)]
    gym = acts[acts["sport_type"].isin(GYM_TYPES)].copy()
    gym["week"] = gym["day"].map(_week_start)
    sessions = gym.groupby("week").size().reindex(week_index, fill_value=0)

    ws = _working_sets(sets, units)
    ws["week"] = ws["day"].map(_week_start)
    ws = ws[ws["week"] >= start]
    vol = ws.pivot_table(index="week", columns="muscle_group", values="volume", aggfunc="sum").reindex(week_index).fillna(0)
    hard_sets = ws.pivot_table(index="week", columns="muscle_group", values="reps", aggfunc="count").reindex(week_index).fillna(0)
    return {
        "weeks": [str(w) for w in week_index],
        "sessions": [int(x) for x in sessions],
        "volume_by_group": {c: [round(float(v)) for v in vol[c]] for c in vol.columns},
        "sets_by_group": {c: [int(v) for v in hard_sets[c]] for c in hard_sets.columns},
    }


def consistency(acts: pd.DataFrame, today: date, weekly_target: int) -> dict:
    gym_days = sorted(set(acts.loc[acts["sport_type"].isin(GYM_TYPES), "day"]))
    active_days = set(acts["day"])
    weeks = pd.Series([_week_start(d) for d in gym_days]).value_counts() if gym_days else pd.Series(dtype=int)

    def streak(ok) -> tuple[int, int]:
        # current streak counts back from last week (this week is still in progress)
        cur, wk = 0, _week_start(today)
        if ok(wk):
            cur += 1
        wk -= timedelta(weeks=1)
        while ok(wk):
            cur += 1
            wk -= timedelta(weeks=1)
        longest = run = 0
        if gym_days:
            wk, end = _week_start(gym_days[0]), _week_start(today)
            while wk <= end:
                run = run + 1 if ok(wk) else 0
                longest = max(longest, run)
                wk += timedelta(weeks=1)
        return cur, longest

    cur, longest = streak(lambda w: weeks.get(w, 0) >= weekly_target)
    this_week = int(weeks.get(_week_start(today), 0))
    last_gym = gym_days[-1] if gym_days else None

    # Daily activity heatmap for the past year (any sport).
    year_ago = today - timedelta(days=364)
    heat = acts[acts["day"] >= year_ago].groupby("day").agg(n=("id", "count"), minutes=("moving_time_s", "sum"))
    return {
        "weekly_target": weekly_target,
        "this_week": this_week,
        "current_streak_weeks": cur,
        "longest_streak_weeks": longest,
        "days_since_gym": (today - last_gym).days if last_gym else None,
        "active_days_30": len([d for d in active_days if d > today - timedelta(days=30)]),
        "heatmap": {str(d): round(float(r["minutes"]) / 60) for d, r in heat.iterrows()},
    }


def days_since_by_group(sets: pd.DataFrame, today: date) -> dict:
    last = sets.groupby("muscle_group")["day"].max()
    return {g: (today - d).days for g, d in last.sort_values().items() if g not in {"Other", "Cardio"}}


# --- runs & hikes --------------------------------------------------------------

def run_stats(acts: pd.DataFrame, units: Units, today: date) -> dict:
    runs = acts[acts["sport_type"].isin(RUN_TYPES) & (acts["distance_m"] > 0)].copy()
    if runs.empty:
        return {"count": 0}
    runs["dist"] = units.dist(runs["distance_m"]).round(2)
    runs["pace_s"] = runs["moving_time_s"] / runs["dist"]  # seconds per mi/km
    runs["month"] = runs["date"].dt.to_period("M").astype(str)
    monthly = runs.groupby("month").agg(dist=("dist", "sum"), runs=("id", "count"), time=("moving_time_s", "sum"))
    monthly["pace_s"] = monthly["time"] / monthly["dist"]
    # Typical easy-ish runs: drop very short ones so pace trend isn't noise.
    min_dist = 1.0 if units.distance == "mi" else 1.6
    usable = runs[runs["dist"] >= min_dist]
    five_k = units.dist(5000)
    fastest_5k = usable[usable["dist"] >= five_k * 0.98].nsmallest(1, "pace_s")
    return {
        "count": int(len(runs)),
        "total_dist": round(float(runs["dist"].sum()), 1),
        "longest": {"dist": float(runs["dist"].max()), "day": str(runs.loc[runs["dist"].idxmax(), "day"])},
        "fastest_5k_plus": None if fastest_5k.empty else {
            "pace_s": float(fastest_5k["pace_s"].iloc[0]), "dist": float(fastest_5k["dist"].iloc[0]),
            "day": str(fastest_5k["day"].iloc[0])},
        "monthly": [{"month": m, "dist": round(float(r["dist"]), 1), "runs": int(r["runs"]),
                     "pace_s": round(float(r["pace_s"]))} for m, r in monthly.iterrows()],
        "runs": [{"day": str(r["day"]), "name": r["name"], "dist": float(r["dist"]), "pace_s": round(float(r["pace_s"])),
                  "hr": None if pd.isna(r["average_heartrate"]) else float(r["average_heartrate"])}
                 for _, r in usable.iterrows()],
    }


def hike_stats(acts: pd.DataFrame, units: Units) -> dict:
    hikes = acts[acts["sport_type"] == "Hike"].copy()
    if hikes.empty:
        return {"count": 0}
    hikes["dist"] = units.dist(hikes["distance_m"])
    hikes["elev"] = units.elev(hikes["elevation_gain_m"])
    hikes["year"] = hikes["date"].dt.year
    yearly = hikes.groupby("year").agg(hikes=("id", "count"), dist=("dist", "sum"), elev=("elev", "sum"),
                                       hours=("moving_time_s", lambda s: s.sum() / 3600))
    top = hikes.nlargest(5, "elev")
    return {
        "count": int(len(hikes)),
        "total_dist": round(float(hikes["dist"].sum()), 1),
        "total_elev": round(float(hikes["elev"].sum())),
        "yearly": [{"year": int(y), "hikes": int(r["hikes"]), "dist": round(float(r["dist"]), 1),
                    "elev": round(float(r["elev"])), "hours": round(float(r["hours"]), 1)} for y, r in yearly.iterrows()],
        "biggest": [{"day": str(r["day"]), "name": r["name"], "dist": round(float(r["dist"]), 1),
                     "elev": round(float(r["elev"]))} for _, r in top.iterrows()],
    }


# --- everything else ------------------------------------------------------------

SPORT_NAMES = {"Ride": "Cycling", "VirtualRide": "Indoor cycling", "EBikeRide": "E-bike", "MountainBikeRide": "Mountain biking",
               "AlpineSki": "Skiing", "BackcountrySki": "Backcountry skiing", "NordicSki": "Cross-country skiing",
               "StandUpPaddling": "Stand-up paddling", "Swim": "Swimming", "Walk": "Walking", "Rowing": "Rowing",
               "Kayaking": "Kayaking", "RockClimbing": "Climbing", "Snowboard": "Snowboarding", "Yoga": "Yoga"}
MAIN_TYPES = GYM_TYPES | RUN_TYPES | {"Hike"}


def sport_label(sport_type: str) -> str:
    import re
    return SPORT_NAMES.get(sport_type) or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", sport_type or "Other").capitalize()


def other_sports(acts: pd.DataFrame, units: Units) -> dict:
    """Per-sport breakdown for everything that isn't gym, running or hiking."""
    o = acts[~acts["sport_type"].isin(MAIN_TYPES)].copy()
    if o.empty:
        return {"count": 0, "sports": []}
    o["dist"] = units.dist(o["distance_m"])
    o["elev"] = units.elev(o["elevation_gain_m"])
    o["hours"] = o["moving_time_s"] / 3600
    o["year"] = o["date"].dt.year
    sports = []
    for sport, g in o.groupby("sport_type"):
        longest = g.loc[g["hours"].idxmax()]
        has_dist = bool((g["dist"] > 0.05).any())
        sports.append({
            "sport_type": sport,
            "label": sport_label(sport),
            "count": int(len(g)),
            "hours": round(float(g["hours"].sum()), 1),
            "dist": round(float(g["dist"].sum()), 1) if has_dist else None,
            "elev": round(float(g["elev"].sum())) if g["elev"].sum() > 0 else None,
            "first": str(g["day"].min()),
            "last": str(g["day"].max()),
            "longest": {"day": str(longest["day"]), "name": longest["name"], "hours": round(float(longest["hours"]), 1),
                        "dist": round(float(longest["dist"]), 1) if has_dist else None},
            "yearly": [{"year": int(y), "count": int(len(x)), "hours": round(float(x["hours"].sum()), 1),
                        "dist": round(float(x["dist"].sum()), 1) if has_dist else None}
                       for y, x in g.groupby("year")],
        })
    sports.sort(key=lambda x: (-x["count"], x["label"]))
    return {"count": int(len(o)), "hours": round(float(o["hours"].sum()), 1), "sports": sports}


# --- comparisons & highlights ------------------------------------------------------

def period_totals(acts: pd.DataFrame, sets: pd.DataFrame, units: Units, start: date, end: date) -> dict:
    a = acts[(acts["day"] >= start) & (acts["day"] <= end)]
    s = _working_sets(sets[(sets["day"] >= start) & (sets["day"] <= end)], units)
    return {
        "gym_sessions": int(a["sport_type"].isin(GYM_TYPES).sum()),
        "gym_volume": round(float(s["volume"].sum())),
        "gym_sets": int(len(s)),
        "run_dist": round(float(units.dist(a.loc[a["sport_type"].isin(RUN_TYPES), "distance_m"].sum())), 1),
        "hike_elev": round(float(units.elev(a.loc[a["sport_type"] == "Hike", "elevation_gain_m"].sum()))),
        "active_hours": round(float(a["moving_time_s"].sum()) / 3600, 1),
        "active_days": int(a["day"].nunique()),
    }


def comparisons(acts, sets, units, today: date) -> dict:
    """Month-to-date vs the same days last month, and year-to-date vs the same span last year."""
    mstart = today.replace(day=1)
    prev_mend = mstart - timedelta(days=1)
    prev_mstart = prev_mend.replace(day=1)
    prev_mcut = min(prev_mstart + (today - mstart), prev_mend)
    ystart = today.replace(month=1, day=1)
    try:
        prev_ycut = today.replace(year=today.year - 1)
    except ValueError:  # Feb 29
        prev_ycut = today.replace(year=today.year - 1, day=28)
    out = {}
    for key, cur, prev in (
        ("month", (mstart, today), (prev_mstart, prev_mcut)),
        ("year", (ystart, today), (ystart.replace(year=today.year - 1), prev_ycut)),
    ):
        c, p = period_totals(acts, sets, units, *cur), period_totals(acts, sets, units, *prev)
        out[key] = {"current": c, "previous": p, "change_pct": {k: _pct(c[k], p[k]) for k in c}}
    return out


def highlights(data: dict, units: Units) -> list[dict]:
    """Short, specific lines for the top of the dashboard. kind: win | nudge | info."""
    out: list[dict] = []
    c = data["consistency"]
    if c["this_week"] >= c["weekly_target"]:
        out.append({"kind": "win", "text": f"Weekly goal hit: {c['this_week']} gym sessions this week."})
    else:
        left = c["weekly_target"] - c["this_week"]
        out.append({"kind": "nudge", "text": f"{c['this_week']} of {c['weekly_target']} gym sessions this week. {left} to go."})
    if c["current_streak_weeks"] >= 2:
        out.append({"kind": "win", "text": f"{c['current_streak_weeks']}-week streak of hitting your target (best: {c['longest_streak_weeks']})."})
    if c["days_since_gym"] is not None and c["days_since_gym"] >= 4:
        out.append({"kind": "nudge", "text": f"{c['days_since_gym']} days since your last gym session."})
    for g, days in data["days_since_group"].items():
        if 10 <= days <= 60:
            out.append({"kind": "nudge", "text": f"{days} days since you trained {g.lower()}."})
            break
    for pr in data["recent_prs"][:3]:
        out.append({"kind": "win", "text": f"New PR on {pr['exercise']}: estimated 1RM {pr['e1rm']:g} {units.weight} (+{pr['gain_pct']:g}%) on {pr['day']}."})
    ytd = data["compare"]["year"]
    for key, label in (("gym_sessions", "gym sessions"), ("run_dist", f"{units.distance} run"), ("hike_elev", f"{units.elevation} climbed")):
        cur, chg = ytd["current"][key], ytd["change_pct"][key]
        if cur and chg is not None and chg > 0:
            out.append({"kind": "win", "text": f"{cur:,.0f} {label} this year, up {chg:g}% on where you were this time last year."})
    improving = [e for e in data["exercises"] if e.get("change_pct") and e["change_pct"] > 0]
    improving.sort(key=lambda e: -e["change_pct"])
    if improving:
        e = improving[0]
        out.append({"kind": "win", "text": f"Biggest 90-day gain: {e['exercise']} est. 1RM up {e['change_pct']:g}%."})
    return out


def build(conn: sqlite3.Connection, today: date | None = None, system: str = "imperial",
          weekly_target: int = 3, weeks: int = 26) -> dict:
    today = today or date.today()
    acts = load_activities(conn)
    sets = load_sets(conn)
    units = Units.for_system(system, detect_weight_unit(sets))
    data = {
        "today": str(today),
        "units": units.__dict__,
        "totals": {
            "activities": int(len(acts)),
            "by_sport": {k: int(v) for k, v in acts["sport_type"].value_counts().items()},
            "first_day": str(acts["day"].min()) if len(acts) else None,
        },
        "consistency": consistency(acts, today, weekly_target),
        "weekly": weekly_gym(acts, sets, units, weeks, today),
        "exercises": exercise_table(sets, units, today),
        "recent_prs": personal_records(sets, units, today - timedelta(days=30)),
        "days_since_group": days_since_by_group(sets, today) if len(sets) else {},
        "runs": run_stats(acts, units, today),
        "hikes": hike_stats(acts, units),
        "other": other_sports(acts, units),
        "compare": comparisons(acts, sets, units, today),
    }
    data["highlights"] = highlights(data, units)
    return data
