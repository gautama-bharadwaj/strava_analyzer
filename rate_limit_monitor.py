#!/usr/bin/env python3
"""
Strava Rate Limit Monitor and Management Tool

This script helps you monitor your Strava API rate limit usage
and provides utilities to manage rate limiting.
"""

import argparse
import sys
import time
from datetime import datetime
from strava_rate_limiter import rate_limiter

def show_status():
    """Show current rate limit status"""
    rate_limiter.print_status()

def reset_counters():
    """Reset rate limit counters (use with caution!)"""
    print("⚠️  WARNING: This will reset all rate limit counters!")
    print("This should only be used if you're sure the stored data is incorrect.")
    confirm = input("Are you sure you want to continue? (yes/NO): ").strip().lower()

    if confirm == 'yes':
        import os
        if os.path.exists(rate_limiter.data_file):
            os.remove(rate_limiter.data_file)
            print("✅ Rate limit data file removed. Counters will start fresh.")
        else:
            print("ℹ️  No rate limit data file found.")
    else:
        print("Operation cancelled.")

def estimate_time_for_requests(num_requests, read_only=True):
    """Estimate how long it would take to make a given number of requests"""
    status = rate_limiter.get_status()

    if read_only:
        remaining_15min = status['read_15min']['remaining']
        remaining_daily = status['read_daily']['remaining']
        limit_15min = status['read_15min']['limit']
        limit_daily = status['read_daily']['limit']
        request_type = "read"
    else:
        remaining_15min = status['overall_15min']['remaining']
        remaining_daily = status['overall_daily']['remaining']
        limit_15min = status['overall_15min']['limit']
        limit_daily = status['overall_daily']['limit']
        request_type = "overall"

    print(f"\n📊 Estimation for {num_requests} {request_type} requests:")
    print("=" * 50)

    if num_requests <= remaining_15min and num_requests <= remaining_daily:
        print("✅ All requests can be made immediately!")
        return

    if num_requests > remaining_daily:
        # Need multiple days
        full_days = (num_requests - remaining_daily) // limit_daily
        remaining_after_full_days = (num_requests - remaining_daily) % limit_daily

        total_hours = full_days * 24
        if remaining_after_full_days > 0:
            # Check if we need additional time for the last batch
            if remaining_after_full_days > limit_15min:
                # Need multiple 15-minute windows
                additional_windows = (remaining_after_full_days + limit_15min - 1) // limit_15min
                total_hours += (additional_windows * 0.25)  # 15 minutes = 0.25 hours

        print(f"⏳ Estimated time: {total_hours:.1f} hours ({total_hours/24:.1f} days)")
        print(f"   - {full_days} full day(s) for bulk requests")
        if remaining_after_full_days > 0:
            print(f"   - Additional time for {remaining_after_full_days} remaining requests")

    elif num_requests > remaining_15min:
        # Need multiple 15-minute windows but within daily limit
        windows_needed = (num_requests + limit_15min - 1) // limit_15min
        total_minutes = windows_needed * 15

        print(f"⏳ Estimated time: {total_minutes} minutes ({total_minutes/60:.1f} hours)")
        print(f"   - Requires {windows_needed} 15-minute window(s)")

    print(f"📈 Current usage:")
    print(f"   - 15-min: {status[f'{request_type}_15min']['used']}/{limit_15min}")
    print(f"   - Daily:  {status[f'{request_type}_daily']['used']}/{limit_daily}")

def wait_for_reset():
    """Wait until rate limits reset"""
    print("⏳ Waiting for rate limits to reset...")
    print("Press Ctrl+C to cancel")

    try:
        start_time = time.time()
        while True:
            status = rate_limiter.get_status()

            # Check if we have any capacity
            if (status['read_15min']['remaining'] > 0 and
                status['read_daily']['remaining'] > 0):
                elapsed = time.time() - start_time
                print(f"✅ Rate limits have capacity after {elapsed:.0f} seconds!")
                rate_limiter.print_status()
                break

            # Show status every minute
            elapsed = time.time() - start_time
            if int(elapsed) % 60 == 0:
                print(f"⏳ Waiting... ({elapsed/60:.0f} minutes elapsed)")
                rate_limiter.print_status()

            time.sleep(10)  # Check every 10 seconds

    except KeyboardInterrupt:
        print("\n❌ Wait cancelled by user")

def main():
    parser = argparse.ArgumentParser(
        description="Strava Rate Limit Monitor and Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rate_limit_monitor.py status           # Show current status
  python rate_limit_monitor.py estimate 150    # Estimate time for 150 requests
  python rate_limit_monitor.py wait            # Wait for rate limits to reset
  python rate_limit_monitor.py reset           # Reset counters (use with caution)
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Status command
    status_parser = subparsers.add_parser('status', help='Show current rate limit status')

    # Estimate command
    estimate_parser = subparsers.add_parser('estimate', help='Estimate time for given number of requests')
    estimate_parser.add_argument('requests', type=int, help='Number of requests to estimate')
    estimate_parser.add_argument('--write', action='store_true',
                                help='Estimate for write requests (default: read requests)')

    # Wait command
    wait_parser = subparsers.add_parser('wait', help='Wait until rate limits reset')

    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Reset rate limit counters')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == 'status':
        show_status()

    elif args.command == 'estimate':
        estimate_time_for_requests(args.requests, read_only=not args.write)

    elif args.command == 'wait':
        wait_for_reset()

    elif args.command == 'reset':
        reset_counters()

if __name__ == "__main__":
    main()
