### IMPORTS
### ============================================================================
## Future
from __future__ import annotations

## Standard Library

## Installed
from pillar.logging import LoggingMixin

## Application
from .exceptions import InvalidMessageError
from .server import NameServer, RawNameServer
from .transport import TransportBase


### CLASSES
### ============================================================================
class BaseApplication(LoggingMixin):
    """Base class for all application classes.

    New in `3.0`.
    """

    def __init__(self, server: NameServer | RawNameServer) -> None:
        if isinstance(server, NameServer):
            server = RawNameServer(server)
        self.server: RawNameServer = server
        self.logger = self.get_logger()
        return

    def run(self) -> int | None:
        """Run this application.

        Child classes must override this method.

        Returns:
            Integer status code to be returned. `None` will be treated as `0`.
        """
        raise NotImplementedError()


class DirectApplication(BaseApplication):
    """Application that directly runs the server.

    New in `3.0`.
    """

    MAX_ERRORS: int = 10

    exit_code: int

    def __init__(self, server: NameServer | RawNameServer, transport: TransportBase) -> None:
        super().__init__(server)
        self.transport = transport
        self.exit_code = 0
        self.shutdown_server = False
        return

    def run(self) -> int:
        """Start running the server

        Returns:
            `exit_code`, `0` if exited normally
        """
        # Start Server
        # TODO: Do we want to recreate the transport instance or do we assume that
        # transport.shutdown_server puts it back into a ready state?
        # We could make this configurable? :thonking:

        self.info(f"Starting {self.transport}")
        try:
            self.transport.start_server()
        except Exception as e:  # pylint: disable=broad-except
            self.critical(f"Failed to start server. {e}", exc_info=e)
            self.exit_code = 1
            return self.exit_code

        # Process Requests
        error_count = 0
        while True:
            if self.shutdown_server:
                break

            try:
                message = self.transport.receive_message()
                message.response = self.server.process_request(message.message)
                self.transport.send_message_response(message)

            except InvalidMessageError as e:
                self.warning(f"{e}")

            except Exception as e:  # pylint: disable=broad-except
                self.error(f"Uncaught error occured. {e}", exc_info=e)
                error_count += 1
                if self.MAX_ERRORS and error_count >= self.MAX_ERRORS:
                    self.critical(f"Max errors hit ({error_count})")
                    self.shutdown_server = True
                    self.exit_code = 1

            except KeyboardInterrupt:
                self.info("KeyboardInterrupt received.")
                self.shutdown_server = True

        # Stop Server
        self.info("Shutting down server")
        self.transport.stop_server()

        return self.exit_code
