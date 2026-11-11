"""Strava OAuth: one-time browser login plus automatic token refresh.

`stravadash auth` starts a tiny server on localhost, opens the Strava consent
page, and captures the redirect, so there is no code to copy by hand.
Set the app's "Authorization Callback Domain" to `localhost` on
https://www.strava.com/settings/api.
"""

from __future__ import annotations

import json
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from stravadash.config import Settings

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
SCOPE = "read,activity:read_all"


class AuthError(RuntimeError):
    pass


def _save(settings: Settings, tokens: dict) -> None:
    keep = {k: tokens[k] for k in ("access_token", "refresh_token", "expires_at") if k in tokens}
    athlete = tokens.get("athlete")
    if athlete:
        keep["athlete_id"] = athlete.get("id")
    elif (old := _load(settings)) and "athlete_id" in old:
        keep["athlete_id"] = old["athlete_id"]
    settings.token_path.write_text(json.dumps(keep, indent=2))
    settings.token_path.chmod(0o600)


def _load(settings: Settings) -> dict | None:
    if settings.token_path.exists():
        return json.loads(settings.token_path.read_text())
    return None


def _exchange(settings: Settings, **data: str) -> dict:
    client_id, client_secret = settings.require_credentials()
    resp = requests.post(
        TOKEN_URL,
        data={"client_id": client_id, "client_secret": client_secret, **data},
        timeout=30,
    )
    if resp.status_code != 200:
        raise AuthError(f"Strava token request failed ({resp.status_code}): {resp.text}")
    tokens = resp.json()
    _save(settings, tokens)
    return tokens


def _bind(port: int) -> HTTPServer:
    """Listen on `port`, or any free port if it's taken (Strava only checks the domain)."""
    for candidate in (port, 0):
        try:
            return HTTPServer(("localhost", candidate), BaseHTTPRequestHandler)
        except OSError:
            continue
    raise AuthError("Couldn't open a local port for the Strava login.")


def authorize(settings: Settings, open_browser: bool = True) -> dict:
    """Run the browser OAuth flow and store tokens."""
    client_id, _ = settings.require_credentials()
    server = _bind(settings.auth_port)
    redirect_uri = f"http://localhost:{server.server_address[1]}/callback"
    url = AUTHORIZE_URL + "?" + urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "approval_prompt": "auto",
            "scope": SCOPE,
        }
    )
    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server API)
            query = parse_qs(urlparse(self.path).query)
            if "error" in query:
                result["error"] = query["error"][0]
            elif "code" in query:
                result["code"] = query["code"][0]
                result["scope"] = query.get("scope", [""])[0]
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = "Strava connected. You can close this tab." if "code" in result else "Authorization failed."
            self.wfile.write(f"<h2>{msg}</h2>".encode())

        def log_message(self, *args):  # keep the terminal quiet
            pass

    server.RequestHandlerClass = Handler
    print(f"Opening Strava to authorize. If the browser doesn't open, visit:\n  {url}")
    if open_browser:
        webbrowser.open(url)
    while not result:
        server.handle_request()
    server.server_close()

    if "error" in result:
        raise AuthError(f"Authorization was denied: {result['error']}")
    if "activity:read_all" not in result.get("scope", ""):
        raise AuthError("Please tick 'View data about your private activities' so gym workouts are readable.")
    return _exchange(settings, code=result["code"], grant_type="authorization_code")


def get_access_token(settings: Settings) -> str:
    tokens = _load(settings)
    if not tokens:
        raise AuthError("Not connected to Strava yet. Run: python -m stravadash auth")
    if tokens["expires_at"] - 60 < time.time():
        tokens = _exchange(settings, grant_type="refresh_token", refresh_token=tokens["refresh_token"])
    return tokens["access_token"]
