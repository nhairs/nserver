# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [3.0.0](https://github.com/nhairs/nserver/compare/v2.0.0...dev) - UNRELEASED

!!! tip
    Version `3.0.0` represents a large incompatible refactor of `nserver` with version `2.0.0` considered a ["misfire"](https://github.com/nhairs/nserver/pull/4#issuecomment-2254354192). If you have been using functionality from `2.0.0` or the development branch you should expect a large number of breaking changes.

### Added
- Add Python 3.13 support
- Generalised CLI interface for running applications; see `nserver --help`.
  - Implemented in `nserver.cli`.
- `nserver.application` classes that focus on running a given server instance.
  - This lays the ground work for different ways of running servers in the future; e.g. using threads.
- `nserver.server.RawNameServer` that handles `RawMiddleware` including exception handling.

### Removed
- Drop Python 3.7 support
- `nserver.server.SubServer` has been removed.
  - `NameServer` instances can now be registered to other `NameServer` instances.

### Changed
- Refactored `nserver.server.NameServer`
  - "Raw" functionality has been removed. This has been moved to the `nserver.server.RawNameServer`.
  - "Transport" and other related "Application" functionality has been removed from `NameServer` instances. This has moved to the `nserver.application` classes.
  - `NameServer` instances can now be registered to other instances. This replaces `SubServer` functionality that was in development.
- Refactoring of `nserver.server` and `nserver.middleware` classes.
- `NameServer` `name` argument / attribute is no longer used when creating the logger.

### Fixed
- Uncaught errors from dropped connections in `nserver.transport.TCPv4Transport`

### Development Changes
- Development tooling has moved to `uv`.
  - The tooling remains wrapped in `dev.sh`.
  - This remove the requirement for `docker` in local development.
- Test suite added to GitHub Actions.
- Added contributing guidelies.

## [2.0.0](https://github.com/nhairs/nserver/compare/v1.0.0...v2.0.0) - 2023-12-20

- Implement [Middleware][middleware]
  - This includes adding error handling middleware that facilitates [error handling][error-handling].
- Add [`StaticRule`][nserver.rules.StaticRule] and [`ZoneRule`][nserver.rules.ZoneRule].
- Refector [`NameServer.rule`][nserver.server.NameServer.rule] to use expanded [`smart_make_rule`][nserver.rules.smart_make_rule] function.
  - Although this change should not affect rules using this decorator from being called correctly, it may change the precise rule type being used. Specifically it may use `StaticRule` instead of `WildcardStringRule` for strings with no substitutions.
- Add [Blueprints][blueprints]
  - Include refactoring `NameServer` into a new shared based `Scaffold` class.

## [1.0.0](https://github.com/nhairs/nserver/commit/628db055848c6543641d514b4186f8d953b6af7d) - 2023-11-03

- Beta release
