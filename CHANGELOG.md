# Changelog

All notable changes to this project are documented here. Versions follow
[Semantic Versioning](https://semver.org/) and the format is based on
[Keep a Changelog](https://keepachangelog.com/).

## [0.1.3] - 2026-08-19

### Added
- This changelog, git tags and GitHub Releases for all published versions.
- Releases are now published to PyPI automatically via trusted publishing
  when a version tag is pushed; no functional changes to the CLI.

## [0.1.2] - 2026-08-19

### Fixed
- Timestamps with Graph's 7-digit ("ticks") fractional-second precision failed
  to parse on Python 3.9 and 3.10, causing affected accounts to be misreported
  as never signed in. Fractional seconds are now normalized before parsing.

### Added
- Graph throttling (HTTP 429) is now handled: the `Retry-After` interval is
  honored and the request retried up to 3 times before an error is raised.
- CI: the test suite runs on Python 3.9–3.13 for every push and pull request.

## [0.1.1] - 2026-08-19

### Fixed
- The user query requested pages of 999, but Graph caps the page size at 120
  when `signInActivity` is selected, so the request failed with a 400 against
  real tenants. The page size is now 120.

## [0.1.0] - 2026-08-19

### Added
- Initial release: `check` command listing enabled Entra ID accounts with no
  interactive sign-in past a configurable threshold (`--days`), including
  accounts that have never signed in.
- Table and CSV output (`--output`), optional inclusion of disabled accounts
  (`--include-disabled`), credentials via environment or `.env` file.

[0.1.3]: https://github.com/pobrienDev/entra-stale-accounts/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/pobrienDev/entra-stale-accounts/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/pobrienDev/entra-stale-accounts/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/pobrienDev/entra-stale-accounts/releases/tag/v0.1.0
