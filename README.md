# Strava Dashboard

A personal dashboard for everything you log on Strava: runs, hikes, and gym
workouts that Hevy posts to Strava. Gym sets (exercise, weight, reps) are read
from the text Hevy writes into each activity's description, so no Hevy Pro
subscription is needed.


## Setup

Requires Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env   # then fill in your Strava client ID and secret
```

On https://www.strava.com/settings/api set **Authorization Callback Domain**
to `localhost`.

## Usage

```bash
stravadash auth       # one time: opens Strava in your browser and saves tokens
stravadash sync       # download activities (incremental after the first run)
stravadash status     # counts by sport and parsed gym totals
stravadash exercises  # parsed exercises, most frequent first
stravadash unparsed   # gym sessions where no sets could be read
stravadash reparse    # re-run the Hevy parser on stored data, no API calls
stravadash serve      # dashboard at http://localhost:8050 (add --demo for sample data)
```

(`python -m stravadash <command>` works too.)

Everything is stored locally in `data/strava.db` (SQLite) and
`data/tokens.json`; both are git-ignored.

### Strava rate limits

Strava allows 100 read requests per 15 minutes and 1,000 per day. Listing
activities is cheap (200 per request), but each gym session needs one extra
request to read its description. The first sync pauses automatically between
15-minute windows; if it hits the daily cap it stops cleanly and the next
`stravadash sync` picks up where it left off.

## Development

```bash
pytest
```

Layout:

- `stravadash/auth.py` – OAuth login with a local callback, token refresh
- `stravadash/client.py` – Strava API client that reads rate-limit headers
- `stravadash/sync.py` – incremental sync into SQLite
- `stravadash/hevy_parser.py` – parses Hevy's workout text into sets
- `stravadash/store.py` – SQLite schema and queries
