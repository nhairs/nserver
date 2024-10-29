### IMPORTS
### ============================================================================
## Standard Library
from collections import deque
from dataclasses import dataclass
import enum
import selectors
import socket
import struct
import time

# Note: Union can only be replaced with `X | Y` in 3.10+
from typing import Tuple, Optional, Dict, List, Deque, NewType, Any, Union, cast

## Installed
import dnslib

## Application
from .exceptions import InvalidMessageError
from .settings import Settings


### CONSTANTS
### ============================================================================
class TcpState(enum.IntEnum):
    """State of a TCP connection"""

    # ref: /usr/include/netinet/tcp.h
    # alt: https://github.com/torvalds/linux/blob/master/include/net/tcp_states.h

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
def get_tcp_info(connection: socket.socket) -> Tuple:
    """Get `socket.TCP_INFO` from socket

    Args:
        connection: the socket to inspect

    Returns:
        Tuple of 28 integers.

            Strictly speaking the data returned is platform dependent as will be whatever is in
            `/usr/include/linux/tcp.h`. For our purposes we cap it at the first 28 values.
    """
    # Ref: https://stackoverflow.com/a/18189190
    fmt = "B" * 7 + "I" * 21
    tcp_info = struct.unpack(fmt, connection.getsockopt(socket.IPPROTO_TCP, socket.TCP_INFO, 92))
    return tcp_info


def get_tcp_state(connection: socket.socket) -> TcpState:
    """Get the `TcpState` of a socket

    Args:
        connection: the socket to inspect
    """
    return TcpState(get_tcp_info(connection)[0])


def recv_data(
    data_length: int, connection: socket.socket, existing_data: bytes = b"", timeout: int = 10
) -> bytes:
    """Receive a given amount of data from a socket.

    Args:
        data_length: number of bytes to receive
        connection: the socket to receive data from
        existing_data: data that is added to the response before we collect further data
        timeout: time before giving up in seconds

    Raises:
        TimeoutError: timeout was reached before we finished receiving the data
    """
    data = bytes(existing_data)
    data_remaining = data_length - len(data)
    start_time = time.time()
    while data_remaining > 0:
        data += connection.recv(data_remaining)
        data_remaining = data_length - len(data)
        if data_remaining and time.time() - start_time > timeout:
            raise TimeoutError(f"timeout reading data from {connection.getpeername()}")
    return data


### CLASSES
### ============================================================================
class MessageContainer:  # pylint: disable=too-few-public-methods
    """Class for holding DNS messages and the transport they originated from.

    Used to simplify the interface (and allow for threading etc later).
    """

    def __init__(
        self,
        raw_data: bytes,
        transport: "TransportBase",
        transport_data: Any,
        remote_client: Union[str, Tuple[str, int]],
    ):
        """Create new message container

        Args:
            raw_data: The raw message pulled from the transport. It will parsed
                as a DNS message.

            transport: The transport instance that created this message (e.g. `self`).
                Messages must only be returned to this transport instance when responding (even
                if it would be possible for another instance to respond (e.g. with UDP processing)).
                As such transports should rely on only receiving messages that they created
                (opposed to `assert message.transport is self`).

            transport_data: Data that the transport instance wishes to store with
                this message for later use. What is stored is up to the transport, and it is
                up to the transport implementation to correctly handle it.

            remote_client: Representation of the remote client that sent this DNS
                request. This value is primarily to allow logging and debugging of invalid
                requests. Whilst transport instances must set this value, they should NOT
                use it for processing.
        """
        # Note: We used to have checks on the validity of the input arguments.
        # However as this function is internal to this package and this package
        # is now mature enough to have unit tests, linters, and type checkers,
        # then we /should/ always have the correct values.
        try:
            self.message = dnslib.DNSRecord.parse(raw_data)
        except dnslib.dns.DNSError as e:
            raise InvalidMessageError(e, raw_data, remote_client) from e

        self.transport = transport
        self.transport_data = transport_data
        self.remote_client = remote_client
        self.response: Optional[dnslib.DNSRecord] = None
        return

    def get_response_bytes(self):
        """Convert response object to bytes"""
        if self.response is None:
            raise AttributeError("response not set!")
        return self.response.pack()


## Transport Classes
## -----------------------------------------------------------------------------
class TransportBase:
    """Base class for all transports"""

    def __init__(self, settings: Settings) -> None:
        """
        Args:
            settings: settings of the server this transport is attached to
        """
        self.settings = settings
        # TODO: setup logging
        return

    def start_server(self, timeout: int = 60) -> None:
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


# UDP Transports
# ..............................................................................
@dataclass
class UDPMessageData:
    """Message.transport_data for UDP transports

    Attributes:
        remote_address: UDP peername that this message was received from
    """

    remote_address: Tuple[str, int]


class UDPv4Transport(TransportBase):
    """Transport class for IPv4 UDP."""

    _SOCKET_AF = socket.AF_INET

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.address = self.settings.server_address
        self.port = self.settings.server_port
        self.socket = socket.socket(self._SOCKET_AF, socket.SOCK_DGRAM)
        return

    def start_server(self, timeout=60) -> None:
        """As per parent class"""
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
        """As per parent class"""
        data, remote_address = self.socket.recvfrom(512)
        message = MessageContainer(data, self, UDPMessageData(remote_address), remote_address)
        return message

    def send_message_response(self, message: MessageContainer) -> None:
        """As per parent class"""
        data = message.get_response_bytes()
        self.socket.sendto(data, message.transport_data.remote_address)
        return

    def stop_server(self) -> None:
        """As per parent class"""
        self.socket.close()
        return

    def __repr__(self):
        return f"{self.__class__.__name__}(address={self.address!r}, port={self.port!r})"


class UDPv6Transport(UDPv4Transport):
    """Transport class for IPv6 UDP."""

    _SOCKET_AF = socket.AF_INET6


# TCP Transport
# ..............................................................................
@dataclass
class TCPMessageData:
    """Message.transport_data for TCP transports

    Attributes:
        socket: the socket this message was received on
    """

    socket: socket.socket


@dataclass
class CachedConnection:
    """Dataclass for storing information about a TCP connection

    Attributes:
        connection: the actual socket we are connected to
        remote_address: the socket's peername
        last_data_time: timestamp when we last received data from this socket
        selector_key: key used by our TCP Transport's selector
        cache_key: the key used to store this connection in the cache
    """

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

    SELECT_TIMEOUT = 0.1
    CONNECTION_KEEPALIVE_LIMIT = 30  # seconds
    CONNECTION_CACHE_LIMIT = 200
    CONNECTION_CACHE_VACUUM_PERCENT = 0.9
    CONNECTION_CACHE_TARGET = int(CONNECTION_CACHE_LIMIT * CONNECTION_CACHE_VACUUM_PERCENT)
    CONNECTION_CACHE_CLEAN_INTERVAL = 10  # seconds

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.address = self.settings.server_address
        self.port = self.settings.server_port
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

    def start_server(self, timeout: int = 60) -> None:
        """As per parent class"""
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
        """As per parent class"""
        connection, remote_address = self._get_next_connection()
        packed_length = recv_data(2, connection)

        data_length = struct.unpack("!H", packed_length)[0]
        data = recv_data(data_length, connection)

        return MessageContainer(data, self, TCPMessageData(connection), remote_address)

    def send_message_response(self, message: MessageContainer) -> None:
        """As per parent class"""
        data = message.get_response_bytes()
        encoded_length = struct.pack("!H", len(data))
        try:
            message.transport_data.socket.sendall(encoded_length + data)
        except BrokenPipeError:
            # Remote closed connection
            # Drop response per https://datatracker.ietf.org/doc/html/rfc7766#section-6.2.4
            self._remove_connection(message.transport_data.socket)

        # Note that we don't close the socket here in order to allow TCP request streaming
        # print(f"Sent response to {self._get_cache_key(message.socket)} {message.remote_address}")
        return

    def stop_server(self) -> None:
        """As per parent class"""
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
        """Get the next connection that is ready to receive data on.

        Blocks until a good connection is found
        """
        while True:
            if not self.connection_queue:
                self._populate_connection_queue()

            # There is something in the queue - attempt to get it
            connection = self.connection_queue.popleft()

            if not self._connection_viable(connection):
                self._remove_connection(connection)
                continue

            # Connection is probably viable
            try:
                remote_address = connection.getpeername()
            except OSError as e:
                if e.errno == 107:  # Transport endpoint is not connected
                    self._remove_connection(connection)
                    continue

                raise  # Unknown OSError - raise it.

            break  # we have a valid connection

        return connection, remote_address

    def _populate_connection_queue(self) -> None:
        """Populate self.connection_queue

        Blocks until there is at least on connection
        """
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
        return

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
                # Even removing all quiet_connections will be above our desired limit,
                # there is no point in restricting how many we close so close all
                # quiet_connections
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
