# Sub-Servers and Blueprints


## Sub-Servers

[`SubServer`][nserver.server.SubServer] provides a way for you to compose your application. They support most of the same functionality as a `NameServer`.

Use cases:

- Split up your application across different servers for maintainability / composability.
- Reuse a server registered under different rules.
- Allow custom packages to define their own rules that you can add to your own server.

!!! note
    SubServers requires `nserver>=2.0`

### Using Sub-Servers

```python
from nserver import SubServer, NameServer, ZoneRule, ALL_CTYPES, A, TXT

# First SubServer
mysite = SubServer("mysite")

@mysite.rule("nicholashairs.com", ["A"])
@mysite.rule("www.nicholashairs.com", ["A"])
def nicholashairs_website(query: Query) -> A:
    return A(query.name, "159.65.13.73")

@mysite.rule(ZoneRule, "", ALL_CTYPES)
def nicholashairs_catchall(query: Query) -> None:
    # Return empty response for all other queries
    return None

# Second SubServer
en_subserver = SubServer("english-speaking-blueprint")

@en_subserver.rule("hello.{base_domain}", ["TXT"])
def en_hello(query: Query) -> TXT:
    return TXT(query.name, "Hello There!")

# Register to NameServer
server = NameServer("server")
server.register_subserver(mysite, ZoneRule, "nicholashairs.com", ALL_CTYPES)
server.register_subserver(en_subserver, ZoneRule, "au", ALL_CTYPES)
server.register_subserver(en_subserver, ZoneRule, "nz", ALL_CTYPES)
server.register_subserver(en_subserver, ZoneRule, "uk", ALL_CTYPES)
```

#### Middleware, Hooks, and Error Handling

Sub-Servers maintain their own `QueryMiddleware` stack which will run before any rule function is run. Included in this stack is the `HookMiddleware` and `ExceptionHandlerMiddleware`.

### Key differences with `NameServer`

- Does not use settings (`Setting`).
- Does not have a `Transport`.
- Does not have a `RawRecordMiddleware` stack.

## Blueprints

[`Blueprint`][nserver.server.Blueprint]s act as a container for rules. They are an efficient way to compose your application if you do not want or need to use functionality provided by a `QueryMiddleware` stack.

!!! note
    Blueprints require `nserver>=2.0`

### Using Blueprints

```python
# ...
from nserver import Blueprint, MX

no_email_blueprint = Blueprint("noemail")

@no_email_blueprint.rule("{base_domain}", ["MX"])
@no_email_blueprint.rule("**.{base_domain}", ["MX"])
def no_email(query: Query) -> MX:
    "Indicate that we do not have a mail exchange"
    return MX(query.name, ".", 0)


## Add it to our sub-servers
en_subserver.register_rule(no_email_blueprint)

# Problem! Because we have already registered the nicholashairs_catchall rule,
# it will prevent our blueprint from being called. So instead let's manually
# insert it as the first rule.
mysite.rules.insert(0, no_email_blueprint)
```

### Key differences with `NameServer` and `SubServer`

- Only provides the `@rule` decorator and `register_rule` method.
  - It does not have a `QueryMiddleware` stack which means it does not support hooks or error-handling.
- Is used directly in `register_rule` (e.g. `some_server.register_rule(my_blueprint)`).
- If rule does not match an internal rule will continue to the next rule in the parent server.

  In comparison the server classes will return `NXDOMAIN` if a rule doesn't match their internal rules.
