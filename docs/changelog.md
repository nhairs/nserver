# Change Log

## 2.0.0

- Implement [Middleware][middleware]
  - This includes adding error handling middleware that facilitates [error handling][error-handling].
- Add [`StaticRule`][nserver.rules.StaticRule] and [`ZoneRule`][nserver.rules.ZoneRule].
- Refector [`NameServer.rule`][nserver.server.NameServer.rule] to use expanded [`smart_make_rule`][nserver.rules.smart_make_rule] function.
  - Although this change should not affect rules using this decorator from being called correctly, it may change the precise rule type being used. Specifically it may use `StaticRule` instead of `WildcardStringRule` for strings with no substitutions.
- Add [Blueprints][blueprints]
  - Include refactoring `NameServer` into a new shared based `Scaffold` class.

## 1.0.0

- Beta release
