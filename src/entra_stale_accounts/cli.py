"""Typer application: the `check` command and its flags."""

from __future__ import annotations

from enum import Enum
from typing import Optional

import typer

from . import __version__
from .filters import find_stale_accounts, to_csv, to_table
from .graph import GraphError, fetch_users


class OutputFormat(str, Enum):
    """Supported rendering formats for the result set."""

    table = "table"
    csv = "csv"


# rich_markup_mode=None keeps --help as plain text rather than a boxed layout.
app = typer.Typer(
    name="entra-stale-accounts",
    help="Read-only CLI that flags inactive Microsoft Entra ID accounts.",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"entra-stale-accounts {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Read-only CLI that flags inactive Microsoft Entra ID accounts."""


@app.command()
def check(
    days: int = typer.Option(90, "--days", help="Inactivity threshold in days", min=0),
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", help="Output format", case_sensitive=False
    ),
    include_disabled: bool = typer.Option(
        False, "--include-disabled", help="Also show already-disabled accounts"
    ),
    env_file: Optional[str] = typer.Option(
        None, "--env-file", help="Path to a .env file with tenant credentials"
    ),
) -> None:
    """List enabled Entra ID accounts with no sign-in activity in the last N days.

    Credentials are read from ENTRA_TENANT_ID, ENTRA_CLIENT_ID and
    ENTRA_CLIENT_SECRET (or a .env file alongside them). Nothing in the tenant is
    modified; the only Graph call made is a read of the user list.
    """
    try:
        users = fetch_users(env_file=env_file)
    except GraphError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    accounts = find_stale_accounts(users, days=days, include_disabled=include_disabled)

    if output is OutputFormat.csv:
        # Header is emitted even for an empty result, so the output stays valid CSV.
        typer.echo(to_csv(accounts), nl=False)
        return

    if not accounts:
        scope = "accounts" if include_disabled else "enabled accounts"
        typer.echo(f"No stale {scope} found (threshold: {days} days).")
        return

    typer.echo(to_table(accounts))
    typer.echo("")
    typer.echo(f"{len(accounts)} stale account(s) past a {days}-day threshold.")


if __name__ == "__main__":  # pragma: no cover
    app()
