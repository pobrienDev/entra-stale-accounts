# entra-stale-accounts

[![Tests](https://github.com/pobrienDev/entra-stale-accounts/actions/workflows/tests.yml/badge.svg)](https://github.com/pobrienDev/entra-stale-accounts/actions/workflows/tests.yml) [![PyPI](https://img.shields.io/pypi/v/entra-stale-accounts)](https://pypi.org/project/entra-stale-accounts/) [![Python](https://img.shields.io/pypi/pyversions/entra-stale-accounts)](https://pypi.org/project/entra-stale-accounts/) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A read-only CLI that flags inactive Microsoft Entra ID (Azure AD) accounts past a configurable threshold. Point it at your own tenant, get a table or CSV of accounts that haven't signed in for N days — including accounts that have **never** signed in.

It never modifies anything: the only Microsoft Graph call it makes is a read of the user list. When Graph throttles (429), it waits out the `Retry-After` interval and retries instead of failing.

## Install

```
pip install entra-stale-accounts
```

On macOS (or any system where Python blocks global pip installs), use [pipx](https://pipx.pypa.io/) instead — it installs the CLI in its own isolated environment and puts the command on your PATH:

```
brew install pipx
pipx ensurepath
pipx install entra-stale-accounts
```

## Usage

```
# Every enabled account with no sign-in in 90+ days
entra-stale-accounts check --days 90

# Same, as CSV — redirect to a file to hand to a manager or import elsewhere
entra-stale-accounts check --days 90 --output csv > stale.csv

# Also include already-disabled accounts, for a fuller audit
entra-stale-accounts check --days 90 --include-disabled

# Add a column of each account's license SKUs — which stale accounts
# are still holding paid licenses you could reclaim?
entra-stale-accounts check --days 90 --licenses

# CSV with the license column — a reclaim list you can sort in Excel
entra-stale-accounts check --days 90 --licenses --output csv > stale-licenses.csv
```

```
$ entra-stale-accounts check --help
Usage: entra-stale-accounts check [OPTIONS]

  List enabled Entra ID accounts with no sign-in activity in the last N days.

Options:
  --days INTEGER          Inactivity threshold in days  [default: 90]
  --output [table|csv]    Output format  [default: table]
  --include-disabled      Also show already-disabled accounts
  --licenses              Add a column of assigned license SKUs (readable
                          names need Organization.Read.All)
  --env-file TEXT         Path to a .env file with tenant credentials
  --help                  Show this message and exit.
```

`--licenses` adds a `LICENSES` column to the table and a trailing `licenses` column to the CSV. An account with several SKUs lists them in one cell, separated by `; `.

Accounts that have never signed in are always flagged — no activity at all is at least as noteworthy as an old sign-in — and sort to the top of the results.

## Setup

The tool authenticates with your own Entra ID app registration via client credentials. Nothing is hardcoded — any tenant works.

### 1. Create an app registration

In [Entra admin center](https://entra.microsoft.com) → App registrations → New registration. No redirect URI needed.

Grant these **application** permissions under Microsoft Graph, then click **Grant admin consent**:

| Permission | Why |
|---|---|
| `User.Read.All` | Read the user list |
| `AuditLog.Read.All` | Read the `signInActivity` field |
| `Organization.Read.All` | *Optional* — lets `--licenses` show your tenant's own SKU names |

Without `Organization.Read.All`, `--licenses` still works: common SKUs resolve
through a built-in table and anything unknown shows as its raw GUID.

Create a client secret under Certificates & secrets.

### 2. Configure credentials

Copy `.env.example` to `.env` and fill in your values:

```
ENTRA_TENANT_ID=your-tenant-id
ENTRA_CLIENT_ID=your-app-client-id
ENTRA_CLIENT_SECRET=your-client-secret
```

Plain environment variables work too, and take precedence over the `.env` file.

### 3. The licensing requirement (read this)

The Graph field this tool depends on — `signInActivity` — requires a **Microsoft Entra ID P1 or P2 license** on the tenant, not just API permissions. Without it, the field comes back empty or the request is denied — that's a licensing wall, not a bug. P1 is included in Microsoft 365 Business Premium (not Basic) and is also available standalone.

Accounts whose `signInActivity` is missing are reported as `never` signed in — if *every* account shows `never`, suspect the license, not your users.

## Example output

```
USER PRINCIPAL NAME            DISPLAY NAME  ENABLED  LAST SIGN-IN  DAYS
-----------------------------  ------------  -------  ------------  -----
nina@contoso.onmicrosoft.com   Never Nina    true     never         never
sam@contoso.onmicrosoft.com    Stale Sam     true     2026-01-01    229

2 stale account(s) past a 90-day threshold.
```

## Troubleshooting

**"blocked by your organization's Device Guard policy" on Windows.** Smart App
Control (and enterprise App Control/WDAC policies) block the unsigned
`entra-stale-accounts.exe` launcher that pip generates. The tool itself still
runs fine through the signed Python interpreter — substitute the command name
and keep every flag the same:

```
python -m entra_stale_accounts.cli check --days 90
```

**CSV opens in Excel as one mangled column.** In Windows PowerShell, `>` writes
UTF-16, which Excel mis-detects. Redirect through `Out-File` instead:

```
entra-stale-accounts check --days 90 --output csv | Out-File stale.csv -Encoding utf8
```

**A `.env` in the current directory is ignored.** Fixed in 0.1.4 — upgrade with
`pip install --upgrade entra-stale-accounts`, or pass `--env-file .env`
explicitly on older versions.

**Every account shows `never`.** Almost always the licensing wall described in
[Setup](#3-the-licensing-requirement-read-this), not a bug.

## Development

```
git clone https://github.com/pobrienDev/entra-stale-accounts
cd entra-stale-accounts
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The test suite mocks every Graph call — it runs in milliseconds and never needs real credentials or a live tenant.

## Origin

Generalized from account-lifecycle automation built for a production Microsoft 365 environment: while automating provisioning, I kept needing to check for stale accounts, so the pattern became a standalone, general-purpose tool any admin can install.

## License

[MIT](LICENSE)
