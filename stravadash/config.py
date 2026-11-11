"""Settings loaded from the environment (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    client_id: str | None
    client_secret: str | None
    data_dir: Path
    auth_port: int

    @property
    def db_path(self) -> Path:
        return self.data_dir / "strava.db"

    @property
    def token_path(self) -> Path:
        return self.data_dir / "tokens.json"

    def require_credentials(self) -> tuple[str, str]:
        if not self.client_id or not self.client_secret:
            raise SystemExit(
                "STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET must be set "
                "(copy .env.example to .env and fill them in)."
            )
        return self.client_id, self.client_secret


def load_settings() -> Settings:
    load_dotenv()
    data_dir = Path(os.getenv("STRAVADASH_DATA_DIR", "data")).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        client_id=os.getenv("STRAVA_CLIENT_ID"),
        client_secret=os.getenv("STRAVA_CLIENT_SECRET"),
        data_dir=data_dir,
        auth_port=int(os.getenv("STRAVADASH_AUTH_PORT", "8765")),
    )
