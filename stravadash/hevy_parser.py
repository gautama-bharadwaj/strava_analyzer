"""Parse the workout text Hevy posts into a Strava activity description.

Hevy writes one block per exercise, roughly:

    Bench Press (Barbell)
    Set 1: 135 lbs x 10
    Set 2: 155 lbs x 8 [Failure]
    Set 3: 95 lbs x 12 [Drop]

    Plank
    Set 1: 1min 30s

The parser is deliberately forgiving: weights may be decimals in lbs or kg,
weighted/assisted bodyweight sets use +/-, timed and distance sets are
supported, and anything it doesn't understand is skipped rather than fatal.
Every workout is parsed regardless of its title.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

LB_TO_KG = 0.45359237

_NUM = r"\d+(?:[.,]\d+)?"
_UNIT = r"(?:kg|kgs|lb|lbs)"

SET_PREFIX = re.compile(
    r"^\s*(?:set\s*(?P<label>[\w-]+)|(?P<warm>warm[\s-]?up(?:\s*set)?)|(?P<drop>drop\s*set))\s*[:.)-]\s*(?P<body>.*)$",
    re.IGNORECASE,
)
TAG = re.compile(r"\[(?P<tag>[^\]]+)\]|\((?P<ptag>warm[\s-]?up|drop|failure|dropset)\)", re.IGNORECASE)
RPE = re.compile(r"@?\s*rpe\s*(?P<rpe>\d+(?:\.\d+)?)|@\s*(?P<rpe2>\d+(?:\.\d+)?)\s*rpe", re.IGNORECASE)
WEIGHT_REPS = re.compile(rf"^(?P<sign>[+-])?\s*(?P<w>{_NUM})\s*(?P<u>{_UNIT})\s*[x×*]\s*(?P<r>\d+)(?![\d:.])(?:\s*reps?)?\b", re.I)
REPS_WEIGHT = re.compile(rf"^(?P<r>\d+)\s*(?:reps?)?\s*[x×*]\s*(?P<sign>[+-])?\s*(?P<w>{_NUM})\s*(?P<u>{_UNIT})?\b", re.I)
WEIGHT_TIME = re.compile(rf"^(?P<sign>[+-])?\s*(?P<w>{_NUM})\s*(?P<u>{_UNIT})\s*[x×*]\s*(?P<t>.+)$", re.I)
REPS_ONLY = re.compile(r"^(?P<r>\d+)\s*reps?\b", re.I)
DISTANCE = re.compile(rf"^(?P<d>{_NUM})\s*(?P<u>km|mi|miles?|m|meters?|yd|yards?)\b(?:\s*(?:in|[x×@,-])\s*(?P<t>.+))?$", re.I)
CLOCK = re.compile(r"^(?:(?P<h>\d+):)?(?P<m>\d{1,2}):(?P<s>\d{2})$")
UNITS_TIME = re.compile(
    r"^(?:(?P<h>\d+)\s*h(?:rs?|ours?)?)?\s*(?:(?P<m>\d+)\s*m(?:in(?:ute)?s?)?)?\s*(?:(?P<s>\d+)\s*s(?:ec(?:ond)?s?)?)?$",
    re.I,
)
NOISE = re.compile(r"(https?://|www\.|hevy\.?app|logged with hevy|^#|^-{3,}$|^total volume|^volume:)", re.I)

DIST_TO_M = {"km": 1000.0, "mi": 1609.344, "mile": 1609.344, "miles": 1609.344, "m": 1.0,
             "meter": 1.0, "meters": 1.0, "yd": 0.9144, "yard": 0.9144, "yards": 0.9144}


@dataclass
class ParsedSet:
    set_type: str = "normal"  # normal | warmup | drop | failure
    reps: int | None = None
    weight: float | None = None  # as written, signed (+ added / - assisted)
    unit: str | None = None  # "lb" or "kg"
    weight_kg: float | None = None
    duration_s: int | None = None
    distance_m: float | None = None
    rpe: float | None = None
    raw: str = ""


@dataclass
class ParsedExercise:
    name: str
    sets: list[ParsedSet] = field(default_factory=list)


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def parse_duration(text: str) -> int | None:
    text = text.strip().lower().rstrip(".")
    if not text:
        return None
    if m := CLOCK.match(text):
        return int(m["h"] or 0) * 3600 + int(m["m"]) * 60 + int(m["s"])
    if (m := UNITS_TIME.match(text)) and any(m.group(g) for g in ("h", "m", "s")):
        return int(m["h"] or 0) * 3600 + int(m["m"] or 0) * 60 + int(m["s"] or 0)
    return None


def _apply_weight(ps: ParsedSet, sign: str | None, w: str, unit: str | None) -> None:
    value = _num(w) * (-1 if sign == "-" else 1)
    ps.weight = value
    if unit:
        ps.unit = "kg" if unit.lower().startswith("kg") else "lb"
        ps.weight_kg = round(value * (LB_TO_KG if ps.unit == "lb" else 1.0), 3)


def parse_set_line(line: str) -> ParsedSet | None:
    """Return a ParsedSet if `line` is a set line, else None."""
    m = SET_PREFIX.match(line)
    if not m:
        return None
    ps = ParsedSet(raw=line.strip())
    label = (m["label"] or "").lower()
    if m["warm"] or label in {"w", "wu", "warmup", "warm-up"}:
        ps.set_type = "warmup"
    elif m["drop"] or label in {"d", "drop"}:
        ps.set_type = "drop"
    elif label == "f":
        ps.set_type = "failure"

    body = m["body"]
    for t in TAG.finditer(body):
        tag = (t["tag"] or t["ptag"]).lower().replace(" ", "").replace("-", "")
        if tag.startswith("warm"):
            ps.set_type = "warmup"
        elif tag.startswith("drop"):
            ps.set_type = "drop"
        elif tag.startswith("fail"):
            ps.set_type = "failure"
    body = TAG.sub("", body)
    if r := RPE.search(body):
        ps.rpe = float(r["rpe"] or r["rpe2"])
        body = RPE.sub("", body)
    body = body.strip(" ,;")

    if m2 := WEIGHT_REPS.match(body):
        _apply_weight(ps, m2["sign"], m2["w"], m2["u"])
        ps.reps = int(m2["r"])
    elif (m2 := WEIGHT_TIME.match(body)) and parse_duration(m2["t"]) is not None:
        _apply_weight(ps, m2["sign"], m2["w"], m2["u"])
        ps.duration_s = parse_duration(m2["t"])
    elif m2 := REPS_WEIGHT.match(body):
        ps.reps = int(m2["r"])
        _apply_weight(ps, m2["sign"], m2["w"], m2["u"] or "lb")
    elif m2 := REPS_ONLY.match(body):
        ps.reps = int(m2["r"])
    elif m2 := DISTANCE.match(body):
        ps.distance_m = round(_num(m2["d"]) * DIST_TO_M[m2["u"].lower()], 2)
        if m2["t"]:
            ps.duration_s = parse_duration(m2["t"])
    elif (d := parse_duration(body)) is not None:
        ps.duration_s = d
    elif body.isdigit():
        ps.reps = int(body)
    else:
        return None
    return ps


def parse_description(description: str | None) -> list[ParsedExercise]:
    """Split a Hevy description into exercises with their sets.

    The exercise name is the last non-set line before a run of set lines,
    which skips any free-text workout notes at the top.
    """
    exercises: list[ParsedExercise] = []
    candidate: str | None = None
    current: ParsedExercise | None = None

    for raw in (description or "").splitlines():
        line = raw.strip()
        if not line:
            current = None
            continue
        ps = parse_set_line(line)
        if ps:
            if current is None:
                if candidate is None:
                    continue  # set with no exercise name: ignore
                current = ParsedExercise(name=candidate)
                exercises.append(current)
                candidate = None
            current.sets.append(ps)
            continue
        if NOISE.search(line):
            continue
        current = None
        candidate = _clean_name(line)
    return [e for e in exercises if e.sets]


def _clean_name(line: str) -> str:
    line = re.sub(r"^\s*(?:\d+[.)]\s+|[-•*]\s+)", "", line)  # "1. Squat" / "- Squat"
    return re.sub(r"\s+", " ", line).strip().rstrip(":")


def looks_like_hevy(description: str | None) -> bool:
    return any(parse_set_line(l) for l in (description or "").splitlines())
