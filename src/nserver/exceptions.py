### IMPORTS
### ============================================================================
## Future
from __future__ import annotations

## Standard Library
import base64

## Installed

## Application


### CLASSES
### ============================================================================
class InvalidMessageError(ValueError):
    """An invalid DNS message"""

    def __init__(
        self, error: Exception, raw_data: bytes, remote_address: str | tuple[str, int]
    ) -> None:
        """
        Args:
            error: The original `Exception` thrown
            raw_data: Raw DNS message as pulled from the transport
            remote_address: The remote end from the transport
        """
        encoded_data = base64.b64encode(raw_data).decode("ascii")
        message = f"{error} Remote: {remote_address} Bytes: {encoded_data}"
        super().__init__(message)
        return
