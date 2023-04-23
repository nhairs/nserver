### IMPORTS
### ============================================================================
## Standard Library
import base64
from collections import deque
from dataclasses import dataclass
from enum import IntEnum
import selectors
import socket
import struct
import time
from typing import Tuple, Optional, Dict, List, Deque, NewType, cast

## Installed
import dnslib

## Application


### CONSTANTS
### ============================================================================
class TcpState(IntEnum):
    """State of a TCP connection.

    General usage:
    `TcpState(get_tcp_info(connection)[0])`
    """

    TCP_ESTABLISHED = 1
    TCP_SYN_SENT = 2
    TCP_SYN_RECV = 3
    TCP_FIN_WAIT1 = 4
    TCP_FIN_WAIT2 = 5
    TCP_TIME_WAIT = 6
    TCP_CLOSE = 7
    TCP_CLOSE_WAIT = 8
    TCP_LAST_ACK = 9
    TCP_LISTEN = 10
    TCP_CLOSING = 11


## Typing
## -----------------------------------------------------------------------------
CacheKey = NewType("CacheKey", str)


### FUNCTIONS
### ============================================================================
def get_tcp_info(connection: socket.socket):
    """Get tcp_info

    ref: https://stackoverflow.com/a/18189190
    """
    fmt = "B" * 7 + "I" * 21
    tcp_info = struct.unpack(fmt, connection.getsockopt(socket.IPPROTO_TCP, socket.TCP_INFO, 92))
    return tcp_info


def get_tcp_state(connection: socket.socket) -> TcpState:
    "Get the TcpState of a socket"
    return TcpState(get_tcp_info(connection)[0])


def recv_data(
    data_length: int, connection: socket.socket, existing_data: bytes = b"", timeout: int = 10
) -> bytes:
    """Receive data a given amount of data from a socket."""
    data = bytes(existing_data)
    data_remaining = data_length - len(data)
    start_time = time.time()
    while data_remaining > 0:
        data += connection.recv(data_remaining)
        data_remaining = data_length - len(data)
        if data_remaining and time.time() - start_time > timeout:
            msg = f"timeout reading data from {connection.getpeername()}"
            raise TimeoutError(msg)
    return data


### CLASSES
### ============================================================================
class MessageContainer:  # pylint: disable=too-few-public-methods
    """Class for holding DNS messages and the socket they originated from.

    Used to simplify the interface (and allow for threading etc later).
    """

    SOCKET_TYPES = {"UDPv4", "TCPv4"}

    def __init__(
        self,
        raw_data: bytes,
        socket_: Optional[socket.socket],
        socket_type: str,
        remote_address: Tuple[str, int],
    ):
        if socket_type not in self.SOCKET_TYPES:
            raise ValueError(f"Unkown socket_type {socket_type!r}")

        try:
            self.message = dnslib.DNSRecord.parse(raw_data)
        except dnslib.dns.DNSError as e:
            raise InvalidMessageError(e, raw_data, remote_address) from e
        self.socket = socket_
        self.socket_type = socket_type
        self.remote_address = remote_address
        self.response: Optional[dnslib.DNSRecord] = None
        return

    def get_response_bytes(self):
        """Convert response object to bytes"""
        if self.response is None:
            raise RuntimeError("response not set!")
        return self.response.pack()


class InvalidMessageError(ValueError):
    """Class for holding invalid messages."""

    def __init__(self, error: Exception, raw_data: bytes, remote_address: Tuple[str, int]):
        encoded_data = base64.b64encode(raw_data).decode("ascii")
        message = f"{error} Remote: {remote_address} Bytes: {encoded_data}"
        super().__init__(message)
        return


## Transport Classes
## -----------------------------------------------------------------------------
class TransportBase:
    """Base class for all transports"""

    def start_server(self, timeout=60) -> None:
        """Start transport's server"""
        raise NotImplementedError()

    def stop_server(self) -> None:
        """Stop transport's server"""
        raise NotImplementedError()

    def receive_message(self) -> MessageContainer:
        """Receive a message from the running server"""
        raise NotImplementedError()

    def send_message_response(self, message: MessageContainer) -> None:
        """Respond to a message that was received by the server"""
        raise NotImplementedError()


class UDPv4Transport(TransportBase):
    """Transport class for IPv4 UDP."""

    SOCKET_TYPE = "UDPv4"

    def __init__(self, address: str, port: int):
        self.address = address
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return

    def start_server(self, timeout=60) -> None:
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            try:
                self.socket.bind((self.address, self.port))
                break
            except OSError as e:
                if e.errno == 98:
                    # Socket already in use.
                    time.sleep(5)
                    continue
                raise e
        else:
            raise RuntimeError(f"Failed to bind server after {timeout} seconds")
        return

    def receive_message(self) -> MessageContainer:
        data, remote_address = self.socket.recvfrom(512)
        message = MessageContainer(data, None, self.SOCKET_TYPE, remote_address)
        return message

    def send_message_response(self, message: MessageContainer) -> None:
        if message.socket_type != self.SOCKET_TYPE:
            raise RuntimeError(f"Invalid socket_type: {message.socket_type} != {self.SOCKET_TYPE}")
        data = message.get_response_bytes()
        self.socket.sendto(data, message.remote_address)
        return

    def stop_server(self) -> None:
        self.socket.close()
        return

    def __repr__(self):
        return f"{self.__class__.__name__}(address={self.address!r}, port={self.port!r})"


# TCPv4 Server
# ..............................................................................
@dataclass
class CachedConnection:
    "Dataclass for storing information about a TCP connection"
    connection: socket.socket
    remote_address: Tuple[str, int]
    last_data_time: float
    selector_key: selectors.SelectorKey
    cache_key: CacheKey


class TCPv4Transport(TransportBase):
    """Transport class for IPv4 TCP.

    References:
        - https://tools.ietf.org/html/rfc7766#section-8
    """

    # pylint: disable=too-many-instance-attributes

    SOCKET_TYPE = "TCPv4"
    SELECT_TIMEOUT = 0.1
    CONNECTION_KEEPALIVE_LIMIT = 30  # seconds
    CONNECTION_CACHE_LIMIT = 200
    CONNECTION_CACHE_VACUUM_PERCENT = 0.9
    CONNECTION_CACHE_TARGET = int(CONNECTION_CACHE_LIMIT * CONNECTION_CACHE_VACUUM_PERCENT)
    CONNECTION_CACHE_CLEAN_INTERVAL = 10  # seconds

    def __init__(self, address: str, port: int) -> None:
        self.address = address
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setblocking(False)
        # Allow taking over of socket when in TIME_WAIT (i.e. previously released)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.selector = selectors.DefaultSelector()
        self.cached_connections: Dict[CacheKey, CachedConnection] = {}
        self.last_cache_clean = 0.0
        self.connection_queue: Deque[socket.socket] = deque()

        self.socket_selector_key = self.selector.register(self.socket, selectors.EVENT_READ)
        return

    def start_server(self, timeout=60) -> None:
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            try:
                self.socket.bind((self.address, self.port))
                break
            except OSError as e:
                if e.errno == 98:
                    # Socket already in use.
                    time.sleep(5)
                    continue
                raise e
        else:
            raise RuntimeError(f"Failed to bind server to {self.port} after {timeout} seconds")
        self.socket.listen()
        self.last_cache_clean = time.time()  # avoid immediately trying to cleaning the cache
        return

    def receive_message(self) -> MessageContainer:
        connection, remote_address = self._get_next_connection()
        packed_length = recv_data(2, connection)

        data_length = struct.unpack("!H", packed_length)[0]
        data = recv_data(data_length, connection)

        return MessageContainer(data, connection, self.SOCKET_TYPE, remote_address)

    def send_message_response(self, message: MessageContainer) -> None:
        if message.socket_type != self.SOCKET_TYPE or message.socket is None:
            raise RuntimeError(f"Invalid socket_type: {message.socket_type} != {self.SOCKET_TYPE}")
        data = message.get_response_bytes()
        encoded_length = struct.pack("!H", len(data))
        try:
            message.socket.sendall(encoded_length + data)
        except BrokenPipeError:
            # Remote closed connection
            # Drop response per https://datatracker.ietf.org/doc/html/rfc7766#section-6.2.4
            self._remove_connection(message.socket)

        # Note that we don't close the socket here in order to allow TCP request streaming
        # print(f"Sent response to {self._get_cache_key(message.socket)} {message.remote_address}")
        return

    def stop_server(self) -> None:
        # Stop listening
        self._close_connection(self.socket)
        # Cleanup existing connections
        cache_keys = list(self.cached_connections)
        for cache_key in cache_keys:
            self._remove_connection(cache_key=cache_key)
        return

    def __repr__(self):
        return f"{self.__class__.__name__}(address={self.address!r}, port={self.port!r})"

    def _get_next_connection(self) -> Tuple[socket.socket, Tuple[str, int]]:
        """Get the next connection that is ready to receive data on."""
        while not self.connection_queue:
            # loop until connection is ready for execution
            events = self.selector.select(self.SELECT_TIMEOUT)
            if events:
                # print(f"Got new events: {events}")
                for key, _ in events:
                    if key.fileobj is self.socket:
                        # new connection on listening socket
                        connection = self._accept_connection()
                        # print(
                        #     f"New connection: id={id(connection)} state={get_tcp_state(connection).name}"
                        # )
                        # TODO: determine if new connection goes into the connection_queue or not
                    else:
                        # This is a remote socket
                        # cast as we known this is a socket.socket
                        connection = cast(socket.socket, key.fileobj)

                        if not self._connection_viable(connection):
                            # Connection not good, remove it
                            self._remove_connection(connection)
                            continue

                        # Connection is viable, update it and add it to connection queue
                        cache_key = self._get_cache_key(connection)
                        self.connection_queue.append(connection)
                        self.cached_connections[cache_key].last_data_time = time.time()

            # No connections ready, take advantage to do cleanup
            elif time.time() - self.last_cache_clean > self.CONNECTION_CACHE_CLEAN_INTERVAL:
                self._cleanup_cached_connections()

        # We have a connection in the queue
        # print(f"connection_queue: {self.connection_queue}")
        connection = self.connection_queue.popleft()
        remote_address = connection.getpeername()

        return connection, remote_address

    def _accept_connection(self) -> socket.socket:
        """Accept a connection, cache it, and add it to the selector"""
        remote_socket, remote_address = self.socket.accept()

        cache_key = self._get_cache_key(remote_socket)
        if cache_key in self.cached_connections:
            raise RuntimeError(f"Key {cache_key} is already cached!")

        remote_socket.setblocking(False)

        self.cached_connections[cache_key] = CachedConnection(
            connection=remote_socket,
            remote_address=remote_address,
            last_data_time=time.time(),
            selector_key=self.selector.register(remote_socket, selectors.EVENT_READ),
            cache_key=cache_key,
        )

        # print(f"New connection: {cache_key} {remote_socket}")
        return remote_socket

    @staticmethod
    def _get_cache_key(connection: socket.socket) -> CacheKey:
        return CacheKey(str(id(connection)))

    @staticmethod
    def _connection_viable(connection: socket.socket) -> bool:
        "Determine if a connection is viable or if needs to be closed"

        # Our selector (at least when epoll), appears to send EVENT_READ when
        # the connection is in TCP 8 (CLOSE-WAIT), i.e. when the client has closed
        # their side of the connection.
        # This will result in connection.recv to return 0 bytes - i.e. python's
        # way of indicating that the socket was closed. This causes issues when reading
        # so instead we do the expensive check of checking the state of the connection.
        # There appears to be no way to know ahead of time if a tcp connection
        # is going to be used for pipelined requests, so we can't optimistically
        # close the connection after serving a response.
        # Ref: https://datatracker.ietf.org/doc/html/rfc7766#section-6.2.1

        if connection.fileno() == -1:
            return False
        if get_tcp_state(connection) == TcpState.TCP_CLOSE_WAIT:
            # TODO: check if I can just check if == to TCP_ESTABLISHED
            return False
        return True

    def _cleanup_cached_connections(self) -> None:
        "Cleanup cached connections"
        now = time.time()
        cache_clear: List[CacheKey] = []
        for cache_key, cache in self.cached_connections.items():
            if now - cache.last_data_time > self.CONNECTION_KEEPALIVE_LIMIT:
                if cache.connection not in self.connection_queue:
                    # No data ready, and no data for a while.
                    # Mark for deletion (do not try to modify iterating object)
                    cache_clear.append(cache_key)

            elif not self._connection_viable(cache.connection):
                cache_clear.append(cache_key)

        for cache_key in cache_clear:
            self._remove_connection(cache_key=cache_key)

        quiet_connections: List[CachedConnection] = []
        cached_connections_len = len(self.cached_connections)
        cache_clear = []

        if cached_connections_len > self.CONNECTION_CACHE_LIMIT:
            print(f"Cache full ({cached_connections_len}/{self.CONNECTION_CACHE_LIMIT})")
            # Check for connections which do not have data ready
            for cache_key, cache in self.cached_connections.items():
                if cache.connection not in self.connection_queue:
                    quiet_connections.append(cache)

            if cached_connections_len - len(quiet_connections) > self.CONNECTION_CACHE_LIMIT:
                # remove all connections
                cache_clear = [c.cache_key for c in quiet_connections]
            else:
                # attempt to reduce cache to self.CONNECTION_CACHE_TARGET
                remove_count = cached_connections_len - self.CONNECTION_CACHE_TARGET
                # sort to remove oldest first
                quiet_connections.sort(key=lambda c: c.last_data_time)
                cache_clear = [c.cache_key for c in quiet_connections[:remove_count]]

            for cache_key in cache_clear:
                self._remove_connection(cache_key=cache_key)

        self.last_cache_clean = time.time()
        # print(f"TCP Connection Cache {len(self.cached_connections)}/{self.CONNECTION_CACHE_LIMIT}")
        return

    def _remove_connection(
        self, connection: Optional[socket.socket] = None, cache_key: Optional[CacheKey] = None
    ) -> None:
        """Remove a connection from the server (closing it in the process)

        Must provide either a connection, or the connection's cache_key
        """
        if connection and cache_key:
            raise ValueError("Must provide only one of connection or cache_key")

        if connection:
            cache_key = self._get_cache_key(connection)
        elif cache_key:
            connection = self.cached_connections[cache_key].connection
        else:
            raise ValueError("Must provide a connection or a cache_key")

        if connection.fileno() >= 0:
            # Only unregister valid connections
            self.selector.unregister(connection)

        cache = self.cached_connections.pop(cache_key)  # pylint: disable=unused-variable
        self._close_connection(connection)

        # print(f"Removed connection: {cache_key} {cache.remote_address}")
        return

    def _close_connection(self, connection: socket.socket) -> None:
        """Close a socket and make sure it is closed.

        You probably want _remove_connection in most circumstances
        """
        if connection.fileno() >= 0:
            # print(f"Shutdown connection state: state={get_tcp_state(connection).name}")
            # Only call shutdown active sockets
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError as e:
                if e.errno == 107:  # Transport endpoint is not connected
                    # nothingtodohere.png
                    pass
                else:
                    raise e
        connection.close()
        return
