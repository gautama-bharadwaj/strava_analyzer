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
stravadash export     # static copy in ./site, activity names hidden (--private keeps them)
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

## Hosting on GitHub Pages

`.github/workflows/publish.yml` runs once a day (and on demand from the
Actions tab): it syncs new activities and publishes the static dashboard.

What gets published is only the exported page: stats, dates, distances,
heart rate and exercise history. Activity titles are replaced with generic
labels because they often name places. GPS routes and coordinates are
dropped before anything is stored, and the database and Strava tokens never
leave the encrypted Actions cache.

One-time setup:

1. **Repository secrets** (Settings → Secrets and variables → Actions):
   - `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET`: from your `.env`
   - `STRAVA_REFRESH_TOKEN`: run
     `python3 -c "import json; print(json.load(open('data/tokens.json'))['refresh_token'])"`
   - `DATA_KEY`: any long random string, e.g. the output of `openssl rand -base64 32`.
     It encrypts the cached database; keep it secret.
2. **Pages**: Settings → Pages → Build and deployment → Source: **GitHub Actions**.
3. Optional: a repository *variable* `STRAVADASH_WEEKLY_TARGET` for your
   weekly gym goal (default 3).
4. Merge to `main`, then Actions → **Publish dashboard** → **Run workflow**.
   The first run does a full sync and takes about an hour because of
   Strava's rate limits; later runs take a minute or two.

GitHub pauses scheduled workflows on public repos after 60 days without a
commit; it emails you first and one click in the Actions tab re-enables it.

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
