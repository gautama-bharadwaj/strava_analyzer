import time
import json
import os
from collections import deque
from datetime import datetime, timedelta
import threading

class StravaRateLimiter:
    """
    Rate limiter for Strava API to respect the following limits:
    - Overall: 200 requests per 15 minutes, 2,000 daily
    - Read: 100 requests per 15 minutes, 1,000 daily
    """

    def __init__(self, data_file="rate_limiter_data.json"):
        self.data_file = data_file
        self.lock = threading.Lock()

        # Rate limits
        self.OVERALL_15MIN_LIMIT = 200
        self.OVERALL_DAILY_LIMIT = 2000
        self.READ_15MIN_LIMIT = 100
        self.READ_DAILY_LIMIT = 1000

        # Time windows
        self.FIFTEEN_MINUTES = 15 * 60  # 900 seconds
        self.ONE_DAY = 24 * 60 * 60     # 86400 seconds

        # Request tracking
        self.overall_requests_15min = deque()
        self.overall_requests_daily = deque()
        self.read_requests_15min = deque()
        self.read_requests_daily = deque()

        # Load existing data
        self._load_data()

    def _load_data(self):
        """Load request history from file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)

                current_time = time.time()

                # Load and filter 15-minute data
                overall_15min = data.get('overall_15min', [])
                self.overall_requests_15min = deque([
                    ts for ts in overall_15min
                    if current_time - ts < self.FIFTEEN_MINUTES
                ])

                read_15min = data.get('read_15min', [])
                self.read_requests_15min = deque([
                    ts for ts in read_15min
                    if current_time - ts < self.FIFTEEN_MINUTES
                ])

                # Load and filter daily data
                overall_daily = data.get('overall_daily', [])
                self.overall_requests_daily = deque([
                    ts for ts in overall_daily
                    if current_time - ts < self.ONE_DAY
                ])

                read_daily = data.get('read_daily', [])
                self.read_requests_daily = deque([
                    ts for ts in read_daily
                    if current_time - ts < self.ONE_DAY
                ])

            except (json.JSONDecodeError, KeyError):
                # If file is corrupted, start fresh
                pass

    def _save_data(self):
        """Save current request history to file"""
        data = {
            'overall_15min': list(self.overall_requests_15min),
            'overall_daily': list(self.overall_requests_daily),
            'read_15min': list(self.read_requests_15min),
            'read_daily': list(self.read_requests_daily),
            'last_updated': time.time()
        }

        with open(self.data_file, 'w') as f:
            json.dump(data, f)

    def _cleanup_old_requests(self):
        """Remove requests outside the time windows"""
        current_time = time.time()

        # Clean 15-minute windows
        while (self.overall_requests_15min and
               current_time - self.overall_requests_15min[0] >= self.FIFTEEN_MINUTES):
            self.overall_requests_15min.popleft()

        while (self.read_requests_15min and
               current_time - self.read_requests_15min[0] >= self.FIFTEEN_MINUTES):
            self.read_requests_15min.popleft()

        # Clean daily windows
        while (self.overall_requests_daily and
               current_time - self.overall_requests_daily[0] >= self.ONE_DAY):
            self.overall_requests_daily.popleft()

        while (self.read_requests_daily and
               current_time - self.read_requests_daily[0] >= self.ONE_DAY):
            self.read_requests_daily.popleft()

    def _get_wait_time(self, is_read_request=True):
        """Calculate how long to wait before making a request"""
        current_time = time.time()
        self._cleanup_old_requests()

        wait_times = []

        # Check overall limits
        if len(self.overall_requests_15min) >= self.OVERALL_15MIN_LIMIT:
            oldest_15min = self.overall_requests_15min[0]
            wait_time = self.FIFTEEN_MINUTES - (current_time - oldest_15min) + 1
            wait_times.append(wait_time)

        if len(self.overall_requests_daily) >= self.OVERALL_DAILY_LIMIT:
            oldest_daily = self.overall_requests_daily[0]
            wait_time = self.ONE_DAY - (current_time - oldest_daily) + 1
            wait_times.append(wait_time)

        # Check read limits if this is a read request
        if is_read_request:
            if len(self.read_requests_15min) >= self.READ_15MIN_LIMIT:
                oldest_read_15min = self.read_requests_15min[0]
                wait_time = self.FIFTEEN_MINUTES - (current_time - oldest_read_15min) + 1
                wait_times.append(wait_time)

            if len(self.read_requests_daily) >= self.READ_DAILY_LIMIT:
                oldest_read_daily = self.read_requests_daily[0]
                wait_time = self.ONE_DAY - (current_time - oldest_read_daily) + 1
                wait_times.append(wait_time)

        return max(wait_times) if wait_times else 0

    def _record_request(self, is_read_request=True):
        """Record a successful request"""
        current_time = time.time()

        # Record overall requests
        self.overall_requests_15min.append(current_time)
        self.overall_requests_daily.append(current_time)

        # Record read requests
        if is_read_request:
            self.read_requests_15min.append(current_time)
            self.read_requests_daily.append(current_time)

        # Save to file
        self._save_data()

    def wait_if_needed(self, is_read_request=True, verbose=True):
        """
        Wait if necessary to respect rate limits before making a request.

        Args:
            is_read_request: True for GET requests, False for write requests
            verbose: Whether to print waiting messages
        """
        with self.lock:
            wait_time = self._get_wait_time(is_read_request)

            if wait_time > 0:
                if verbose:
                    wait_minutes = wait_time / 60
                    if wait_minutes > 60:
                        wait_hours = wait_minutes / 60
                        print(f"⏳ Rate limit reached. Waiting {wait_hours:.1f} hours...")
                    elif wait_minutes > 1:
                        print(f"⏳ Rate limit reached. Waiting {wait_minutes:.1f} minutes...")
                    else:
                        print(f"⏳ Rate limit reached. Waiting {wait_time:.0f} seconds...")

                time.sleep(wait_time)

            # Record the request
            self._record_request(is_read_request)

    def get_status(self):
        """Get current rate limit status"""
        with self.lock:
            self._cleanup_old_requests()

            return {
                'overall_15min': {
                    'used': len(self.overall_requests_15min),
                    'limit': self.OVERALL_15MIN_LIMIT,
                    'remaining': self.OVERALL_15MIN_LIMIT - len(self.overall_requests_15min)
                },
                'overall_daily': {
                    'used': len(self.overall_requests_daily),
                    'limit': self.OVERALL_DAILY_LIMIT,
                    'remaining': self.OVERALL_DAILY_LIMIT - len(self.overall_requests_daily)
                },
                'read_15min': {
                    'used': len(self.read_requests_15min),
                    'limit': self.READ_15MIN_LIMIT,
                    'remaining': self.READ_15MIN_LIMIT - len(self.read_requests_15min)
                },
                'read_daily': {
                    'used': len(self.read_requests_daily),
                    'limit': self.READ_DAILY_LIMIT,
                    'remaining': self.READ_DAILY_LIMIT - len(self.read_requests_daily)
                }
            }

    def print_status(self):
        """Print current rate limit status"""
        status = self.get_status()

        print("\n📊 Strava API Rate Limit Status:")
        print("=" * 40)

        print(f"Overall (15min): {status['overall_15min']['used']}/{status['overall_15min']['limit']} "
              f"(remaining: {status['overall_15min']['remaining']})")

        print(f"Overall (daily): {status['overall_daily']['used']}/{status['overall_daily']['limit']} "
              f"(remaining: {status['overall_daily']['remaining']})")

        print(f"Read (15min):    {status['read_15min']['used']}/{status['read_15min']['limit']} "
              f"(remaining: {status['read_15min']['remaining']})")

        print(f"Read (daily):    {status['read_daily']['used']}/{status['read_daily']['limit']} "
              f"(remaining: {status['read_daily']['remaining']})")

        print("=" * 40)

# Global rate limiter instance
rate_limiter = StravaRateLimiter()
