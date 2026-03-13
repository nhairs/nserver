### IMPORTS
### ============================================================================
## Standard Library

## Installed
from nserver import NameServer, Query, A

## Application

### SERVER
### ============================================================================
server = NameServer("simple_server")


@server.rule("**", ["A"])
def catchall_a(query: Query) -> A:  # pylint: disable=missing-function-docstring
    return A(query.name, "1.2.3.4")
