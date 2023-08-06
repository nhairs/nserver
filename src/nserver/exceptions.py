### IMPORTS
### ============================================================================
## Standard Library
import base64

# Note: Union can only be replaced with `X | Y` in 3.10+
from typing import Tuple, Union

## Installed

## Application


### CLASSES
### ============================================================================
class InvalidMessageError(ValueError):
    """Class for holding invalid messages."""

    def __init__(
        self, error: Exception, raw_data: bytes, remote_address: Union[str, Tuple[str, int]]
    ) -> None:
        encoded_data = base64.b64encode(raw_data).decode("ascii")
        message = f"{error} Remote: {remote_address} Bytes: {encoded_data}"
        super().__init__(message)
        return
