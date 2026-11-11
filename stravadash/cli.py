"""Command line entry point: python -m stravadash <command>."""

from __future__ import annotations

import argparse

from stravadash import auth
from stravadash.client import StravaClient
from stravadash.config import load_settings
from stravadash.store import Store
from stravadash.sync import GYM_SPORT_TYPES, reparse, sync


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except (auth.AuthError, KeyboardInterrupt) as e:
        print(e or "Stopped.")
        return 1


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stravadash", description="Personal Strava + Hevy dashboard")
    sub = parser.add_subparsers(dest="command", required=True)

    p_auth = sub.add_parser("auth", help="connect your Strava account (one time)")
    p_auth.add_argument("--no-browser", action="store_true", help="print the URL instead of opening it")

    p_sync = sub.add_parser("sync", help="download new activities from Strava")
    p_sync.add_argument("--full", action="store_true", help="re-list every activity, not just new ones")

    sub.add_parser("reparse", help="re-parse stored Hevy descriptions without hitting Strava")
    sub.add_parser("status", help="show what's in the local database")

    p_ex = sub.add_parser("exercises", help="list parsed exercises and how often they appear")
    p_ex.add_argument("--limit", type=int, default=50)

    sub.add_parser("unparsed", help="show gym sessions whose description produced no sets")

    p_serve = sub.add_parser("serve", help="open the dashboard at http://localhost:8050")
    p_serve.add_argument("--port", type=int, default=8050)  # 5000 is taken by AirPlay on macOS
    p_serve.add_argument("--demo", action="store_true", help="use generated sample data instead of your own")

    args = parser.parse_args(argv)
    settings = load_settings()

    if args.command == "auth":
        tokens = auth.authorize(settings, open_browser=not args.no_browser)
        print(f"Connected to Strava (athlete {tokens.get('athlete', {}).get('id', '?')}). Tokens saved to {settings.token_path}.")
        return 0

    if args.command == "serve":
        return _serve(settings, args.port, args.demo)

    store = Store(settings.db_path)
    try:
        if args.command == "sync":
            client = StravaClient(lambda: auth.get_access_token(settings))
            stats = sync(store, client, full=args.full)
            print(f"Done: {stats['listed']} listed, {stats['details']} gym sessions read, {stats['sets']} sets parsed.")
            if not stats["complete"]:
                print("Sync stopped early because of Strava's daily limit; run it again tomorrow to finish.")
        elif args.command == "reparse":
            stats = reparse(store)
            print(f"Parsed {stats['sets']} sets from {stats['activities']} workouts.")
        elif args.command == "status":
            print(f"Database: {settings.db_path}")
            print(f"Last full sync: {store.get_meta('last_sync') or 'never'}")
            for sport, n in store.counts_by_sport():
                print(f"  {sport:<32} {n:>5}")
            g = store.gym_summary()
            print(f"Gym: {g['workouts']} workouts, {g['exercises']} distinct exercises, {g['sets']} sets")
        elif args.command == "exercises":
            rows = store.conn.execute(
                "SELECT exercise, COUNT(DISTINCT activity_id) sessions, COUNT(*) sets FROM gym_sets "
                "GROUP BY exercise ORDER BY sessions DESC LIMIT ?", (args.limit,)
            )
            for r in rows:
                print(f"{r['sessions']:>4} sessions {r['sets']:>5} sets  {r['exercise']}")
        elif args.command == "unparsed":
            q = ",".join("?" * len(GYM_SPORT_TYPES))
            rows = store.conn.execute(
                f"SELECT a.id, a.start_date_local, a.name, a.description FROM activities a "
                f"WHERE a.sport_type IN ({q}) AND a.detail_fetched=1 "
                f"AND NOT EXISTS (SELECT 1 FROM gym_sets s WHERE s.activity_id=a.id) "
                f"ORDER BY a.start_date DESC", sorted(GYM_SPORT_TYPES)
            ).fetchall()
            print(f"{len(rows)} gym sessions with no parsed sets")
            for r in rows[:20]:
                preview = (r["description"] or "(no description)").replace("\n", " | ")[:120]
                print(f"  {r['start_date_local'][:10]}  {r['name']}: {preview}")
    finally:
        store.close()
    return 0


def _serve(settings, port: int, demo: bool) -> int:
    from stravadash.web import create_app

    db_path = settings.db_path
    if demo:
        from stravadash.demo import populate

        db_path = settings.data_dir / "demo.db"
        db_path.unlink(missing_ok=True)
        populate(Store(db_path))
    elif not db_path.exists():
        print("No data yet. Run `stravadash auth` and `stravadash sync` first, or try `stravadash serve --demo`.")
        return 1
    print(f"Dashboard running at http://localhost:{port}  (Ctrl+C to stop)")
    create_app(db_path, units=settings.units, weekly_target=settings.weekly_target).run(port=port)
    return 0
