#!/usr/bin/env python3
"""
Enhanced Gym Analyzer with Smart Rate Limiting

This version of the gym analyzer uses intelligent batch processing
and rate limiting to efficiently fetch data while respecting API limits.
"""

import argparse
import sys
import os
import json
from datetime import datetime
from gym_analyzer import (
    TARGET_TITLES, ACTIVITIES_FILE, GYM_DATA_FILE,
    load_activities, parse_activity, create_analysis_charts,
    analyze_by_muscle_group
)
from batch_processor import StravaBatchProcessor, save_activities_incrementally
from strava_rate_limiter import rate_limiter
import pandas as pd

def fetch_activities_smart(force_refresh=False, batch_size=10):
    """
    Smart activity fetching with rate limiting and batch processing

    Args:
        force_refresh: Whether to fetch fresh data even if local file exists
        batch_size: Number of detailed requests to process in each batch
    """
    # Check if we have local activities
    activities = None if force_refresh else load_activities()

    if activities is None:
        print("📥 No local activities found or refresh requested.")
        print("📊 Current rate limit status:")
        rate_limiter.print_status()

        # Import here to avoid circular dependency
        from gym_analyzer import fetch_all_activities
        activities = fetch_all_activities()
    else:
        print(f"📁 Loaded {len(activities)} activities from local file")

    # Filter for gym activities
    gym_activities = []
    for activity in activities:
        if any(target in activity['name'] for target in TARGET_TITLES):
            gym_activities.append(activity)

    print(f"🏋️ Found {len(gym_activities)} gym activities")

    if not gym_activities:
        print("❌ No gym activities found!")
        return []

    # Check if we need detailed data
    detailed_file = "detailed_gym_activities.json"

    if os.path.exists(detailed_file) and not force_refresh:
        print(f"📁 Loading detailed activities from {detailed_file}")
        try:
            with open(detailed_file, 'r') as f:
                detailed_activities = json.load(f)
            print(f"✅ Loaded {len(detailed_activities)} detailed activities")
            return detailed_activities
        except Exception as e:
            print(f"⚠️  Failed to load detailed activities: {e}")
            print("🔄 Will fetch fresh detailed data")

    # Get detailed information using batch processor
    print(f"\n🔄 Fetching detailed information for {len(gym_activities)} gym activities")
    print("📊 Current rate limit status before detailed fetch:")
    rate_limiter.print_status()

    # Estimate time needed
    from rate_limit_monitor import estimate_time_for_requests
    print(f"\n⏱️  Time estimation for {len(gym_activities)} detailed requests:")
    estimate_time_for_requests(len(gym_activities), read_only=True)

    # Ask user if they want to continue
    if len(gym_activities) > 50:  # Only ask for large batches
        response = input(f"\nProceed with fetching {len(gym_activities)} detailed activities? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ Operation cancelled by user")
            return []

    # Extract activity IDs
    activity_ids = [activity['id'] for activity in gym_activities]

    # Create batch processor
    processor = StravaBatchProcessor(batch_size=batch_size, delay_between_batches=1)

    def progress_callback(progress):
        """Progress callback for batch processing"""
        pct = 100 * progress['completed'] / progress['total']
        print(f"📈 Progress: {progress['completed']}/{progress['total']} ({pct:.1f}%) "
              f"- Batch {progress['batch_num']}/{progress['total_batches']}")

    # Process activities in batches
    detailed_activities, failed_ids = processor.process_activity_details(
        activity_ids,
        progress_callback=progress_callback
    )

    # Retry failed activities
    if failed_ids:
        print(f"\n🔄 Retrying {len(failed_ids)} failed activities...")
        retry_activities, still_failed = processor.retry_failed_activities(failed_ids, max_retries=2)
        detailed_activities.extend(retry_activities)

        if still_failed:
            print(f"⚠️  {len(still_failed)} activities could not be fetched: {still_failed}")

    # Save detailed activities
    save_activities_incrementally(detailed_activities, detailed_file)

    print(f"\n✅ Successfully fetched detailed data for {len(detailed_activities)} activities")
    print("📊 Final rate limit status:")
    rate_limiter.print_status()

    return detailed_activities

def analyze_gym_workouts_smart(force_refresh=False, batch_size=10, save_csv=True):
    """
    Enhanced gym workout analysis with smart fetching

    Args:
        force_refresh: Whether to fetch fresh data
        batch_size: Batch size for API requests
        save_csv: Whether to save results to CSV
    """
    print("🏋️ Smart Gym Analyzer")
    print("=" * 50)

    # Fetch activities with smart rate limiting
    activities = fetch_activities_smart(force_refresh=force_refresh, batch_size=batch_size)

    if not activities:
        print("❌ No activities to analyze!")
        return None

    print(f"\n📊 Analyzing {len(activities)} gym activities...")

    # Show sample activity for debugging
    print("\n🔍 Sample activity:")
    sample = activities[0]
    print(f"   Name: {sample['name']}")
    print(f"   Date: {sample['start_date_local']}")
    print(f"   Description preview: {sample.get('description', 'No description')[:200]}...")

    # Parse all activities
    all_sets = []
    for act in activities:
        sets = parse_activity(act)
        all_sets.extend(sets)
        if sets:
            print(f"   📋 {len(sets)} sets from {act['name']} on {act['start_date_local']}")

    if not all_sets:
        print("❌ No exercise sets found in activity descriptions!")
        return None

    # Create DataFrame
    df = pd.DataFrame(all_sets)
    print(f"\n📈 Analysis Results:")
    print(f"   Total sets parsed: {len(all_sets)}")

    if save_csv:
        # Save raw data to CSV
        df.to_csv(GYM_DATA_FILE, index=False)
        print(f"   💾 Workout data saved to {GYM_DATA_FILE}")

    # Process data
    df['date'] = pd.to_datetime(df['date'])
    df['muscle_group'] = df['workout'].str.extract(r'(\d+)\.\s*(.+)')[1]

    print(f"\n📊 Dataset Overview:")
    print(f"   Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"   Unique exercises: {df['exercise'].nunique()}")
    print(f"   Total workouts: {df.groupby(['date', 'workout']).ngroups}")

    print(f"\n🏋️ Workout distribution:")
    workout_counts = df['workout'].value_counts()
    for workout, count in workout_counts.items():
        print(f"   {workout}: {count} sets")

    print(f"\n🔥 Top exercises by frequency:")
    top_exercises = df['exercise'].value_counts().head(10)
    for exercise, count in top_exercises.items():
        print(f"   {exercise}: {count} sets")

    # Analysis and visualizations
    try:
        print(f"\n📈 Generating analysis charts...")
        create_analysis_charts(df)
        print(f"   ✅ Overview charts saved")

        analyze_by_muscle_group(df)
        print(f"   ✅ Muscle group analysis complete")
    except Exception as e:
        print(f"   ⚠️  Chart generation failed: {e}")

    return df

def main():
    parser = argparse.ArgumentParser(
        description="Enhanced Gym Analyzer with Smart Rate Limiting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python smart_gym_analyzer.py                    # Analyze with cached data
  python smart_gym_analyzer.py --refresh          # Fetch fresh data
  python smart_gym_analyzer.py --batch-size 5     # Use smaller batches
  python smart_gym_analyzer.py --status           # Show rate limit status only
        """
    )

    parser.add_argument('--refresh', action='store_true',
                       help='Force refresh of all data from Strava API')
    parser.add_argument('--batch-size', type=int, default=10,
                       help='Number of detailed requests per batch (default: 10)')
    parser.add_argument('--no-csv', action='store_true',
                       help='Skip saving results to CSV')
    parser.add_argument('--status', action='store_true',
                       help='Show rate limit status only')

    args = parser.parse_args()

    if args.status:
        print("📊 Current Strava API Rate Limit Status:")
        rate_limiter.print_status()
        return

    try:
        df = analyze_gym_workouts_smart(
            force_refresh=args.refresh,
            batch_size=args.batch_size,
            save_csv=not args.no_csv
        )

        if df is not None:
            print(f"\n✅ Analysis complete! Check the generated charts and CSV file.")

    except KeyboardInterrupt:
        print(f"\n❌ Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
