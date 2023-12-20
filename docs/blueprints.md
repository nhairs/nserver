# Blueprints

[`Blueprint`][nserver.server.Blueprint]s provide a way for you to compose your application. They support most of the same functionality as a `NameServer`.

Use cases:

- Split up your application across different blueprints for maintainability / composability.
- Reuse a blueprint registered under different rules.
- Allow custom packages to define their own rules that you can add to your own server.

Blueprints require `nserver>=2.0`

## Using Blueprints

```python
from nserver import Blueprint, NameServer, ZoneRule, ALL_CTYPES, A

# First Blueprint
mysite = Blueprint("mysite")

@mysite.rule("nicholashairs.com", ["A"])
@mysite.rule("www.nicholashairs.com", ["A"])
def nicholashairs_website(query: Query) -> A:
    return A(query.name, "159.65.13.73")

@mysite.rule(ZoneRule, "", ALL_CTYPES)
def nicholashairs_catchall(query: Query) -> None:
    # Return empty response for all other queries
    return None

# Second Blueprint
en_blueprint = Blueprint("english-speaking-blueprint")

@en_blueprint.rule("hello.{base_domain}", ["A"])
def en_hello(query: Query) -> A:
    return A(query.name, "1.1.1.1")

# Register to NameServer
server = NameServer("server")
server.register_blueprint(mysite, ZoneRule, "nicholashairs.com", ALL_CTYPES)
server.register_blueprint(en_blueprint, ZoneRule, "au", ALL_CTYPES)
server.register_blueprint(en_blueprint, ZoneRule, "nz", ALL_CTYPES)
server.register_blueprint(en_blueprint, ZoneRule, "uk", ALL_CTYPES)
```

### Middleware, Hooks, and Error Handling

Blueprints maintain their own `QueryMiddleware` stack which will run before any rule function is run. Included in this stack is the `HookMiddleware` and `ExceptionHandlerMiddleware`.

## Key differences with `NameServer`

- Does not use settings (`Setting`).
- Does not have a `Transport`.
- Does not have a `RawRecordMiddleware` stack.
