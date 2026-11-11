"""Pull activities from Strava into the local store."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from stravadash.client import DailyLimitReached, StravaClient
from stravadash.hevy_parser import parse_description
from stravadash.store import Store

# Strava sport types Hevy (and other strength apps) post as. Only these get
# the extra per-activity request needed to read the description.
GYM_SPORT_TYPES = {"WeightTraining", "Workout", "Crossfit", "HighIntensityIntervalTraining"}

# Re-list a few days before the newest stored activity so recent edits
# (renames, Hevy updating a description) are picked up.
OVERLAP_SECONDS = 3 * 24 * 3600


def sync(store: Store, client: StravaClient, full: bool = False, log: Callable[[str], None] = print) -> dict:
    stats = {"listed": 0, "details": 0, "sets": 0, "complete": True}

    after = None if full else store.latest_start_epoch()
    if after:
        after -= OVERLAP_SECONDS
    log("Listing all activities..." if after is None else "Listing new activities...")

    try:
        with store.transaction():
            for a in client.list_activities(after=after):
                store.upsert_summary(a)
                if after is not None:
                    # Recent activities get re-read in case the description was edited.
                    store.conn.execute("UPDATE activities SET detail_fetched=0 WHERE id=?", (a["id"],))
                stats["listed"] += 1
                if stats["listed"] % 200 == 0:
                    log(f"  {stats['listed']} activities listed")
        log(f"Listed {stats['listed']} activities.")

        todo = store.ids_needing_detail(GYM_SPORT_TYPES)
        if todo:
            log(f"Fetching workout details for {len(todo)} gym sessions (newest first)...")
        for i, activity_id in enumerate(todo, 1):
            detail = client.get_activity(activity_id)
            with store.transaction():
                store.save_detail(detail)
                stats["sets"] += store.replace_gym_sets(activity_id, parse_description(detail.get("description")))
            stats["details"] += 1
            if i % 25 == 0:
                log(f"  {i}/{len(todo)} gym sessions")
    except DailyLimitReached as e:
        stats["complete"] = False
        log(str(e))

    store.conn.commit()
    if stats["complete"]:
        with store.transaction():
            store.set_meta("last_sync", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    return stats


def reparse(store: Store) -> dict:
    """Re-run the parser over stored descriptions (no network)."""
    stats = {"activities": 0, "sets": 0}
    with store.transaction():
        for row in store.activities_with_description():
            n = store.replace_gym_sets(row["id"], parse_description(row["description"]))
            stats["activities"] += 1 if n else 0
            stats["sets"] += n
    return stats
