# entra-stale-accounts

[![PyPI](https://img.shields.io/pypi/v/entra-stale-accounts)](https://pypi.org/project/entra-stale-accounts/) [![Python](https://img.shields.io/pypi/pyversions/entra-stale-accounts)](https://pypi.org/project/entra-stale-accounts/) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A read-only CLI that flags inactive Microsoft Entra ID (Azure AD) accounts past a configurable threshold. Point it at your own tenant, get a table or CSV of accounts that haven't signed in for N days — including accounts that have **never** signed in.

It never modifies anything: the only Microsoft Graph call it makes is a read of the user list.

## Install

```
pip install entra-stale-accounts
```

## Usage

```
# Every enabled account with no sign-in in 90+ days
entra-stale-accounts check --days 90

# Same, as CSV — redirect to a file to hand to a manager or import elsewhere
entra-stale-accounts check --days 90 --output csv > stale.csv

# Also include already-disabled accounts, for a fuller audit
entra-stale-accounts check --days 90 --include-disabled
```

```
$ entra-stale-accounts check --help
Usage: entra-stale-accounts check [OPTIONS]

  List enabled Entra ID accounts with no sign-in activity in the last N days.

Options:
  --days INTEGER          Inactivity threshold in days  [default: 90]
  --output [table|csv]    Output format  [default: table]
  --include-disabled      Also show already-disabled accounts
  --env-file TEXT         Path to a .env file with tenant credentials
  --help                  Show this message and exit.
```

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
