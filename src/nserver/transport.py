### IMPORTS
### ============================================================================
## Standard Library
import socket
import struct
import time
from typing import Tuple, Optional

## Installed
import dnslib

## Application

### CLASSES
### ============================================================================
class MessageContainer:
    """Class for holding DNS messages and the socket they originated from.

    Used to simplify the interface (and allow for threading etc later).
    """

    SOCKET_TYPES = {"UDPv4", "TCPv4"}

    def __init__(
        self,
        raw_data: bytes,
        socket_: Optional[socket.socket],
        socket_type: str,
        remote_address: Tuple[str, str],
    ):
        if socket_type not in self.SOCKET_TYPES:
            raise ValueError(f"Unkown socket_type {socket_type!r}")

        self.message = dnslib.DNSRecord.parse(raw_data)
        self.socket = socket_
        self.socket_type = socket_type
        self.remote_address = remote_address
        self.response: Optional[dnslib.DNSRecord] = None
        return

    def get_response_bytes(self):
        if self.response is None:
            raise RuntimeError("response not set!")
        return self.response.pack()


## Transport Classes
## -----------------------------------------------------------------------------
class TransportBase:
    def start_server(self, timeout=60) -> None:
        raise NotImplementedError()

    def stop_server(self) -> None:
        raise NotImplementedError()

    def receive_message(self) -> MessageContainer:
        raise NotImplementedError()

    def send_message_response(self, message: MessageContainer) -> None:
        raise NotImplementedError()


class UDPv4Transport(TransportBase):
    """Transport class for IPv4 UDP.
    """

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
