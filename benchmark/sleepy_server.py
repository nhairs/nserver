### IMPORTS
### ============================================================================
## Standard Library
import random
import time

## Installed
from nserver import NameServer, Query, A

## Application

### CONSTANTS
### ============================================================================
SLEEP_MIN = 0.01
SLEEP_MAX = 0.1

### SERVER
### ============================================================================
server = NameServer("sleepy_server")


@server.rule("**", ["A"])
def catchall_a(query: Query) -> A:  # pylint: disable=missing-function-docstring
    time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
    return A(query.name, "1.2.3.4")
