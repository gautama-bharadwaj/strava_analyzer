import re
import pandas as pd
import matplotlib.pyplot as plt
from strava_auth_manager import get_access_token
from strava_rate_limiter import rate_limiter
import requests
import json
import os
from datetime import datetime

TARGET_TITLES = [
    "1. Chest Shoulders and Triceps",
    "2. Back and Biceps",
    "3. Legs and Abs"
]

ACTIVITIES_FILE = "strava_activities.json"
GYM_DATA_FILE = "gym_workout_data.csv"

def fetch_all_activities():
    """Fetch all activities from Strava and store locally"""
    access_token = get_access_token()
    headers = {'Authorization': f"Bearer {access_token}"}
    activities = []
    page = 1

    print("Fetching all activities from Strava...")
    print("📊 Checking rate limits before starting...")
    rate_limiter.print_status()

    while True:
        print(f"Fetching page {page}...")

        # Wait if needed before making request
        rate_limiter.wait_if_needed(is_read_request=True, verbose=True)

        response = requests.get(
            f'https://www.strava.com/api/v3/athlete/activities?page={page}&per_page=50',
            headers=headers
        )

        if response.status_code != 200:
            print(f"Error fetching activities: {response.status_code}")
            if response.status_code == 429:  # Rate limit exceeded
                print("⚠️  Rate limit exceeded by Strava. Waiting longer...")
                rate_limiter.print_status()
            break

        data = response.json()
        if not data:
            break
        activities.extend(data)
        page += 1

        # Show progress every 5 pages
        if page % 5 == 0:
            rate_limiter.print_status()

    print(f"Total activities fetched: {len(activities)}")
    print("📊 Final rate limit status:")
    rate_limiter.print_status()

    # Store all activities locally
    with open(ACTIVITIES_FILE, 'w') as f:
        json.dump(activities, f, indent=2)

    print(f"Activities saved to {ACTIVITIES_FILE}")
    return activities

def load_activities():
    """Load activities from local file"""
    if os.path.exists(ACTIVITIES_FILE):
        with open(ACTIVITIES_FILE, 'r') as f:
            return json.load(f)
    return None

def fetch_gym_activities():
    """Get gym activities with detailed descriptions"""
    # Try to load from local file first
    activities = load_activities()

    if activities is None:
        print("No local activities found. Fetching from Strava...")
        activities = fetch_all_activities()
    else:
        print(f"Loaded {len(activities)} activities from local file")

    access_token = get_access_token()
    headers = {'Authorization': f"Bearer {access_token}"}

    # Filter for gym activities
    gym_activities = []
    for activity in activities:
        if any(target in activity['name'] for target in TARGET_TITLES):
            gym_activities.append(activity)

    print(f"Found {len(gym_activities)} gym activities")

    # Fetch detailed information for each gym activity to get descriptions
    detailed_activities = []
    total_gym_activities = len(gym_activities)

    print(f"📊 Rate limit status before fetching details:")
    rate_limiter.print_status()

    for i, activity in enumerate(gym_activities, 1):
        activity_id = activity['id']
        print(f"Fetching details for activity {i}/{total_gym_activities}: {activity['name']} ({activity['start_date_local']})")

        # Wait if needed before making detailed request
        rate_limiter.wait_if_needed(is_read_request=True, verbose=True)

        detail_response = requests.get(
            f'https://www.strava.com/api/v3/activities/{activity_id}',
            headers=headers
        )
        if detail_response.status_code == 200:
            detailed_activities.append(detail_response.json())
        elif detail_response.status_code == 429:  # Rate limit exceeded
            print(f"⚠️  Rate limit exceeded for activity {activity_id}. Waiting...")
            rate_limiter.print_status()
            # The rate limiter should handle this, but let's add extra safety
            print(f"Failed to fetch details for activity {activity_id} due to rate limit")
        else:
            print(f"Failed to fetch details for activity {activity_id}")

        # Show progress every 10 activities
        if i % 10 == 0:
            print(f"📊 Progress: {i}/{total_gym_activities} activities processed")
            rate_limiter.print_status()

    print(f"📊 Final rate limit status after fetching details:")
    rate_limiter.print_status()

    return detailed_activities

def parse_activity(activity):
    """Parse activity description to extract exercise data"""
    desc = activity.get('description', '')
    exercises = []
    current_exercise = None

    for line in desc.splitlines():
        line = line.strip()
        if not line:
            continue

        # Check if this is an exercise name (starts with letter, not "Set")
        if re.match(r'^[A-Za-z]', line) and not line.startswith('Set'):
            current_exercise = line
            continue

        # Parse sets with weight and reps: "Set 1: 135 lbs x 10"
        if match := re.match(r'^Set \d+: (\d+) lbs x (\d+)', line):
            if current_exercise:
                weight = int(match.group(1))
                reps = int(match.group(2))
                is_drop = '[Drop]' in line or 'drop' in line.lower()
                exercises.append({
                    'date': activity['start_date_local'],
                    'exercise': current_exercise,
                    'weight': weight,
                    'reps': reps,
                    'volume': weight * reps,
                    'is_drop': is_drop,
                    'workout': activity['name']
                })

        # Parse bodyweight exercises: "Set 1: 15 reps"
        elif match := re.match(r'^Set \d+: (\d+) reps', line):
            if current_exercise:
                reps = int(match.group(1))
                is_drop = '[Drop]' in line or 'drop' in line.lower()
                exercises.append({
                    'date': activity['start_date_local'],
                    'exercise': current_exercise,
                    'weight': 0,  # bodyweight
                    'reps': reps,
                    'volume': 0,  # can't calculate volume for bodyweight
                    'is_drop': is_drop,
                    'workout': activity['name']
                })

        # Alternative format: "Set 1: 10x135" or "Set 1: 10 x 135"
        elif match := re.match(r'^Set \d+: (\d+)\s*x\s*(\d+)', line):
            if current_exercise:
                reps = int(match.group(1))
                weight = int(match.group(2))
                is_drop = '[Drop]' in line or 'drop' in line.lower()
                exercises.append({
                    'date': activity['start_date_local'],
                    'exercise': current_exercise,
                    'weight': weight,
                    'reps': reps,
                    'volume': weight * reps,
                    'is_drop': is_drop,
                    'workout': activity['name']
                })

    return exercises

def analyze_gym_workouts():
    """Main analysis function for gym workout data"""
    activities = fetch_gym_activities()
    print(f"Found {len(activities)} gym activities")

    if not activities:
        print("No gym activities found!")
        return

    # Show sample activity for debugging
    print("\nSample activity structure:")
    print(f"Name: {activities[0]['name']}")
    print(f"Date: {activities[0]['start_date_local']}")
    print(f"Description preview: {activities[0].get('description', 'No description')[:200]}...")

    # Parse all activities
    all_sets = []
    for act in activities:
        sets = parse_activity(act)
        all_sets.extend(sets)
        print(f"Parsed {len(sets)} sets from {act['name']} on {act['start_date_local']}")

    if not all_sets:
        print("No exercise sets found in activity descriptions!")
        return

    # Create DataFrame
    df = pd.DataFrame(all_sets)
    print(f"\nTotal sets parsed: {len(all_sets)}")

    # Save raw data to CSV
    df.to_csv(GYM_DATA_FILE, index=False)
    print(f"Workout data saved to {GYM_DATA_FILE}")

    # Process data
    df['date'] = pd.to_datetime(df['date'])
    df['muscle_group'] = df['workout'].str.extract(r'(\d+)\.\s*(.+)')[1]

    print("\nDataset Overview:")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Unique exercises: {df['exercise'].nunique()}")
    print(f"Total workouts: {df.groupby(['date', 'workout']).ngroups}")

    print("\nWorkout distribution:")
    print(df['workout'].value_counts())

    print("\nTop exercises by frequency:")
    print(df['exercise'].value_counts().head(10))

    # Analysis and visualizations
    create_analysis_charts(df)

    # Detailed analysis by muscle group
    analyze_by_muscle_group(df)

    return df

def create_analysis_charts(df):
    """Create comprehensive analysis charts"""
    plt.style.use('default')

    # 1. Total Volume Over Time
    plt.figure(figsize=(12, 8))

    plt.subplot(2, 2, 1)
    daily_volume = df.groupby('date')['volume'].sum().reset_index()
    plt.plot(daily_volume['date'], daily_volume['volume'], marker='o', linewidth=2)
    plt.title('Total Workout Volume Over Time')
    plt.xlabel('Date')
    plt.ylabel('Total Volume (lbs × reps)')
    plt.xticks(rotation=45)
    plt.grid(True, alpha=0.3)

    # 2. Volume by Muscle Group
    plt.subplot(2, 2, 2)
    muscle_volume = df.groupby('workout')['volume'].sum().sort_values(ascending=True)
    muscle_volume.plot(kind='barh')
    plt.title('Total Volume by Muscle Group')
    plt.xlabel('Total Volume (lbs × reps)')

    # 3. Top Exercises by Volume
    plt.subplot(2, 2, 3)
    top_exercises = df[df['volume'] > 0].groupby('exercise')['volume'].sum().sort_values(ascending=False).head(8)
    top_exercises.plot(kind='bar')
    plt.title('Top Exercises by Total Volume')
    plt.ylabel('Total Volume (lbs × reps)')
    plt.xticks(rotation=45, ha='right')

    # 4. Workout Frequency Over Time
    plt.subplot(2, 2, 4)
    workout_freq = df.groupby([df['date'].dt.to_period('W'), 'workout']).size().unstack(fill_value=0)
    workout_freq.plot(kind='bar', stacked=True)
    plt.title('Weekly Workout Frequency')
    plt.xlabel('Week')
    plt.ylabel('Number of Workouts')
    plt.xticks(rotation=45)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.tight_layout()
    plt.savefig("gym_analysis_overview.png", dpi=300, bbox_inches='tight')
    plt.show()

def analyze_by_muscle_group(df):
    """Detailed analysis by muscle group"""
    muscle_groups = df['workout'].unique()

    for muscle_group in muscle_groups:
        muscle_data = df[df['workout'] == muscle_group]

        print(f"\n=== {muscle_group} Analysis ===")
        print(f"Total workouts: {muscle_data['date'].nunique()}")
        print(f"Total sets: {len(muscle_data)}")
        print(f"Total volume: {muscle_data['volume'].sum():,} lbs×reps")

        # Top exercises for this muscle group
        top_exercises = muscle_data.groupby('exercise')['volume'].sum().sort_values(ascending=False).head(5)
        print(f"\nTop 5 exercises by volume:")
        for exercise, volume in top_exercises.items():
            print(f"  {exercise}: {volume:,} lbs×reps")

        # Progress over time for top exercise
        if not top_exercises.empty:
            top_exercise = top_exercises.index[0]
            exercise_data = muscle_data[muscle_data['exercise'] == top_exercise]

            plt.figure(figsize=(10, 6))

            # Plot max weight over time
            plt.subplot(1, 2, 1)
            max_weight_by_date = exercise_data.groupby('date')['weight'].max()
            plt.plot(max_weight_by_date.index, max_weight_by_date.values, marker='o')
            plt.title(f'{top_exercise}\nMax Weight Progress')
            plt.xlabel('Date')
            plt.ylabel('Weight (lbs)')
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)

            # Plot total volume per workout
            plt.subplot(1, 2, 2)
            volume_by_date = exercise_data.groupby('date')['volume'].sum()
            plt.plot(volume_by_date.index, volume_by_date.values, marker='s', color='orange')
            plt.title(f'{top_exercise}\nVolume per Workout')
            plt.xlabel('Date')
            plt.ylabel('Total Volume (lbs × reps)')
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)

            plt.tight_layout()
            safe_filename = muscle_group.replace(', ', '_').replace(' ', '_').replace('.', '')
            plt.savefig(f"{safe_filename}_progress.png", dpi=300, bbox_inches='tight')
            plt.show()

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--refresh':
        print("Refreshing data from Strava...")
        # Remove local file to force refresh
        if os.path.exists(ACTIVITIES_FILE):
            os.remove(ACTIVITIES_FILE)

    analyze_gym_workouts()
