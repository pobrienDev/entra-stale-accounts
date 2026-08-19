"""Shared fake Graph data. No test in this suite makes a network call."""

from datetime import datetime, timezone

import pytest

#: Fixed "now" so day counts in tests never drift with the wall clock.
NOW = datetime(2026, 8, 18, 12, 0, 0, tzinfo=timezone.utc)


def graph_user(
    *,
    user_id="00000000-0000-0000-0000-000000000000",
    display_name="Test User",
    upn="test@contoso.onmicrosoft.com",
    enabled=True,
    last_sign_in="2026-08-01T09:00:00Z",
    last_non_interactive="2026-08-01T09:00:00Z",
    include_activity=True,
):
    """Build one user object in the shape Graph's /users endpoint returns."""
    user = {
        "id": user_id,
        "displayName": display_name,
        "userPrincipalName": upn,
        "accountEnabled": enabled,
    }
    if include_activity:
        user["signInActivity"] = {
            "lastSignInDateTime": last_sign_in,
            "lastNonInteractiveSignInDateTime": last_non_interactive,
        }
    return user


@pytest.fixture
def now():
    return NOW


@pytest.fixture
def users():
    """One clearly stale account, one clearly active, one that never signed in."""
    return [
        graph_user(
            user_id="1",
            display_name="Stale Sam",
            upn="sam@contoso.onmicrosoft.com",
            last_sign_in="2026-01-01T08:00:00Z",  # 229 days before NOW
        ),
        graph_user(
            user_id="2",
            display_name="Active Ada",
            upn="ada@contoso.onmicrosoft.com",
            last_sign_in="2026-08-15T08:00:00Z",  # 3 days before NOW
        ),
        graph_user(
            user_id="3",
            display_name="Never Nina",
            upn="nina@contoso.onmicrosoft.com",
            last_sign_in=None,
            last_non_interactive=None,
        ),
    ]
