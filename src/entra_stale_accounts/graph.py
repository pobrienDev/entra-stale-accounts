"""Microsoft Graph authentication and the user-list call.

Credentials are read from the environment (or a local .env file) so the tool can
be pointed at any tenant without touching the source. Nothing here modifies
anything in the tenant — the only Graph call made is a GET against /users.
"""

from __future__ import annotations

import os
from typing import Any, Iterator, Optional

import requests
from dotenv import load_dotenv

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

#: signInActivity is not returned by default — it has to be asked for explicitly.
USER_SELECT_FIELDS = "id,displayName,userPrincipalName,accountEnabled,signInActivity"

#: Graph caps $top at 999 for /users; fewer, larger pages means fewer round trips.
PAGE_SIZE = 999

DEFAULT_TIMEOUT = 30


class GraphError(RuntimeError):
    """Raised when Graph or the token endpoint returns something unusable."""


class MissingCredentialsError(GraphError):
    """Raised when the tenant/client credentials are not configured."""


class Credentials:
    """Client-credentials app registration details for one tenant."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret


def load_credentials(env_file: Optional[str] = None) -> Credentials:
    """Read credentials from the environment, loading a .env file if present.

    Real environment variables win over .env values, so CI and shell exports
    override the local file rather than the other way round.
    """
    load_dotenv(dotenv_path=env_file, override=False)

    values = {
        "ENTRA_TENANT_ID": os.getenv("ENTRA_TENANT_ID", "").strip(),
        "ENTRA_CLIENT_ID": os.getenv("ENTRA_CLIENT_ID", "").strip(),
        "ENTRA_CLIENT_SECRET": os.getenv("ENTRA_CLIENT_SECRET", "").strip(),
    }

    missing = sorted(name for name, value in values.items() if not value)
    if missing:
        raise MissingCredentialsError(
            "Missing credentials: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill in your app registration details."
        )

    return Credentials(
        tenant_id=values["ENTRA_TENANT_ID"],
        client_id=values["ENTRA_CLIENT_ID"],
        client_secret=values["ENTRA_CLIENT_SECRET"],
    )


def get_access_token(credentials: Credentials, *, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Exchange the client secret for an app-only Graph access token."""
    response = requests.post(
        TOKEN_URL_TEMPLATE.format(tenant_id=credentials.tenant_id),
        data={
            "grant_type": "client_credentials",
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scope": GRAPH_SCOPE,
        },
        timeout=timeout,
    )

    if response.status_code != 200:
        raise GraphError(f"Token request failed ({response.status_code}): {_error_detail(response)}")

    token = response.json().get("access_token")
    if not token:
        raise GraphError("Token endpoint returned no access_token.")
    return token


def iter_users(access_token: str, *, timeout: int = DEFAULT_TIMEOUT) -> Iterator[dict[str, Any]]:
    """Yield every user in the tenant, following Graph's @odata.nextLink paging."""
    url: Optional[str] = f"{GRAPH_BASE_URL}/users?$select={USER_SELECT_FIELDS}&$top={PAGE_SIZE}"
    headers = {"Authorization": f"Bearer {access_token}", "ConsistencyLevel": "eventual"}

    while url:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code != 200:
            raise GraphError(f"User query failed ({response.status_code}): {_error_detail(response)}")

        payload = response.json()
        for user in payload.get("value", []):
            yield user

        url = payload.get("@odata.nextLink")


def fetch_users(
    credentials: Optional[Credentials] = None,
    *,
    env_file: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Authenticate and return every user object, with sign-in activity included.

    This is the single seam the CLI tests patch — mock this and no network call
    is ever made.
    """
    credentials = credentials or load_credentials(env_file=env_file)
    token = get_access_token(credentials, timeout=timeout)
    return list(iter_users(token, timeout=timeout))


def _error_detail(response: "requests.Response") -> str:
    """Pull Graph's error message out of the body, falling back to raw text."""
    try:
        payload = response.json()
    except ValueError:
        return response.text[:200]

    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error)
    if isinstance(error, str):
        # The token endpoint uses a flat error/error_description shape.
        return str(payload.get("error_description") or error)
    return str(payload)[:200]
