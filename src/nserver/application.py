### IMPORTS
### ============================================================================
## Future
from __future__ import annotations

## Standard Library
import concurrent.futures
import os
import queue
import threading
import time
from typing import Optional

## Installed
from pillar.logging import LoggingMixin

## Application
from .exceptions import InvalidMessageError
from .server import NameServer, RawNameServer
from .transport import TransportBase, MessageContainer


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

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(server={self.server!r}, transport={self.transport!r})"

    def run(self) -> int:
        """Start running the server

        Returns:
            `exit_code`, `0` if exited normally
        """
        # Start Server
        # TODO: Do we want to recreate the transport instance or do we assume that
        # transport.shutdown_server puts it back into a ready state?
        # We could make this configurable? :thonking:

        self.info(f"Starting {self!r}...")
        try:
            self.transport.start_server()
        except Exception as e:  # pylint: disable=broad-except
            self.critical(f"Failed to start server. {e}", exc_info=e)
            self.exit_code = 1
            return self.exit_code
        self.info("Applicationed started.")

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
        self.info("Shutting down Application...")
        self.transport.stop_server()
        self.info("Application has shutdown.")

        return self.exit_code


class ThreadsApplication(BaseApplication):
    """Application that processes requests using a threads.

    New in `3.2`
    """

    MAX_ERRORS: int = 10
    QUEUE_MAX_SIZE = 100_000

    exit_code: int

    def __init__(
        self,
        server: NameServer | RawNameServer,
        transport: TransportBase,
        workers: Optional[int] = None,
    ) -> None:
        super().__init__(server)
        self.transport = transport
        self.workers = (
            max(workers, 1) if workers is not None else min(max(os.cpu_count() - 2, 1), 16)  # type: ignore[operator]
        )
        self.error_count = 0
        self.error_count_lock = threading.Lock()
        self.exit_code = 0
        self.shutdown_server = False

        self.receive_thread = threading.Thread(target=self.receive_loop, name="nserver-recv")
        self.receive_queue: queue.Queue[MessageContainer] = queue.Queue(self.QUEUE_MAX_SIZE)
        self.worker_threads = [
            threading.Thread(target=self.worker_loop, name=f"nserver-worker-{i}")
            for i in range(self.workers)
        ]
        self.send_queue: queue.Queue[MessageContainer] = queue.Queue(self.QUEUE_MAX_SIZE)
        self.send_thread = threading.Thread(target=self.send_loop, name="nserver-send")
        return

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(server={self.server!r}, transport={self.transport!r}, workers={self.workers})"

    def run(self) -> int:
        """Start running the server

        Returns:
            `exit_code`, `0` if exited normally
        """
        # Start Server
        # TODO: Do we want to recreate the transport instance or do we assume that
        # transport.shutdown_server puts it back into a ready state?
        # We could make this configurable? :thonking:

        self.info(f"Starting {self!r}...")
        try:
            self.transport.start_server()
            self.receive_thread.start()
            # map(lambda t: t.start(), self.worker_threads)
            for t in self.worker_threads:
                t.start()
            self.debug(f"worker threads: {self.worker_threads}")
            self.send_thread.start()

        except Exception as e:  # pylint: disable=broad-except
            self.critical(f"Failed to start server. {e}", exc_info=e)
            self.exit_code = 1
            return self.exit_code

        self.info("Application started.")

        # Process Requests
        while True:
            try:
                if self.MAX_ERRORS and self.error_count >= self.MAX_ERRORS:
                    self.critical(f"Max errors hit ({self.error_count})")
                    self.shutdown_server = True
                    self.exit_code = 1
                    break

                time.sleep(1)

            except KeyboardInterrupt:
                self.info("KeyboardInterrupt received.")
                self.shutdown_server = True
                break

        # Stop Server
        self.info("Shutting down Application...")
        self.receive_thread.join()
        self.receive_queue.shutdown()
        # map(lambda t: t.join(), self.worker_threads)
        for t in self.worker_threads:
            t.join()
        self.send_queue.shutdown()
        self.send_thread.join()
        self.transport.stop_server()
        self.info("Application has shutdown.")

        return self.exit_code

    def receive_loop(self) -> None:
        """Receive messages from the transport and send them to the worker threads"""
        while not self.shutdown_server:
            try:
                self.debug("attempting to receive message")
                message = self.transport.receive_message()
                self.debug(f"message received {message}")
                self.receive_queue.put(message)

            except InvalidMessageError as e:
                self.warning(f"Skipping invalid message: {e}")

            except Exception as e:  # pylint: disable=broad-except
                self.handle_uncaught_error(e)
        return

    def worker_loop(self) -> None:
        """Process a message using the server and send to the send thread"""
        while True:
            try:
                self.debug("worker attempting to receive message")
                message = self.receive_queue.get(True, 1)
                self.debug(f"worker received message {message}")
                message.response = self.server.process_request(message.message)
                self.send_queue.put(message)
                self.receive_queue.task_done()

            except queue.Empty:
                # No work
                continue

            except queue.ShutDown:
                # Queue empty and no more work
                break

            except Exception as e:  # pylint: disable=broad-except
                self.handle_uncaught_error(e)
                self.receive_queue.task_done()
        return

    def send_loop(self) -> None:
        """Send a processed message"""
        while True:
            try:
                message = self.send_queue.get(True, 1)
                self.transport.send_message_response(message)
                self.send_queue.task_done()

            except queue.Empty:
                # No work
                continue

            except queue.ShutDown:
                # Queue empty and no more work
                break

            except Exception as e:  # pylint: disable=broad-except
                self.handle_uncaught_error(e)
                self.send_queue.task_done()
        return

    def handle_uncaught_error(self, e: Exception) -> None:
        """Handle uncaught errors from the application, transport, and server."""
        self.error(f"Uncaught error occured. {e}", exc_info=e)
        with self.error_count_lock:
            self.error_count += 1
        return


class ThreadPoolApplication(BaseApplication):
    """Application that processes requests using a threadpool.

    New in `3.2`
    """

    MAX_ERRORS: int = 10

    exit_code: int

    def __init__(
        self,
        server: NameServer | RawNameServer,
        transport: TransportBase,
        max_workers: Optional[int] = None,
    ) -> None:
        super().__init__(server)
        self.transport = transport
        self.receive_thread = threading.Thread(target=self.receive_loop, name="nserver-recv-loop")
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers, "nserver-worker")
        self.error_count = 0
        self.error_count_lock = threading.Lock()
        self.exit_code = 0
        self.shutdown_server = False
        return

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(server={self.server!r}, transport={self.transport!r}, max_workers={self.thread_pool._max_workers})"

    def run(self) -> int:
        """Start running the server

        Returns:
            `exit_code`, `0` if exited normally
        """
        # Start Server
        # TODO: Do we want to recreate the transport instance or do we assume that
        # transport.shutdown_server puts it back into a ready state?
        # We could make this configurable? :thonking:

        self.info(f"Starting {self!r}...")
        try:
            self.transport.start_server()
            self.receive_thread.start()

        except Exception as e:  # pylint: disable=broad-except
            self.critical(f"Failed to start server. {e}", exc_info=e)
            self.exit_code = 1
            return self.exit_code

        self.info("Application started.")

        # Process Requests
        while True:
            if self.shutdown_server:
                break

            try:
                time.sleep(0.1)

                if self.MAX_ERRORS and self.error_count >= self.MAX_ERRORS:
                    self.critical(f"Max errors hit ({self.error_count})")
                    self.shutdown_server = True
                    self.exit_code = 1

            except KeyboardInterrupt:
                self.info("KeyboardInterrupt received.")
                self.shutdown_server = True

        # Stop Server
        self.info("Shutting down Application...")
        self.receive_thread.join()
        self.thread_pool.shutdown()
        self.transport.stop_server()
        self.info("Application has shutdown.")

        return self.exit_code

    def receive_loop(self) -> None:
        """Receive messages from the transport and submit to the thread pool"""
        while not self.shutdown_server:
            try:
                message = self.transport.receive_message()
                self.thread_pool.submit(self.process_message, message)

            except InvalidMessageError as e:
                self.warning(f"{e}")

            except Exception as e:  # pylint: disable=broad-except
                self.handle_uncaught_error(e)
        return

    def process_message(self, message: MessageContainer) -> None:
        """Process a message using the server"""
        try:
            message.response = self.server.process_request(message.message)
            self.transport.send_message_response(message)
        except Exception as e:  # pylint: disable=broad-except
            self.handle_uncaught_error(e)
        return

    def handle_uncaught_error(self, e: Exception) -> None:
        """Handle uncaught errors from the application, transport, and server."""
        self.error(f"Uncaught error occured. {e}", exc_info=e)
        with self.error_count_lock:
            self.error_count += 1
        return

    def run_2(self) -> int:
        """Start running the server

        Returns:
            `exit_code`, `0` if exited normally
        """
        # Start Server
        # TODO: Do we want to recreate the transport instance or do we assume that
        # transport.shutdown_server puts it back into a ready state?
        # We could make this configurable? :thonking:

        self.info(f"Starting {self!r}...")
        try:
            self.transport.start_server()
        except Exception as e:  # pylint: disable=broad-except
            self.critical(f"Failed to start server. {e}", exc_info=e)
            self.exit_code = 1
            return self.exit_code

        self.info("Application started.")

        # Process Requests
        while True:
            if self.shutdown_server:
                break

            try:
                message = self.transport.receive_message()
                self.thread_pool.submit(self.process_message, message)

            except InvalidMessageError as e:
                self.warning(f"{e}")

            except Exception as e:  # pylint: disable=broad-except
                self.handle_uncaught_error(e)

            except KeyboardInterrupt:
                self.info("KeyboardInterrupt received.")
                self.shutdown_server = True

            if self.MAX_ERRORS and self.error_count >= self.MAX_ERRORS:
                self.critical(f"Max errors hit ({self.error_count})")
                self.shutdown_server = True
                self.exit_code = 1

        # Stop Server
        self.info("Shutting down Application...")
        self.thread_pool.shutdown()
        self.transport.stop_server()
        self.info("Application has shutdown.")

        return self.exit_code
