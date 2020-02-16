### IMPORTS
### ============================================================================
## Standard Library
import logging
import socket
import struct
import time
from typing import List, Callable, Dict, Optional, Tuple

## Installed
import dnslib

## Application
from .rules import RuleBase
from .models import Query, Response

### NAME SERVER
### ============================================================================
class NameServer:
    """NameServer for responding to requests.

    """

    def __init__(self, name: str, hostname: str) -> None:
        """Initialise NameServer

        args:
            name: The name of the server. This is used for internal logging.
            hostname: The name of the current host, is used for populating authority records.
        """
        self.name = name
        self.hostname = hostname
        self.rules: List[RuleBase] = []
        self.hooks: Dict[str, List[Callable]] = {
            "before_first_query": [],
            "before_query": [],
            "after_query": [],
        }
        self._logger = logging.getLogger(f"nserver.instance.{self.name}")
        self._before_first_query_run = False
        self.settings = {
            "SERVER_TYPE": "UDPv4",
            "SERVER_ADDRESS": "localhost",
            "SERVER_PORT": 9953,
            "DEBUG": False,
            "HEALTH_CHECK": False,
            "STATS": False,
            "REMOTE_ADMIN": False,
        }
        self.shutdown_server = False
        return

    def register_rule(self, rule: RuleBase) -> None:
        """Register the given rule.
        """
        self.rules.append(rule)
        return

    def register_blueprint(self, blueprint, rule) -> None:
        """Register a blueprint using the given rule.

        If the rule triggers, the query is passed to the Blueprint to determine
        if a rule matches. Just because a rule matches the blueprint does not
        mean that the rule will match any rule in the blueprint.

        If rule is a str is interpreted as a the input for a WildcardStringRule.
        If rule is a regex is interpreted as the input for a RegexRule.
        If rule is a instance of RuleBase is used as is.

        Note: that all rules are internally converted to a BlueprintRule.
        """
        raise NotImplementedError()

    def run(self) -> None:
        server_type = self.settings["SERVER_TYPE"]

        if server_type == "TCPv4":
            server = TCPv4Transport(self.settings["SERVER_ADDRESS"], self.settings["SERVER_PORT"])
        elif server_type == "UDPv4":
            server = UDPv4Transport(self.settings["SERVER_ADDRESS"], self.settings["SERVER_PORT"])
        else:
            raise ValueError(f"Unknown SERVER_TYPE: {server_type}")

        server.start_server()

        try:
            while True:
                if self.shutdown_server:
                    break
                message = server.receive_message()
                response = self._process_dns_record(message.message)
                message.response = response
                server.send_message_response(message)
        except Exception:  # pylint: disable=broad-except
            pass
        except KeyboardInterrupt:
            pass

        server.stop_server()
        return

    ## Decorators
    ## -------------------------------------------------------------------------
    def rule(self, rule, *args, **kwargs):
        """Decorator for registering a function as a rule.

        If regex, then RegexRule, if str then WildcardStringRule.
        """

        def decorator(func):
            print(f"func: {func!r}, args: {args}, kwargs: {kwargs}")
            # TO DO: actually register the rule
            return func

        return decorator

    def before_first_query(self, func, *args, **kwargs):
        """Decorator for registering before_first_query hook.

        These functions are called when the server receives it's first query, but
        before any further processesing.
        """
        raise NotImplementedError()

    def before_query(self, func, *args, **kwargs):
        """Decorator for registering before_query hook.

        These functions are called before processing each query.
        """
        raise NotImplementedError()

    def after_query(self, func, *args, **kwargs):
        """Decorator for registering after_query hook.

        These functions are after the rule function is run and may modify the
        response.
        """
        raise NotImplementedError()

    ## Internal Functions
    ## -------------------------------------------------------------------------
    def _process_dns_record(self, message: dnslib.DNSRecord) -> dnslib.DNSRecord:
        """Process the given DNSRecord.

        This is the main function that implements all the hooks, rule processing,
        error handling, etc.
        """
        if not self._before_first_query_run:
            # Not implemented (might move to s
            pass

        response = message.reply()

        if message.header.opcode != dnslib.OPCODE.QUERY:
            # This server only response to DNS queries
            response.header.set_rcode(dnslib.RCODE.REFUSED)
            return response

        if len(message.questions) != 1:
            # To simplify things we only respond if there is 1 question.
            # This is apparently common amongst DNS server implementations.
            # For more information see the responses to this SO question:
            # https://stackoverflow.com/q/4082081
            response.header.set_rcode(dnslib.RCODE.FORMERR)
            return response

        try:
            query = Query.from_dns_question(message.questions[0])

            # Process before_request hooks
            for hook in self.hooks["before_query"]:
                result = hook(query)
                if result is not None:
                    # before_request hook returned a response, stop processing
                    break
            else:
                # No hook returned a response
                for rule in self.rules:
                    rule_func = rule.get_func(query)
                    if rule_func is not None:
                        break
                else:
                    response.header.set_rcode(dnslib.RCODE.NXDOMAIN)
                    return response

                result = rule_func(query)

            # Ensure result is a Response object
            if result is None:
                result = Response()

            # run after_query hooks
            for hook in self.hooks["after_query"]:
                result = hook(result)

            # Add results to response
            # Note: we do this in the same try-except block so that if we get a
            # malformed `Response` instance we response with nothing

            # TO DO

        except Exception:  # pylint: disable=broad-except
            # NOTE: We create a new response so that if an error occurs partway through
            # constructing the response we response with an empty SERVFAIL response
            # opposed to a partial SERVFAIL response.
            response = message.reply()
            response.header.set_rcode(dnslib.RCODE.SERVFAIL)
            return response

        return response


## Transport Classes
## -----------------------------------------------------------------------------
class MessageContainer:
    """Class for holding DNS messages and the socket they originated from.

    Used to simplify the interface (and allow for threading etc later).
    """

    SOCKET_TYPES = {"UDPv4", "TCPv4"}

    def __init__(
        self,
        raw_data: bytes,
        socket_: socket.socket,
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
        if message.socket_type != self.SOCKET_TYPE:
            raise RuntimeError(f"Invalid socket_type: {message.socket_type} != {self.SOCKET_TYPE}")
        data = message.get_response_bytes()
        encoded_length = struct.pack("!H", len(data))
        message.socket.sendall(encoded_length + data)
        message.socket.close()
        return

    def stop_server(self) -> None:
        self.socket.close()
        return
