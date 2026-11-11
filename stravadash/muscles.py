"""Map Hevy exercise names to a primary muscle group.

Hevy names look like "Bench Press (Barbell)" or "Lat Pulldown (Cable)".
The first matching rule wins, so more specific patterns come first.
"""

from __future__ import annotations

import re

RULES: list[tuple[str, str]] = [
    (r"farmer|carry|\bclean|snatch|thruster|burpee|kettlebell swing", "Full body"),
    (r"treadmill|bike|cycling|elliptical|rowing|row(er)? machine|stair|\brun|walk|jump rope|cardio|ski erg|assault", "Cardio"),
    (r"calf|calves", "Calves"),
    (r"romanian|rdl|stiff[ -]?leg|good morning|hip thrust|glute|leg curl|hamstring|nordic", "Hamstrings & glutes"),
    (r"squat|leg press|lunge|leg extension|step[ -]?up|hack|split squat|adductor|abductor|sled", "Quads"),
    (r"deadlift|rack pull|back extension|hyperextension", "Back"),
    (r"crunch|plank|ab |abs|\bab\b|sit[ -]?up|leg raise|knee raise|russian twist|wood ?chop|pallof|hollow|v[ -]?up|oblique|core|dead bug", "Core"),
    (r"shrug", "Traps"),
    (r"face pull|rear delt|reverse fly|reverse pec", "Shoulders"),
    (r"overhead press|shoulder press|military|arnold|lateral raise|front raise|upright row|landmine press|push press", "Shoulders"),
    (r"tricep|pushdown|push down|skull|close grip bench|dip|kickback|overhead extension|jm press", "Triceps"),
    (r"curl", "Biceps"),
    (r"row|pull[ -]?up|chin[ -]?up|pulldown|pull down|lat |pullover|t-bar|straight arm", "Back"),
    (r"bench|chest|fly|flye|pec|push[ -]?up|press up|crossover", "Chest"),
]
_COMPILED = [(re.compile(p, re.I), g) for p, g in RULES]
GROUPS = list(dict.fromkeys(g for _, g in RULES)) + ["Other"]


def muscle_group(exercise: str) -> str:
    name = exercise.lower()
    # "Seated Leg Curl" is legs, not biceps: leg-specific rules come before curls.
    for pattern, group in _COMPILED:
        if pattern.search(name + " "):
            return group
    return "Other"
