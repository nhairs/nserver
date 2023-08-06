### IMPORTS
### ============================================================================
## Standard Library
from dataclasses import dataclass
import logging

## Installed

## Application


### CLASSES
### ============================================================================
@dataclass
class Settings:
    "Dataclass for NameServer settings"
    server_transport: str = "UDPv4"
    server_address: str = "localhost"
    server_port: int = 9953
    console_log_level: int = logging.INFO
    file_log_level: int = logging.INFO
    max_errors: int = 5

    # Not implemented, ideas for useful things
    # debug: bool = False  # Put server into "debug mode" (e.g. hot reload)
    # health_check: bool = False  # provde route for health check
    # stats: bool = False  # provide route for retrieving operational stats
    # remote_admin: bool = False  # allow remote shutdown restart etc?
