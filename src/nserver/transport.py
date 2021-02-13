### IMPORTS
### ============================================================================
## Standard Library
import base64
import socket
import struct
import time
from typing import Tuple, Optional

## Installed
import dnslib

## Application

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

    def __init__(
        self, error: dnslib.dns.DNSError, raw_data: bytes, remote_address: Tuple[str, int]
    ):
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

    SOCKET_TYPE = "TCPv4"

    def __init__(self, address: str, port: int):
        self.address = address
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
        return

    def receive_message(self) -> MessageContainer:
        connection, remote_address = self.socket.accept()

        data_length = struct.unpack("!H", connection.recv(2))[0]
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
        message.socket.sendall(encoded_length + data)
        message.socket.close()
        return

    def stop_server(self) -> None:
        self.socket.close()
        return

    def __repr__(self):
        return f"{self.__class__.__name__}(address={self.address!r}, port={self.port!r})"
