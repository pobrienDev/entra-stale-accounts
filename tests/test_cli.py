"""CliRunner tests for command output and exit codes. The Graph API is mocked."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from entra_stale_accounts.cli import app
from entra_stale_accounts.graph import GraphError, MissingCredentialsError

from .conftest import graph_user

runner = CliRunner()


def iso_days_ago(days: int) -> str:
    """A Graph-shaped timestamp N days before the real now.

    Using a relative date keeps these tests from going stale as the clock moves.
    """
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def fake_users():
    return [
        graph_user(
            user_id="1",
            display_name="Stale Sam",
            upn="sam@contoso.onmicrosoft.com",
            last_sign_in=iso_days_ago(200),
        ),
        graph_user(
            user_id="2",
            display_name="Active Ada",
            upn="ada@contoso.onmicrosoft.com",
            last_sign_in=iso_days_ago(3),
        ),
        graph_user(
            user_id="3",
            display_name="Never Nina",
            upn="nina@contoso.onmicrosoft.com",
            last_sign_in=None,
            last_non_interactive=None,
        ),
        graph_user(
            user_id="4",
            display_name="Disabled Dan",
            upn="dan@contoso.onmicrosoft.com",
            enabled=False,
            last_sign_in=iso_days_ago(400),
        ),
    ]


def all_output(result) -> str:
    """Combine stdout and stderr across click versions that split them."""
    try:
        return result.output + (result.stderr or "")
    except ValueError:  # click <8.2 with mix_stderr=True
        return result.output


class TestCheckCommand:
    def test_table_output_lists_stale_accounts_only(self, fake_users):
        with patch("entra_stale_accounts.cli.fetch_users", return_value=fake_users):
            result = runner.invoke(app, ["check", "--days", "90"])

        assert result.exit_code == 0
        assert "sam@contoso.onmicrosoft.com" in result.output
        assert "nina@contoso.onmicrosoft.com" in result.output
        assert "ada@contoso.onmicrosoft.com" not in result.output
        assert "dan@contoso.onmicrosoft.com" not in result.output
        assert "2 stale account(s)" in result.output

    def test_include_disabled_adds_disabled_accounts(self, fake_users):
        with patch("entra_stale_accounts.cli.fetch_users", return_value=fake_users):
            result = runner.invoke(app, ["check", "--days", "90", "--include-disabled"])

        assert result.exit_code == 0
        assert "dan@contoso.onmicrosoft.com" in result.output
        assert "3 stale account(s)" in result.output

    def test_zero_results_exits_cleanly_with_a_message(self, fake_users):
        with patch("entra_stale_accounts.cli.fetch_users", return_value=[fake_users[1]]):
            result = runner.invoke(app, ["check", "--days", "90"])

        assert result.exit_code == 0
        assert "No stale enabled accounts found" in result.output

    def test_empty_tenant_exits_cleanly(self):
        with patch("entra_stale_accounts.cli.fetch_users", return_value=[]):
            result = runner.invoke(app, ["check"])

        assert result.exit_code == 0
        assert "No stale" in result.output

    def test_default_threshold_is_90_days(self, fake_users):
        with patch("entra_stale_accounts.cli.fetch_users", return_value=fake_users):
            default_run = runner.invoke(app, ["check"])
            explicit_run = runner.invoke(app, ["check", "--days", "90"])

        assert default_run.output == explicit_run.output

    def test_higher_threshold_narrows_results(self, fake_users):
        with patch("entra_stale_accounts.cli.fetch_users", return_value=fake_users):
            result = runner.invoke(app, ["check", "--days", "300"])

        assert result.exit_code == 0
        assert "sam@contoso.onmicrosoft.com" not in result.output
        assert "nina@contoso.onmicrosoft.com" in result.output


class TestCsvOutput:
    def test_csv_output_is_parseable(self, fake_users):
        with patch("entra_stale_accounts.cli.fetch_users", return_value=fake_users):
            result = runner.invoke(app, ["check", "--days", "90", "--output", "csv"])

        lines = result.output.strip().splitlines()
        assert result.exit_code == 0
        assert lines[0] == "userPrincipalName,displayName,accountEnabled,lastSignIn,daysInactive"
        assert len(lines) == 3
        assert "Stale Sam" in result.output

    def test_csv_output_writes_a_header_for_zero_results(self, fake_users):
        with patch("entra_stale_accounts.cli.fetch_users", return_value=[fake_users[1]]):
            result = runner.invoke(app, ["check", "--output", "csv"])

        assert result.exit_code == 0
        assert result.output.strip() == (
            "userPrincipalName,displayName,accountEnabled,lastSignIn,daysInactive"
        )

    def test_csv_output_can_be_redirected_to_a_file(self, tmp_path, fake_users):
        with patch("entra_stale_accounts.cli.fetch_users", return_value=fake_users):
            result = runner.invoke(app, ["check", "--output", "csv"])

        target = tmp_path / "stale.csv"
        target.write_text(result.output)
        assert target.read_text().splitlines()[0].startswith("userPrincipalName")

    def test_invalid_output_format_is_rejected(self, fake_users):
        with patch("entra_stale_accounts.cli.fetch_users", return_value=fake_users):
            result = runner.invoke(app, ["check", "--output", "yaml"])

        assert result.exit_code != 0


class TestErrorHandling:
    def test_missing_credentials_exit_code_is_1(self):
        error = MissingCredentialsError("Missing credentials: ENTRA_TENANT_ID")
        with patch("entra_stale_accounts.cli.fetch_users", side_effect=error):
            result = runner.invoke(app, ["check"])

        assert result.exit_code == 1
        assert "Missing credentials" in all_output(result)

    def test_graph_failure_exit_code_is_1(self):
        error = GraphError("User query failed (403): Insufficient privileges.")
        with patch("entra_stale_accounts.cli.fetch_users", side_effect=error):
            result = runner.invoke(app, ["check"])

        assert result.exit_code == 1
        assert "Insufficient privileges" in all_output(result)

    def test_negative_days_is_rejected_by_the_cli(self):
        result = runner.invoke(app, ["check", "--days", "-5"])
        assert result.exit_code != 0


class TestHelpAndVersion:
    def test_check_help_documents_every_flag(self):
        result = runner.invoke(app, ["check", "--help"])

        assert result.exit_code == 0
        for expected in ("--days", "--output", "--include-disabled", "--help"):
            assert expected in result.output
        assert "Inactivity threshold in days" in result.output

    def test_version_flag_prints_the_version(self):
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "entra-stale-accounts" in result.output
