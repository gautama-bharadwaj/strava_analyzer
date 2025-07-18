# Strava API Rate Limiting Guide

## Overview

This project now includes comprehensive rate limiting to respect Strava's API limits:

- **Overall Rate Limits**: 200 requests every 15 minutes, 2,000 daily
- **Read Rate Limits**: 100 requests every 15 minutes, 1,000 daily

## New Features

### 1. Automatic Rate Limiting (`strava_rate_limiter.py`)

The rate limiter automatically:
- Tracks your API usage across 15-minute and daily windows
- Waits when limits are reached
- Persists usage data between script runs
- Provides detailed status information

### 2. Rate Limit Monitor (`rate_limit_monitor.py`)

Monitor and manage your rate limits:

```bash
# Show current status
python rate_limit_monitor.py status

# Estimate time needed for 150 requests
python rate_limit_monitor.py estimate 150

# Wait until rate limits reset
python rate_limit_monitor.py wait

# Reset counters (use with caution!)
python rate_limit_monitor.py reset
```

### 3. Batch Processor (`batch_processor.py`)

Intelligent batch processing for large numbers of API requests:

```python
from batch_processor import StravaBatchProcessor

processor = StravaBatchProcessor(batch_size=10)
activities, failed = processor.process_activity_details(activity_ids)
```

### 4. Smart Gym Analyzer (`smart_gym_analyzer.py`)

Enhanced version of the gym analyzer with built-in rate limiting:

```bash
# Analyze with cached data (recommended)
python smart_gym_analyzer.py

# Force refresh from API (respects rate limits)
python smart_gym_analyzer.py --refresh

# Use smaller batches (better for rate limiting)
python smart_gym_analyzer.py --batch-size 5

# Check rate limit status only
python smart_gym_analyzer.py --status
```

## Usage Recommendations

### First Time Setup

1. Use the smart analyzer to get your data efficiently:
```bash
python smart_gym_analyzer.py --refresh --batch-size 5
```

2. Monitor your rate limits:
```bash
python rate_limit_monitor.py status
```

### Daily Usage

For regular analysis, use cached data:
```bash
python smart_gym_analyzer.py
```

This will use your previously downloaded data without making new API calls.

### Handling Large Data Sets

If you have many activities (>100), the system will:
1. Show you an estimate of how long it will take
2. Ask for confirmation before proceeding
3. Process in small batches with delays
4. Save progress incrementally
5. Retry failed requests

### Rate Limit Best Practices

1. **Use cached data when possible**: The smart analyzer saves detailed data locally
2. **Monitor your usage**: Check `python rate_limit_monitor.py status` regularly
3. **Use appropriate batch sizes**: Smaller batches (5-10) are safer
4. **Plan large operations**: Use the estimate command to plan timing
5. **Be patient**: The system will wait when limits are reached

## File Structure

- `strava_rate_limiter.py` - Core rate limiting logic
- `rate_limit_monitor.py` - CLI tool for monitoring limits
- `batch_processor.py` - Intelligent batch processing
- `smart_gym_analyzer.py` - Enhanced analyzer with rate limiting
- `gym_analyzer.py` - Original analyzer (now rate-limited)
- `rate_limiter_data.json` - Stores your rate limit usage (auto-created)

## Error Handling

The system handles:
- Rate limit exceeded (429) responses
- Network timeouts and errors
- Interrupted operations (Ctrl+C)
- Data corruption (automatic backup/restore)

## Monitoring Your Usage

The rate limiter tracks:
- Requests in the last 15 minutes
- Requests in the last 24 hours
- Separate counters for read vs. write operations
- Persistent storage across script runs

## Troubleshooting

### "Rate limit reached" messages
This is normal - the system will wait automatically.

### High API usage
Check your status with:
```bash
python rate_limit_monitor.py status
```

### Reset counters (if needed)
Only if you're sure the stored data is wrong:
```bash
python rate_limit_monitor.py reset
```

### Force fresh data
```bash
python smart_gym_analyzer.py --refresh
```

## Examples

### Quick Analysis (Recommended)
```bash
# Use cached data - fast and doesn't use API calls
python smart_gym_analyzer.py
```

### Fresh Data with Rate Limiting
```bash
# This will respect all rate limits automatically
python smart_gym_analyzer.py --refresh --batch-size 5
```

### Monitor Before Large Operations
```bash
# Check your current API usage
python rate_limit_monitor.py status

# Estimate time for 200 requests
python rate_limit_monitor.py estimate 200

# If needed, wait for reset
python rate_limit_monitor.py wait
```

The system is designed to be "set and forget" - it will automatically handle rate limiting so you don't have to worry about hitting Strava's limits!
