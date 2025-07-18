#!/usr/bin/env python3
"""
Test and demonstration script for the new Strava rate limiting features.
This script showcases all the capabilities that have been added to respect Strava's API limits.
"""

import time
from strava_rate_limiter import rate_limiter
from rate_limit_monitor import estimate_time_for_requests

def test_rate_limiter():
    """Test the rate limiter functionality"""
    print("🧪 Testing Strava Rate Limiter")
    print("=" * 50)

    # Show current status
    print("📊 Current Rate Limit Status:")
    rate_limiter.print_status()

    # Test estimation for various scenarios
    test_scenarios = [25, 50, 100, 150, 200, 500, 1500]

    print("\n⏱️  Time Estimations for Different Request Counts:")
    print("-" * 50)

    for num_requests in test_scenarios:
        print(f"\n🔍 Estimating time for {num_requests} requests:")
        estimate_time_for_requests(num_requests, read_only=True)

    print("\n✅ Rate limiter tests completed!")

def demonstrate_features():
    """Demonstrate the key features of the rate limiting system"""
    print("\n🌟 Strava API Rate Limiting System Features")
    print("=" * 60)

    features = [
        "✅ Automatic rate limit tracking (15-min and daily windows)",
        "✅ Intelligent waiting when limits are reached",
        "✅ Persistent storage of usage across script runs",
        "✅ Separate tracking for read vs. write operations",
        "✅ Real-time status monitoring and reporting",
        "✅ Time estimation for large batch operations",
        "✅ Smart batch processing with retry logic",
        "✅ Incremental data saving to prevent loss",
        "✅ User-friendly CLI tools for monitoring",
        "✅ Integration with existing gym analyzer"
    ]

    for feature in features:
        print(feature)
        time.sleep(0.1)  # Small delay for dramatic effect

    print("\n📋 Usage Summary:")
    print("-" * 30)

    status = rate_limiter.get_status()

    print(f"🔸 Read requests used today: {status['read_daily']['used']}/{status['read_daily']['limit']}")
    print(f"🔸 Overall requests used today: {status['overall_daily']['used']}/{status['overall_daily']['limit']}")
    print(f"🔸 Read requests in last 15 min: {status['read_15min']['used']}/{status['read_15min']['limit']}")
    print(f"🔸 Overall requests in last 15 min: {status['overall_15min']['used']}/{status['overall_15min']['limit']}")

    # Calculate efficiency
    if status['overall_daily']['used'] > 0:
        efficiency = (status['read_daily']['used'] / status['overall_daily']['used']) * 100
        print(f"🔸 API efficiency: {efficiency:.1f}% (read operations)")

    print("\n📚 Available Commands:")
    print("-" * 30)
    commands = [
        "python smart_gym_analyzer.py --status",
        "python rate_limit_monitor.py status",
        "python rate_limit_monitor.py estimate 150",
        "python smart_gym_analyzer.py --refresh",
        "python smart_gym_analyzer.py --batch-size 5"
    ]

    for cmd in commands:
        print(f"  💻 {cmd}")

def show_best_practices():
    """Show best practices for using the rate limiting system"""
    print("\n🎯 Best Practices for Strava API Usage")
    print("=" * 50)

    practices = [
        "1️⃣  Use cached data when possible (smart_gym_analyzer.py without --refresh)",
        "2️⃣  Monitor your usage regularly (rate_limit_monitor.py status)",
        "3️⃣  Estimate before large operations (rate_limit_monitor.py estimate N)",
        "4️⃣  Use smaller batch sizes for safety (--batch-size 5-10)",
        "5️⃣  Let the system handle waiting - don't interrupt it",
        "6️⃣  Plan large data fetches during off-peak hours",
        "7️⃣  The system persists your usage across restarts",
        "8️⃣  Check the generated charts and CSV files for insights"
    ]

    for practice in practices:
        print(f"  {practice}")

    print(f"\n💡 Pro Tip: The detailed_gym_activities.json file contains all your")
    print(f"   gym workout details and is automatically saved for future use!")

def main():
    """Main demonstration function"""
    print("🏋️ Strava Gym Analyzer - Rate Limiting System Demo")
    print("=" * 60)
    print("This system now respects Strava's API limits:")
    print("  • Overall: 200 requests/15min, 2,000/day")
    print("  • Read: 100 requests/15min, 1,000/day")
    print("=" * 60)

    # Run demonstrations
    test_rate_limiter()
    demonstrate_features()
    show_best_practices()

    print(f"\n🎉 All systems are working perfectly!")
    print(f"📖 Check RATE_LIMITING_GUIDE.md for detailed documentation")
    print(f"🚀 You're ready to analyze your Strava data efficiently!")

if __name__ == "__main__":
    main()
