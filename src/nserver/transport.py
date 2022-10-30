### IMPORTS
### ============================================================================
## Standard Library
import base64
from collections import deque
import selectors
import socket
import struct
import time
from typing import Tuple, Optional, Dict, List, Deque, Any, cast

## Installed
import dnslib

## Application

### FUNCTIONS
### ============================================================================
def get_tcp_info(connection: socket.socket):
    """Get tcp_info

    TCP_ESTABLISHED = 1,
    TCP_SYN_SENT,
    TCP_SYN_RECV,
    TCP_FIN_WAIT1,
    TCP_FIN_WAIT2,
    TCP_TIME_WAIT,
    TCP_CLOSE,
    TCP_CLOSE_WAIT,
    TCP_LAST_ACK,
    TCP_LISTEN,
    TCP_CLOSING

    ref: https://stackoverflow.com/a/18189190
    """
    fmt = "B" * 7 + "I" * 21
    tcp_info = struct.unpack(fmt, connection.getsockopt(socket.IPPROTO_TCP, socket.TCP_INFO, 92))
    return tcp_info


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
        self.cached_connections: Dict[int, Dict[str, Any]] = {}
        self.last_cache_clean = 0.0
        self.connection_queue: Deque[selectors.SelectorKey] = deque()

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
            raise RuntimeError(f"Failed to bind server after {timeout} seconds")
        self.socket.listen()
        self.last_cache_clean = time.time()  # avoid immediately trying to cleaning the cache
        return

    def receive_message(self) -> MessageContainer:

        # Our selector (at least when epoll), appears to send EVENT_READ when
        # the connection is in TCP 8 (CLOSE-WAIT), i.e. when the client has closed
        # their side of the connection.
        # This will result in connection.recv to return 0 bytes - i.e. python's
        # way of indicating that the socket was closed.
        # This means when getting the next connection, we may need to iterate
        # through a number of closed connections and make sure we close them.
        # There appears to be no way to know ahead of time if a tcp connection
        # is going to be used for pipelined requests, so we can't optimistically
        # close the connection after servign a response.
        # Ref: https://datatracker.ietf.org/doc/html/rfc7766#section-6.2.1

        while True:
            connection, remote_address = self._get_next_connection()
            packed_length = connection.recv(2)

            if packed_length:
                # We have data
                break
            # No data, we need to close this connection and keep looping.
            self._close_connection(connection)
            continue

        data_length = struct.unpack("!H", packed_length)[0]
        data_remaining = data_length

        data = b""
        while data_remaining > 0:
            data += connection.recv(data_remaining)
            data_remaining = data_length - len(data)

        message = MessageContainer(data, connection, self.SOCKET_TYPE, remote_address)
        return message

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
            self._close_connection(message.socket)

        # Note that we don't close the socket here in order to allow TCP request streaming
        return

    def stop_server(self) -> None:
        # Stop listening
        self._close_connection(self.socket)
        # Cleanup existing connections
        cached_connections = list(self.cached_connections.values())
        for cache in cached_connections:
            self._cache_remove(cache)
        return

    def __repr__(self):
        return f"{self.__class__.__name__}(address={self.address!r}, port={self.port!r})"

    def _get_next_connection(self) -> Tuple[socket.socket, Tuple[str, int]]:
        while not self.connection_queue:
            # loop until connection is ready for execution
            events = self.selector.select(self.SELECT_TIMEOUT)
            if events:
                # print(f"Got new events: {events}")
                for key, _ in events:
                    if key.fileobj is self.socket:
                        # new connection on listening socket
                        self._accept_connection()
                    else:
                        # remote_socket, update last_data_time
                        self.connection_queue.append(key)
                        self.cached_connections[key.fd]["last_data_time"] = time.time()
                        break
            # No connections ready, take advantage to do cleanup
            if time.time() - self.last_cache_clean > self.CONNECTION_CACHE_CLEAN_INTERVAL:
                self._cleanup_cached_connections()

        # We have a connection
        # print(f"connection_queue: {self.connection_queue}")
        selector_key = self.connection_queue.popleft()
        # cast as we know that we are only adding sockets to the selector.
        connection = cast(socket.socket, selector_key.fileobj)

        # print(f"Checking socket: {connection}")

        ## Remote socket
        try:
            remote_address = connection.getpeername()
        except OSError as e:
            if e.errno == 107:  # Transport endpoint is not connected
                self._close_connection(connection)
                return self._get_next_connection()
            raise e

        return connection, remote_address

    def _accept_connection(self) -> None:
        """Accept a connection, cache it, and add it to the selector"""
        remote_socket, remote_address = self.socket.accept()
        if remote_socket.fileno() not in self.cached_connections:
            remote_socket.setblocking(False)
            # print(f"New connection: {remote_socket}")
            cache = {
                "socket": remote_socket,
                "remote_address": remote_address,
                "last_data_time": time.time(),
                "selector_key": self.selector.register(remote_socket, selectors.EVENT_READ),
            }
            self.cached_connections[remote_socket.fileno()] = cache
        return

    def _cleanup_cached_connections(self) -> None:
        # check for expired connections
        now = time.time()
        cache_clear: List[Dict[str, Any]] = []
        for cache in self.cached_connections.values():
            if now - cache["last_data_time"] > self.CONNECTION_KEEPALIVE_LIMIT:
                if cache["selector_key"] not in self.connection_queue:
                    # No data ready, and no data for a while.
                    # Mark for deletion (do not try to modify iterating object)
                    cache_clear.append(cache)

        for cache in cache_clear:
            self._cache_remove(cache)

        quiet_connections: List[Dict[str, Any]] = []
        cached_connections_len = len(self.cached_connections)
        if cached_connections_len > self.CONNECTION_CACHE_LIMIT:
            # print(f"Cache full ({cached_connections_len}/{self.CONNECTION_CACHE_LIMIT})")
            # Check for connections which do not have data ready
            for cache in self.cached_connections.values():
                if cache["selector_key"] not in self.connection_queue:
                    quiet_connections.append(cache)

            if cached_connections_len - len(quiet_connections) > self.CONNECTION_CACHE_LIMIT:
                # remove all connections
                remove_connections = quiet_connections
            else:
                # attempt to reduce cache to self.CONNECTION_CACHE_TARGET
                remove_count = cached_connections_len - self.CONNECTION_CACHE_TARGET
                # sort to remove oldest first
                quiet_connections.sort(key=lambda c: c["last_data_time"])
                remove_connections = quiet_connections[:remove_count]

            for cache in remove_connections:
                self._cache_remove(cache)

        self.last_cache_clean = time.time()
        # print(f"TCP Connection Cache {len(self.cached_connections)}/{self.CONNECTION_CACHE_LIMIT}")
        return

    def _cache_remove(self, cache: Dict[str, Any]) -> None:
        # print(f"Clearing {cache}")
        connection = cache["socket"]
        if connection.fileno == -1:
            # Connection has closed
            pass

        del self.cached_connections[cache["selector_key"].fd]
        self.selector.unregister(connection)
        self._close_connection(connection)
        # print(f"Expired TCP: {cache['remote_address']}")
        return

    def _close_connection(self, connection: socket.socket) -> None:
        """Close a socket and make sure it is closed."""
        if connection.fileno() >= 0:
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
