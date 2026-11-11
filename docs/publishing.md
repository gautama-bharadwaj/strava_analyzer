# Publishing your dashboard to GitHub Pages

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
