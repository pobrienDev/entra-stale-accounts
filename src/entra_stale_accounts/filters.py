"""Pure functions: parsing sign-in activity, threshold filtering, output formatting.

Nothing in this module touches the network or reads configuration, which is what
makes it directly unit-testable without mocking anything.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

#: Column order used for both the table and the CSV output.
COLUMNS = ("userPrincipalName", "displayName", "accountEnabled", "lastSignIn", "daysInactive")

#: Fractional seconds in a timestamp, e.g. the ".1234567" in Graph's tick precision.
_FRACTION = re.compile(r"\.(\d+)")


@dataclass(frozen=True)
class StaleAccount:
    """One account that met the inactivity threshold."""

    id: str
    display_name: str
    user_principal_name: str
    account_enabled: bool
    last_sign_in: Optional[datetime]
    days_inactive: Optional[int]

    @property
    def never_signed_in(self) -> bool:
        return self.last_sign_in is None

    def as_row(self) -> dict[str, str]:
        """Flatten to the string values used by both output formats."""
        return {
            "userPrincipalName": self.user_principal_name,
            "displayName": self.display_name,
            "accountEnabled": "true" if self.account_enabled else "false",
            "lastSignIn": "never" if self.never_signed_in else self.last_sign_in.strftime("%Y-%m-%d"),
            "daysInactive": "never" if self.days_inactive is None else str(self.days_inactive),
        }


def parse_graph_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse a Graph ISO-8601 timestamp into an aware UTC datetime.

    Returns None for null/empty values. Graph emits a trailing "Z" that
    ``datetime.fromisoformat`` did not accept before Python 3.11, and the
    fractional-second precision varies, so both are normalized here.
    """
    if not value:
        return None

    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    # Graph emits up to 7 fractional digits (ticks), but fromisoformat before
    # Python 3.11 only accepts exactly 3 or 6. Pad or truncate to 6 so every
    # supported Python parses the same timestamps.
    match = _FRACTION.search(text)
    if match:
        digits = match.group(1)[:6].ljust(6, "0")
        text = text[: match.start(1)] + digits + text[match.end(1) :]

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def last_sign_in(user: dict[str, Any]) -> Optional[datetime]:
    """Pull lastSignInDateTime out of a Graph user object.

    A missing ``signInActivity`` block is treated the same as a null timestamp:
    no recorded interactive sign-in. Note that the block is absent entirely when
    the tenant lacks an Entra ID P1/P2 license (see README).
    """
    activity = user.get("signInActivity") or {}
    return parse_graph_datetime(activity.get("lastSignInDateTime"))


def days_since_last_sign_in(user: dict[str, Any], now: Optional[datetime] = None) -> Optional[int]:
    """Whole days since the user's last interactive sign-in, or None if never."""
    signed_in = last_sign_in(user)
    if signed_in is None:
        return None

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    return max(0, (reference - signed_in).days)


def to_stale_account(user: dict[str, Any], now: Optional[datetime] = None) -> StaleAccount:
    """Build a StaleAccount record from a raw Graph user object."""
    return StaleAccount(
        id=user.get("id", ""),
        display_name=user.get("displayName") or "",
        user_principal_name=user.get("userPrincipalName") or "",
        account_enabled=bool(user.get("accountEnabled")),
        last_sign_in=last_sign_in(user),
        days_inactive=days_since_last_sign_in(user, now=now),
    )


def find_stale_accounts(
    users: Iterable[dict[str, Any]],
    days: int,
    *,
    include_disabled: bool = False,
    now: Optional[datetime] = None,
) -> list[StaleAccount]:
    """Return accounts with no interactive sign-in in the last ``days`` days.

    Accounts that have never signed in are always considered stale — they have
    no activity at all, which is at least as noteworthy as an old sign-in.
    Disabled accounts are skipped unless ``include_disabled`` is set.

    Results are sorted most-inactive first, with never-signed-in accounts at the
    top, then alphabetically by UPN so the output is stable run to run.
    """
    if days < 0:
        raise ValueError("days must be zero or greater")

    reference = now or datetime.now(timezone.utc)
    stale: list[StaleAccount] = []

    for user in users:
        account = to_stale_account(user, now=reference)
        if not account.account_enabled and not include_disabled:
            continue
        if account.days_inactive is not None and account.days_inactive < days:
            continue
        stale.append(account)

    # Never-signed-in (None) gets a huge sentinel so it sorts as maximally stale.
    stale.sort(key=lambda a: (-(a.days_inactive if a.days_inactive is not None else 10**9),
                              a.user_principal_name.lower()))
    return stale


def to_csv(accounts: Iterable[StaleAccount]) -> str:
    """Render accounts as CSV text, header included even when there are no rows."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(COLUMNS), lineterminator="\n")
    writer.writeheader()
    for account in accounts:
        writer.writerow(account.as_row())
    return buffer.getvalue()


def to_table(accounts: Iterable[StaleAccount]) -> str:
    """Render accounts as a plain-text aligned table."""
    rows = [account.as_row() for account in accounts]
    if not rows:
        return ""

    headers = {
        "userPrincipalName": "USER PRINCIPAL NAME",
        "displayName": "DISPLAY NAME",
        "accountEnabled": "ENABLED",
        "lastSignIn": "LAST SIGN-IN",
        "daysInactive": "DAYS",
    }
    widths = {
        column: max(len(headers[column]), *(len(row[column]) for row in rows))
        for column in COLUMNS
    }

    def render(values: dict[str, str]) -> str:
        return "  ".join(values[column].ljust(widths[column]) for column in COLUMNS).rstrip()

    lines = [render(headers), render({c: "-" * widths[c] for c in COLUMNS})]
    lines.extend(render(row) for row in rows)
    return "\n".join(lines)
