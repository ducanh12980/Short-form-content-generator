#!/usr/bin/env python3
"""One-time OAuth setup for Google Drive personal account upload."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.publish.drive import DRIVE_SCOPES


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_REPO_ROOT / ".env")


def main() -> None:
    _load_env()

    client_id = os.environ.get("GOOGLE_DRIVE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_DRIVE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("Set GOOGLE_DRIVE_CLIENT_ID and GOOGLE_DRIVE_CLIENT_SECRET in .env first.")
        print()
        print("Steps:")
        print("1. Open https://console.cloud.google.com/apis/credentials")
        print("2. Create OAuth client ID → Application type: Desktop app")
        print("3. Enable Google Drive API for the project")
        print("4. Copy Client ID and Client Secret into .env")
        raise SystemExit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise SystemExit(
            "Install google-auth-oauthlib first: pip install google-auth-oauthlib"
        ) from exc

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uris": ["http://localhost"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        DRIVE_SCOPES,
    )
    print("Opening browser for Google sign-in...")
    creds = flow.run_local_server(port=0)

    print()
    print("Add this line to your .env file:")
    print(f"GOOGLE_DRIVE_REFRESH_TOKEN={creds.refresh_token}")
    print()
    print("Then remove GOOGLE_DRIVE_CREDENTIALS_JSON (service account) if present.")
    print("Keep GOOGLE_DRIVE_FOLDER_ID pointing to your target folder.")


if __name__ == "__main__":
    main()
