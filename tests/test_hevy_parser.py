import pytest

from stravadash.hevy_parser import parse_description, parse_duration, parse_set_line

HEVY = """Push day, felt strong today

Bench Press (Barbell)
Set 1: 95 lbs x 10 [Warm-up]
Set 2: 135 lbs x 8
Set 3: 155.5 lbs x 6 [Failure]
Set 4: 115 lbs x 10 [Drop]

Weighted Dips
Set 1: +25 lbs x 8 @ RPE 8

Pull Up (Assisted)
Set 1: -40 lbs x 10

Push Up
Set 1: 15 reps

Plank
Set 1: 1min 30s

Farmers Walk (Dumbbell)
Set 1: 60 kg x 0:45

Treadmill
Set 1: 1.5 km - 10:05

Logged with Hevy
https://hevy.com/workout/abc
"""


def test_full_workout():
    exercises = parse_description(HEVY)
    assert [e.name for e in exercises] == [
        "Bench Press (Barbell)", "Weighted Dips", "Pull Up (Assisted)",
        "Push Up", "Plank", "Farmers Walk (Dumbbell)", "Treadmill",
    ]
    bench = exercises[0].sets
    assert [s.set_type for s in bench] == ["warmup", "normal", "failure", "drop"]
    assert bench[2].weight == 155.5 and bench[2].unit == "lb" and bench[2].reps == 6
    assert bench[2].weight_kg == pytest.approx(70.534, abs=0.01)


def test_signed_bodyweight_and_rpe():
    dips = parse_set_line("Set 1: +25 lbs x 8 @ RPE 8")
    assert (dips.weight, dips.reps, dips.rpe) == (25, 8, 8)
    assisted = parse_set_line("Set 1: -40 lbs x 10")
    assert assisted.weight == -40 and assisted.weight_kg < 0


def test_kg_and_reps_only():
    s = parse_set_line("Set 2: 80 kg x 5")
    assert (s.weight, s.unit, s.weight_kg, s.reps) == (80, "kg", 80, 5)
    s = parse_set_line("Set 1: 15 reps")
    assert s.reps == 15 and s.weight is None


def test_legacy_reps_x_weight():
    s = parse_set_line("Set 1: 10 x 135")
    assert (s.reps, s.weight, s.unit) == (10, 135, "lb")


def test_timed_and_distance():
    assert parse_set_line("Set 1: 1min 30s").duration_s == 90
    farmers = parse_set_line("Set 1: 60 kg x 0:45")
    assert farmers.duration_s == 45 and farmers.weight_kg == 60
    tread = parse_set_line("Set 1: 1.5 km - 10:05")
    assert tread.distance_m == 1500 and tread.duration_s == 605


@pytest.mark.parametrize("text,seconds", [
    ("45s", 45), ("1:30", 90), ("1:02:03", 3723), ("2 min", 120), ("1h 5min", 3900), ("30 sec", 30),
])
def test_durations(text, seconds):
    assert parse_duration(text) == seconds


def test_any_title_and_notes_are_not_exercises():
    # Old code only matched three hardcoded workout titles; titles no longer matter,
    # and note lines without sets are dropped.
    desc = "Random note\nAnother note\nSquat (Barbell)\nSet 1: 225 lbs x 5\n"
    ex = parse_description(desc)
    assert len(ex) == 1 and ex[0].name == "Squat (Barbell)"


def test_numbered_exercise_names_and_empty():
    ex = parse_description("1. Deadlift (Barbell)\nSet 1: 315 lbs x 3")
    assert ex[0].name == "Deadlift (Barbell)"
    assert parse_description(None) == []
    assert parse_description("Morning walk with the dog") == []


def test_unknown_set_lines_are_skipped():
    assert parse_set_line("Set 1: something odd") is None
    assert parse_set_line("Settings changed") is None
