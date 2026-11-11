import pytest

from stravadash.muscles import muscle_group


@pytest.mark.parametrize("name,group", [
    ("Triceps Rope Pushdown", "Triceps"), ("Lat Pulldown (Cable)", "Back"), ("Seated Row (Machine)", "Back"),
    ("Hammer Curl (Dumbbell)", "Biceps"), ("Bench Press (Dumbbell)", "Chest"), ("Seated Leg Curl (Machine)", "Hamstrings & glutes"),
    ("Leg Extension (Machine)", "Quads"), ("Hanging Leg Raise", "Core"), ("Single Arm Lateral Raise (Cable)", "Shoulders"),
    ("Cable Crunch", "Core"), ("Leg Press Horizontal (Machine)", "Quads"), ("Seated Calf Raise", "Calves"),
    ("Chest Press (Band)", "Chest"), ("Seated Palms Up Wrist Curl", "Forearms"), ("Cable Fly Crossovers", "Chest"),
    ("Pull Up", "Back"), ("Dumbbell Row", "Back"), ("Rack Pull", "Back"), ("Flutter Kicks", "Core"), ("Ab Wheel", "Core"),
    ("Arnold Press (Dumbbell)", "Shoulders"), ("Seated Cable Row - V Grip (Cable)", "Back"), ("Close Grip Bench Press", "Triceps"), ("Rope Cable Curl", "Biceps"), ("Calf Extension (Machine)", "Calves"),
])
def test_gb_exercises(name, group):
    assert muscle_group(name) == group
