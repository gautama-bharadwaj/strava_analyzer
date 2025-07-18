#!/usr/bin/env python3
"""
Intelligent Batch Processing for Strava API

This script provides utilities for processing large numbers of Strava API requests
while respecting rate limits and optimizing the schedule.
"""

import time
import json
import requests
from datetime import datetime, timedelta
from strava_auth_manager import get_access_token
from strava_rate_limiter import rate_limiter

class StravaBatchProcessor:
    """Intelligent batch processor for Strava API requests"""

    def __init__(self, batch_size=None, delay_between_batches=1):
        """
        Initialize batch processor

        Args:
            batch_size: Maximum requests per batch (auto-calculated if None)
            delay_between_batches: Minimum delay between batches in seconds
        """
        self.access_token = get_access_token()
        self.headers = {'Authorization': f"Bearer {self.access_token}"}
        self.batch_size = batch_size
        self.delay_between_batches = delay_between_batches

        # Auto-calculate optimal batch size if not provided
        if self.batch_size is None:
            status = rate_limiter.get_status()
            # Use smaller of 15-min or daily remaining, with some buffer
            remaining_15min = status['read_15min']['remaining']
            remaining_daily = status['read_daily']['remaining']
            self.batch_size = min(remaining_15min, remaining_daily, 20)  # Cap at 20 per batch

    def process_activity_details(self, activity_ids, progress_callback=None):
        """
        Process activity detail requests in batches

        Args:
            activity_ids: List of activity IDs to fetch
            progress_callback: Function to call with progress updates

        Returns:
            List of activity details
        """
        total_activities = len(activity_ids)
        detailed_activities = []
        failed_activities = []

        print(f"🔄 Processing {total_activities} activity details in batches of {self.batch_size}")
        rate_limiter.print_status()

        for i in range(0, total_activities, self.batch_size):
            batch_end = min(i + self.batch_size, total_activities)
            batch_ids = activity_ids[i:batch_end]
            batch_num = (i // self.batch_size) + 1
            total_batches = (total_activities + self.batch_size - 1) // self.batch_size

            print(f"\n📦 Processing batch {batch_num}/{total_batches} ({len(batch_ids)} activities)")

            batch_results, batch_failed = self._process_batch(batch_ids)
            detailed_activities.extend(batch_results)
            failed_activities.extend(batch_failed)

            # Progress callback
            if progress_callback:
                progress = {
                    'completed': len(detailed_activities),
                    'failed': len(failed_activities),
                    'total': total_activities,
                    'batch_num': batch_num,
                    'total_batches': total_batches
                }
                progress_callback(progress)

            # Show progress
            completed = len(detailed_activities)
            print(f"✅ Batch complete. Total progress: {completed}/{total_activities} "
                  f"({100*completed/total_activities:.1f}%)")

            # Wait between batches (except for last batch)
            if batch_end < total_activities:
                if self.delay_between_batches > 0:
                    print(f"⏱️  Waiting {self.delay_between_batches}s between batches...")
                    time.sleep(self.delay_between_batches)

        print(f"\n🎯 Batch processing complete!")
        print(f"✅ Successfully processed: {len(detailed_activities)}")
        print(f"❌ Failed: {len(failed_activities)}")

        if failed_activities:
            print(f"\n⚠️  Failed activity IDs: {failed_activities}")

        rate_limiter.print_status()

        return detailed_activities, failed_activities

    def _process_batch(self, activity_ids):
        """Process a single batch of activity IDs"""
        results = []
        failed = []

        for activity_id in activity_ids:
            try:
                # Wait for rate limit if needed
                rate_limiter.wait_if_needed(is_read_request=True, verbose=False)

                response = requests.get(
                    f'https://www.strava.com/api/v3/activities/{activity_id}',
                    headers=self.headers,
                    timeout=30
                )

                if response.status_code == 200:
                    results.append(response.json())
                    print(f"  ✅ {activity_id}")
                elif response.status_code == 429:
                    print(f"  ⚠️  Rate limited for {activity_id}")
                    failed.append(activity_id)
                    # Rate limiter should handle this, but add extra safety
                    time.sleep(5)
                else:
                    print(f"  ❌ Failed {activity_id} (status: {response.status_code})")
                    failed.append(activity_id)

            except requests.exceptions.RequestException as e:
                print(f"  ❌ Network error for {activity_id}: {e}")
                failed.append(activity_id)
            except Exception as e:
                print(f"  ❌ Unexpected error for {activity_id}: {e}")
                failed.append(activity_id)

        return results, failed

    def retry_failed_activities(self, failed_activity_ids, max_retries=3):
        """Retry failed activity requests"""
        if not failed_activity_ids:
            return [], []

        print(f"\n🔄 Retrying {len(failed_activity_ids)} failed activities...")

        retry_results = []
        still_failed = []

        for retry_num in range(1, max_retries + 1):
            if not failed_activity_ids:
                break

            print(f"\n🔄 Retry attempt {retry_num}/{max_retries}")

            # Wait a bit longer between retries
            retry_delay = self.delay_between_batches * (retry_num * 2)
            if retry_delay > 0:
                print(f"⏱️  Waiting {retry_delay}s before retry...")
                time.sleep(retry_delay)

            batch_results, batch_failed = self._process_batch(failed_activity_ids)
            retry_results.extend(batch_results)
            failed_activity_ids = batch_failed

        still_failed = failed_activity_ids

        print(f"\n🎯 Retry complete!")
        print(f"✅ Recovered: {len(retry_results)}")
        print(f"❌ Still failed: {len(still_failed)}")

        return retry_results, still_failed

def save_activities_incrementally(activities, filename="strava_activities_batch.json"):
    """Save activities incrementally to avoid data loss"""
    backup_filename = f"{filename}.backup"

    # Create backup of existing file
    try:
        with open(filename, 'r') as f:
            existing_data = json.load(f)
        with open(backup_filename, 'w') as f:
            json.dump(existing_data, f, indent=2)
        print(f"📁 Backup created: {backup_filename}")
    except FileNotFoundError:
        print("📁 No existing file to backup")
    except Exception as e:
        print(f"⚠️  Backup failed: {e}")

    # Save new data
    try:
        with open(filename, 'w') as f:
            json.dump(activities, f, indent=2)
        print(f"💾 Activities saved to {filename}")
    except Exception as e:
        print(f"❌ Failed to save activities: {e}")
        # Try to restore backup
        try:
            with open(backup_filename, 'r') as f:
                backup_data = json.load(f)
            with open(filename, 'w') as f:
                json.dump(backup_data, f, indent=2)
            print(f"🔄 Restored from backup")
        except:
            print("❌ Failed to restore backup. Data may be lost!")

def example_batch_processing():
    """Example of how to use batch processing"""
    # This is an example - you would replace this with your actual activity IDs
    example_activity_ids = [12345, 67890, 11111, 22222]  # Replace with real IDs

    def progress_callback(progress):
        print(f"Progress update: {progress['completed']}/{progress['total']} completed")

    processor = StravaBatchProcessor(batch_size=5, delay_between_batches=2)

    # Process activities
    activities, failed = processor.process_activity_details(
        example_activity_ids,
        progress_callback=progress_callback
    )

    # Retry failed activities
    if failed:
        retry_activities, still_failed = processor.retry_failed_activities(failed)
        activities.extend(retry_activities)

    # Save results
    save_activities_incrementally(activities, "detailed_activities.json")

    return activities

if __name__ == "__main__":
    print("🚀 Strava Batch Processor")
    print("This is a utility module. Import it in your scripts for batch processing.")
    print("\nExample usage:")
    print("  from batch_processor import StravaBatchProcessor")
    print("  processor = StravaBatchProcessor()")
    print("  activities, failed = processor.process_activity_details(activity_ids)")
