### IMPORTS
### ============================================================================
## Standard Library
import logging

# Note: Optional can only be replaced with `| None` in 3.10+
from typing import List, Callable, Dict, Pattern, Optional, Union, Type, Any

## Installed
import dnslib

## Application
from .exceptions import InvalidMessageError
from .models import Query, Response
from .records import RecordBase
from .rules import RuleBase, WildcardStringRule, RegexRule, ResponseFunction
from .settings import Settings
from .transport import TransportBase, UDPv4Transport, UDPv6Transport, TCPv4Transport


### CONSTANTS
### ============================================================================
TRANSPORT_MAP: Dict[str, Type[TransportBase]] = {
    "UDPv4": UDPv4Transport,
    "UDPv6": UDPv6Transport,
    "TCPv4": TCPv4Transport,
}


### Classes
### ============================================================================
class NameServer:
    """NameServer for responding to requests."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, name: str, settings: Optional[Settings] = None) -> None:
        """Initialise NameServer

        Args:
            name: The name of the server. This is used for internal logging.
            settings: settings ot use with this `NameServer` instance
        """
        self.name = name
        self.rules: List[RuleBase] = []
        self.hooks: Dict[str, List[Callable]] = {
            "before_first_query": [],
            "before_query": [],
            "after_query": [],
        }
        self._logger = logging.getLogger(f"nserver.i.{self.name}")
        self._before_first_query_run = False

        self.settings = settings if settings is not None else Settings()

        transport = TRANSPORT_MAP.get(self.settings.server_transport)
        if transport is None:
            raise ValueError(
                f"Invalid settings.server_transport {self.settings.server_transport!r}"
            )
        self.transport = transport(self.settings)

        self.shutdown_server = False
        self.exit_code = 0
        return

    def register_rule(self, rule: RuleBase) -> None:
        """Register the given rule

        Args:
            rule: the rule to register
        """
        self._debug(f"Registered rule: {rule!r}")
        self.rules.append(rule)
        return

    # def register_blueprint(self, blueprint, rule: Union[str, Pattern, RuleBase]) -> None:
    #     """Register a blueprint using the given rule.
    #
    #
    #     If the rule triggers, the query is passed to the Blueprint to determine
    #     if a rule matches. Just because a rule matches the blueprint does not
    #     mean that the rule will match any rule in the blueprint.
    #
    #     Args:
    #         blueprint: the `Blueprint` to attach
    #         rule: The rule to use to match to this `blueprint`
    #             - If rule is a `str` is interpreted as a the input for a WildcardStringRule.
    #             - If rule is a `Pattern` is interpreted as the input for a RegexRule.
    #             - If rule is a instance of `RuleBase` is used as is.
    #
    #     Note: that all rules are internally converted to a `BlueprintRule`.
    #     """
    #     raise NotImplementedError()

    def register_before_first_query(self, func: Callable[[], None]) -> None:
        """Register a function to be run before the first query.

        Args:
            func: the function to register
        """
        self.hooks["before_first_query"].append(func)
        return

    def register_before_query(self, func: Callable[[Query], Any]) -> None:
        """Register a function to be run before every query.

        Args:
            func: the function to register
                If `func` returns anything other than `None` will stop processing the
                incoming `Query` and continue to result processing with the return value.
        """
        self.hooks["before_query"].append(func)
        return

    def register_after_query(self, func: Callable[[Response], Response]) -> None:
        """Register a function to be run on the result of a query.

        Args:
            func: the function to register
        """
        self.hooks["after_query"].append(func)
        return

    def run(self) -> int:
        """Start running the server

        Returns:
            `exit_code`, `0` if exited normally
        """
        # Setup Logging
        console_logger = logging.StreamHandler()
        console_logger.setLevel(self.settings.console_log_level)

        console_formatter = logging.Formatter(
            "[{asctime}][{levelname}][{name}] {message}", style="{"
        )

        console_logger.setFormatter(console_formatter)

        self._logger.addHandler(console_logger)
        self._logger.setLevel(min(self.settings.console_log_level, self.settings.file_log_level))

        # Start Server
        # TODO: Do we want to recreate the transport instance or do we assume that
        # transport.shutdown_server puts it back into a ready state?
        # We could make this configurable? :thonking:

        self._info(f"Starting {self.transport}")
        try:
            self.transport.start_server()
        except Exception as e:  # pylint: disable=broad-except
            self._critical(e)
            self.exit_code = 1
            return self.exit_code

        # Process Requests
        error_count = 0
        while True:
            if self.shutdown_server:
                break
            try:
                message = self.transport.receive_message()
                response = self._process_dns_record(message.message)
                message.response = response
                self.transport.send_message_response(message)
            except InvalidMessageError as e:
                self._warning(f"{e}")
            except Exception as e:  # pylint: disable=broad-except
                self._error(f"Uncaught error occured. {e}", exc_info=True)
                error_count += 1
                if error_count >= self.settings.max_errors:
                    self._critical(f"Max errors hit ({error_count})")
                    self.shutdown_server = True
                    self.exit_code = 1
            except KeyboardInterrupt:
                self._info("KeyboardInterrupt received.")
                self.shutdown_server = True

        # Stop Server
        self._info("Shutting down server")
        self.transport.stop_server()

        # Teardown Logging
        self._logger.removeHandler(console_logger)
        return self.exit_code

    ## Decorators
    ## -------------------------------------------------------------------------
    def rule(
        self, rule_: Union[str, Pattern], allowed_qtypes: List[str], case_sensitive: bool = False
    ):  # pylint: disable=unused-argument
        """Decorator for registering a function as a rule.

        Args:
            rule_: if `Pattern` then `RegexRule`, if `str` then `WildcardStringRule`.
            allowed_qtypes: Only match the given DNS query types
            case_sensitive: how to handle case when matching the rule
        """

        def decorator(func: ResponseFunction):
            nonlocal rule_
            nonlocal allowed_qtypes
            nonlocal case_sensitive
            actual_rule: RuleBase

            if isinstance(rule_, str):
                actual_rule = WildcardStringRule(
                    rule_, allowed_qtypes, func, case_sensitive=case_sensitive
                )
            elif isinstance(  # pylint: disable=isinstance-second-argument-not-valid-type
                rule_, Pattern
            ):
                # Note: I've disabled this type check thing as it currently works and it might
                # vary between versions of python and other bugs.
                # see also: https://stackoverflow.com/questions/6102019/type-of-compiled-regex-object-in-python
                actual_rule = RegexRule(rule_, allowed_qtypes, func, case_sensitive=case_sensitive)
            else:
                raise ValueError(f"Could not handle rule: {rule_!r}")

            self.register_rule(actual_rule)
            return func

        return decorator

    def before_first_query(self):
        """Decorator for registering before_first_query hook.

        These functions are called when the server receives it's first query, but
        before any further processesing.
        """

        def decorator(func: Callable[[], None]):
            self.register_before_first_query(func)
            return func

        return decorator

    def before_query(self):
        """Decorator for registering before_query hook.

        These functions are called before processing each query.
        """

        def decorator(func: Callable[[Query], Any]):
            self.register_before_query(func)
            return func

        return decorator

    def after_query(self):
        """Decorator for registering after_query hook.

        These functions are after the rule function is run and may modify the
        response.
        """

        def decorator(func: Callable[[Response], Response]):
            self.register_after_query(func)
            return func

        return decorator

    ## Internal Functions
    ## -------------------------------------------------------------------------
    def _process_dns_record(self, message: dnslib.DNSRecord) -> dnslib.DNSRecord:
        """Process the given DNSRecord.

        This is the main function that implements all the hooks, rule processing,
        error handling, etc.

        Args:
            message: the DNS query to process

        Returns:
            the DNS response
        """

        # pylint: disable=too-many-branches

        # We run before_first_query hook here so that _process_dns_record can be
        # called without the underlying server existing.
        if not self._before_first_query_run:
            self._debug("Running before_first_query")
            self._before_first_query_run = True  # If we error everything dies anyway
            for func in self.hooks["before_first_query"]:
                self._vdebug(f"Running before_first_query func: {func}")
                func()

        response = message.reply()

        if message.header.opcode != dnslib.OPCODE.QUERY:
            self._info(f"Received non-query opcode: {message.header.opcode}")
            # This server only response to DNS queries
            response.header.set_rcode(dnslib.RCODE.NOTIMP)
            return response

        if len(message.questions) != 1:
            self._info(f"Received len(questions_ != 1 ({message.questions})")
            # To simplify things we only respond if there is 1 question.
            # This is apparently common amongst DNS server implementations.
            # For more information see the responses to this SO question:
            # https://stackoverflow.com/q/4082081
            response.header.set_rcode(dnslib.RCODE.REFUSED)
            return response

        try:
            try:
                query = Query.from_dns_question(message.questions[0])
            except ValueError as e:
                self._warning(e)
                response.header.set_rcode(dnslib.RCODE.FORMERR)
                return response

            self._info(f"Question: {query.type} {query.name}")

            # Process before_request hooks
            for hook in self.hooks["before_query"]:
                result = hook(query)
                if result is not None:
                    # before_request hook returned a response, stop processing
                    self._debug(f"Got result from before_hook: {hook}")
                    break
            else:
                # No hook returned a response
                for rule in self.rules:
                    rule_func = rule.get_func(query)
                    if rule_func is not None:
                        self._info(f"Matched Rule: {rule}")
                        break
                else:
                    self._info("Did not match any rule")
                    response.header.set_rcode(dnslib.RCODE.NXDOMAIN)
                    return response

                result = rule_func(query)

            # Ensure result is a Response object
            if result is None:
                result = Response()
            elif isinstance(result, Response):
                pass
            elif isinstance(result, RecordBase) and result.__class__ is not RecordBase:
                result = Response(result)
            elif isinstance(result, list) and all(isinstance(item, RecordBase) for item in result):
                result = Response(result)
            else:
                raise TypeError(f"Cannot process result: {result!r}")

            # run after_query hooks
            for hook in self.hooks["after_query"]:
                result = hook(result)

            # Add results to response
            # Note: we do this in the same try-except block so that if we get a
            # malformed `Response` instance we response with nothing
            response.add_answer(*result.get_answer_records())
            response.add_ar(*result.get_additional_records())
            response.add_auth(*result.get_authority_records())
            response.header.set_rcode(result.error_code)

        except Exception as e:  # pylint: disable=broad-except
            self._error(f"Uncaught Exception {e}", exc_info=True)
            # NOTE: We create a new response so that if an error occurs partway through
            # constructing the response we response with an empty SERVFAIL response
            # opposed to a partial SERVFAIL response.
            response = message.reply()
            response.header.set_rcode(dnslib.RCODE.SERVFAIL)
            return response

        return response

    ## Logging
    ## -------------------------------------------------------------------------
    def _vvdebug(self, *args, **kwargs):
        """Log very verbose debug message."""

        return self._logger.log(6, *args, **kwargs)

    def _vdebug(self, *args, **kwargs):
        """Log verbose debug message."""

        return self._logger.log(8, *args, **kwargs)

    def _debug(self, *args, **kwargs):
        """Log debug message."""

        return self._logger.debug(*args, **kwargs)

    def _info(self, *args, **kwargs):
        """Log very verbose debug message."""

        return self._logger.info(*args, **kwargs)

    def _warning(self, *args, **kwargs):
        """Log warning message."""

        return self._logger.warning(*args, **kwargs)

    def _error(self, *args, **kwargs):
        """Log an error message."""

        return self._logger.error(*args, **kwargs)

    def _critical(self, *args, **kwargs):
        """Log a critical message."""

        return self._logger.critical(*args, **kwargs)
