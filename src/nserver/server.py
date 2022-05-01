### IMPORTS
### ============================================================================
## Standard Library
from argparse import Namespace
import logging
from typing import List, Callable, Dict, Pattern

## Installed
import dnslib

## Application
from .rules import RuleBase, WildcardStringRule, RegexRule
from .models import Query, Response
from .transport import UDPv4Transport, TCPv4Transport, TransportBase, InvalidMessageError
from .records import RecordBase

### NAME SERVER
### ============================================================================
class NameServer:
    """NameServer for responding to requests."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, name: str) -> None:
        """Initialise NameServer

        args:
            name: The name of the server. This is used for internal logging.
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

        self.settings = Namespace()
        self.settings.SERVER_TYPE = "UDPv4"
        self.settings.SERVER_ADDRESS = "localhost"
        self.settings.SERVER_PORT = 9953
        self.settings.DEBUG = False
        self.settings.HEALTH_CHECK = False
        self.settings.STATS = False
        self.settings.REMOTE_ADMIN = False
        self.settings.CONSOLE_LOG_LEVEL = logging.INFO
        self.settings.FILE_LOG_LEVEL = logging.INFO
        self.settings.MAX_ERRORS = 5

        self.shutdown_server = False
        self.exit_code = 0
        return

    def register_rule(self, rule: RuleBase) -> None:
        """Register the given rule."""
        self._debug(f"Registered rule: {rule!r}")
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

    def register_before_first_query(self, func) -> None:
        """Register a function to be run before the first query."""
        self.hooks["before_first_query"].append(func)
        return

    def register_before_query(self, func) -> None:
        """Register a function to be run before every query.

        If `func` returns anything other than null will stop processing the
        incoming query and continue to result processing with the return value.
        """
        self.hooks["before_query"].append(func)
        return

    def register_after_query(self, func) -> None:
        """Register a function to be run on the result of a query.

        `func` must accept an instance of `Response` and must return an instance
        of `Response`. It can do nothing, modify or replace the response.
        """
        self.hooks["after_query"].append(func)
        return

    def run(self) -> int:
        """Start running the server"""
        # Setup Logging
        console_logger = logging.StreamHandler()
        console_logger.setLevel(self.settings.CONSOLE_LOG_LEVEL)

        console_formatter = logging.Formatter(
            "[{asctime}][{levelname}][{name}] {message}", style="{"
        )

        console_logger.setFormatter(console_formatter)

        self._logger.addHandler(console_logger)
        self._logger.setLevel(min(self.settings.CONSOLE_LOG_LEVEL, self.settings.FILE_LOG_LEVEL))

        # Start Server
        server_type = self.settings.SERVER_TYPE
        server: TransportBase

        if server_type == "TCPv4":
            server = TCPv4Transport(self.settings.SERVER_ADDRESS, self.settings.SERVER_PORT)
        elif server_type == "UDPv4":
            server = UDPv4Transport(self.settings.SERVER_ADDRESS, self.settings.SERVER_PORT)
        else:
            raise ValueError(f"Unknown SERVER_TYPE: {server_type}")

        self._info(f"Starting {server}")
        try:
            server.start_server()
        except Exception as e:  # pylint: disable=broad-except
            self._critical(e)
            self.exit_code = 1
            return self.exit_code

        error_count = 0
        # Process Requests
        while True:
            if self.shutdown_server:
                break
            try:
                message = server.receive_message()
                response = self._process_dns_record(message.message)
                message.response = response
                server.send_message_response(message)
            except InvalidMessageError as e:
                self._warning(f"{e}")
            except Exception as e:  # pylint: disable=broad-except
                self._error(f"Uncaught error occured. {e}", exc_info=True)
                error_count += 1
                if error_count >= self.settings.MAX_ERRORS:
                    self._critical(f"Max errors hit ({error_count})")
                    self.shutdown_server = True
                    self.exit_code = 1
            except KeyboardInterrupt:
                self._info("KeyboardInterrupt received.")
                self.shutdown_server = True

        # Stop Server
        self._info("Shutting down server")
        server.stop_server()

        # Teardown Logging
        self._logger.removeHandler(console_logger)
        return self.exit_code

    ## Decorators
    ## -------------------------------------------------------------------------
    def rule(self, rule_, allowed_qtypes, case_sensitive=False):  # pylint: disable=unused-argument
        """Decorator for registering a function as a rule.

        If regex, then RegexRule, if str then WildcardStringRule.
        """

        def decorator(func):
            nonlocal rule_
            nonlocal allowed_qtypes
            nonlocal case_sensitive
            if isinstance(rule_, str):
                rule_ = WildcardStringRule(
                    rule_, allowed_qtypes, func, case_sensitive=case_sensitive
                )
            elif isinstance(  # pylint: disable=isinstance-second-argument-not-valid-type
                rule_, Pattern
            ):
                # Note: I've disabled thiss type check thing as it currently works and it might
                # vary between versions of python and other bugs.
                # see also: https://stackoverflow.com/questions/6102019/type-of-compiled-regex-object-in-python
                rule_ = RegexRule(rule_, allowed_qtypes, func, case_sensitive=case_sensitive)
            else:
                raise ValueError(f"Could not handle rule: {rule_!r}")

            self.register_rule(rule_)
            return func

        return decorator

    def before_first_query(self):
        """Decorator for registering before_first_query hook.

        These functions are called when the server receives it's first query, but
        before any further processesing.
        """

        def decorator(func):
            self.register_before_first_query(func)
            return func

        return decorator

    def before_query(self):
        """Decorator for registering before_query hook.

        These functions are called before processing each query.
        """

        def decorator(func):
            self.register_before_query(func)
            return func

        return decorator

    def after_query(self):
        """Decorator for registering after_query hook.

        These functions are after the rule function is run and may modify the
        response.
        """

        def decorator(func):
            self.register_after_query(func)
            return func

        return decorator

    ## Internal Functions
    ## -------------------------------------------------------------------------
    def _process_dns_record(self, message: dnslib.DNSRecord) -> dnslib.DNSRecord:
        """Process the given DNSRecord.

        This is the main function that implements all the hooks, rule processing,
        error handling, etc.
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
            elif isinstance(result, RecordBase) and result.__class__ is not RecordBase:
                result = Response(result)
            elif isinstance(result, list):
                for item in result:
                    if not isinstance(item, RecordBase) or result.__class__ is RecordBase:
                        raise TypeError()
            elif not isinstance(result, Response):
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
