"""Unit tests for the pure filtering logic. No API calls, no mocking needed."""

from datetime import datetime, timezone

import pytest

from entra_stale_accounts.filters import (
    days_since_last_sign_in,
    find_stale_accounts,
    last_sign_in,
    parse_graph_datetime,
    to_csv,
    to_table,
)

from .conftest import graph_user


class TestParseGraphDatetime:
    def test_parses_zulu_timestamp_as_utc(self):
        parsed = parse_graph_datetime("2026-05-12T14:32:00Z")
        assert parsed == datetime(2026, 5, 12, 14, 32, tzinfo=timezone.utc)

    def test_parses_fractional_seconds(self):
        parsed = parse_graph_datetime("2026-05-12T14:32:00.1234567Z")
        assert parsed.year == 2026 and parsed.tzinfo is timezone.utc

    def test_parses_short_fractional_seconds(self):
        # Pre-3.11 fromisoformat also rejects 1-2 and 4-5 digit fractions.
        parsed = parse_graph_datetime("2026-05-12T14:32:00.1Z")
        assert parsed == datetime(2026, 5, 12, 14, 32, 0, 100000, tzinfo=timezone.utc)

    def test_parses_explicit_offset(self):
        parsed = parse_graph_datetime("2026-05-12T16:32:00+02:00")
        assert parsed == datetime(2026, 5, 12, 14, 32, tzinfo=timezone.utc)

    @pytest.mark.parametrize("value", [None, "", "   ", "not-a-date"])
    def test_returns_none_for_unusable_values(self, value):
        assert parse_graph_datetime(value) is None


class TestSignInExtraction:
    def test_missing_sign_in_activity_block_is_treated_as_never(self):
        # This is what a tenant without an Entra ID P1/P2 license returns.
        assert last_sign_in(graph_user(include_activity=False)) is None

    def test_null_last_sign_in_is_treated_as_never(self):
        assert last_sign_in(graph_user(last_sign_in=None)) is None

    def test_days_since_last_sign_in_counts_whole_days(self, now):
        user = graph_user(last_sign_in="2026-07-19T12:00:00Z")
        assert days_since_last_sign_in(user, now=now) == 30

    def test_days_is_none_when_never_signed_in(self, now):
        assert days_since_last_sign_in(graph_user(last_sign_in=None), now=now) is None

    def test_future_timestamp_clamps_to_zero(self, now):
        user = graph_user(last_sign_in="2026-12-01T12:00:00Z")
        assert days_since_last_sign_in(user, now=now) == 0


class TestFindStaleAccounts:
    def test_flags_only_the_stale_and_never_signed_in(self, users, now):
        stale = find_stale_accounts(users, days=90, now=now)
        assert [a.user_principal_name for a in stale] == [
            "nina@contoso.onmicrosoft.com",
            "sam@contoso.onmicrosoft.com",
        ]

    def test_never_signed_in_sorts_first(self, users, now):
        stale = find_stale_accounts(users, days=90, now=now)
        assert stale[0].never_signed_in is True

    def test_threshold_boundary_is_inclusive(self, now):
        # Exactly 90 days inactive counts as stale at --days 90.
        user = graph_user(last_sign_in="2026-05-20T12:00:00Z")
        assert days_since_last_sign_in(user, now=now) == 90
        assert len(find_stale_accounts([user], days=90, now=now)) == 1
        assert len(find_stale_accounts([user], days=91, now=now)) == 0

    def test_disabled_accounts_are_excluded_by_default(self, now):
        disabled = graph_user(enabled=False, last_sign_in="2026-01-01T08:00:00Z")
        assert find_stale_accounts([disabled], days=90, now=now) == []

    def test_include_disabled_brings_them_back(self, now):
        disabled = graph_user(enabled=False, last_sign_in="2026-01-01T08:00:00Z")
        stale = find_stale_accounts([disabled], days=90, include_disabled=True, now=now)
        assert len(stale) == 1 and stale[0].account_enabled is False

    def test_zero_results_when_everyone_is_active(self, users, now):
        assert find_stale_accounts(users[1:2], days=90, now=now) == []

    def test_empty_input_returns_empty_list(self, now):
        assert find_stale_accounts([], days=90, now=now) == []

    def test_negative_threshold_is_rejected(self, now):
        with pytest.raises(ValueError):
            find_stale_accounts([], days=-1, now=now)


class TestFormatting:
    def test_csv_has_header_and_one_row_per_account(self, users, now):
        stale = find_stale_accounts(users, days=90, now=now)
        lines = to_csv(stale).strip().splitlines()
        assert lines[0] == "userPrincipalName,displayName,accountEnabled,lastSignIn,daysInactive"
        assert len(lines) == 3

    def test_csv_header_is_emitted_for_zero_results(self):
        assert to_csv([]).strip().splitlines() == [
            "userPrincipalName,displayName,accountEnabled,lastSignIn,daysInactive"
        ]

    def test_csv_renders_never_signed_in_accounts(self, users, now):
        stale = find_stale_accounts(users, days=90, now=now)
        assert "nina@contoso.onmicrosoft.com,Never Nina,true,never,never" in to_csv(stale)

    def test_table_is_empty_string_for_zero_results(self):
        assert to_table([]) == ""

    def test_table_includes_a_header_row(self, users, now):
        table = to_table(find_stale_accounts(users, days=90, now=now))
        assert table.splitlines()[0].startswith("USER PRINCIPAL NAME")
        assert "sam@contoso.onmicrosoft.com" in table
