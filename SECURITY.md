# Security Policy

## Reporting a vulnerability

Please report vulnerabilities privately via GitHub's
[Report a vulnerability](https://github.com/pobrienDev/entra-stale-accounts/security/advisories/new)
form rather than opening a public issue. You'll get an acknowledgement within a
few days, and a fix will be prioritized over any other work on this project.

## Supported versions

Only the latest release published to [PyPI](https://pypi.org/project/entra-stale-accounts/)
receives security fixes. Upgrade with `pip install --upgrade entra-stale-accounts`.

## Security posture

This tool is deliberately read-only:

- The only Microsoft Graph calls it makes are GETs (`/users`, and
  `/subscribedSkus` when `--licenses` is used), plus the OAuth token request.
  Nothing in a tenant is ever created, modified, or deleted.
- Credentials are read from environment variables or a local `.env` file and
  sent only to Microsoft's endpoints; they are never logged or echoed.
- CSV output neutralizes formula injection (values that Excel would execute
  are prefixed to render as text), since display names are end-user-controlled.

Things that are *out of scope*: the security of your Entra app registration
(scope its permissions minimally and protect its client secret), and the
handling of generated reports, which contain directory data about your tenant.
