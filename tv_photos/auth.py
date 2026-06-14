"""Desktop OAuth for the Google Photos Library API, with token caching + scope upgrade."""
from __future__ import annotations

import json
import os
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .gphotos import SCOPES, GooglePhotosClient


def write_private(path: Path, text: str) -> None:
    """Write a secret (token / client secret) restricted to the owner (0600)."""
    path.write_text(text)
    os.chmod(path, 0o600)


def token_has_scopes(token: Path, required) -> bool:
    """True only if the token file itself records all `required` scopes.

    We read the file's own `scopes` rather than trusting `Credentials.scopes`,
    because `from_authorized_user_file(path, scopes)` adopts the *requested*
    scopes — which would make any scope check trivially pass.
    """
    if not token.exists():
        return False
    try:
        stored = set(json.loads(token.read_text()).get("scopes") or [])
    except (ValueError, OSError):
        return False
    return set(required).issubset(stored)


def get_credentials(client_secret: Path, token: Path, scopes=SCOPES) -> Credentials:
    creds: Credentials | None = None
    if token_has_scopes(token, scopes):
        creds = Credentials.from_authorized_user_file(str(token), scopes)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            write_private(token, creds.to_json())
            return creds
        except RefreshError:
            creds = None  # fall through to a fresh interactive flow

    if not client_secret.exists():
        raise FileNotFoundError(
            f"Missing {client_secret}. Put your OAuth 'Desktop app' client_secret.json there."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), scopes)
    creds = flow.run_local_server(port=0)
    missing = set(scopes) - set(creds.scopes or [])
    if missing:
        raise PermissionError(
            "Authorization is missing required permissions: "
            + ", ".join(sorted(missing))
            + ". Re-run and approve all requested permissions."
        )
    write_private(token, creds.to_json())
    return creds


def make_client(client_secret: Path, token: Path) -> GooglePhotosClient:
    creds = get_credentials(client_secret, token)
    return GooglePhotosClient(AuthorizedSession(creds))
