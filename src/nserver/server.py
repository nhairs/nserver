### IMPORTS
### ============================================================================
## Standard Library
import logging

# Note: Optional can only be replaced with `| None` in 3.10+
from typing import List, Dict, Optional, Union, Type, Pattern

## Installed
import dnslib

## Application
from .exceptions import InvalidMessageError
from .models import Query, Response
from .rules import smart_make_rule, RuleBase, ResponseFunction
from .settings import Settings
from .transport import TransportBase, UDPv4Transport, UDPv6Transport, TCPv4Transport

from . import middleware

### CONSTANTS
### ============================================================================
TRANSPORT_MAP: Dict[str, Type[TransportBase]] = {
    "UDPv4": UDPv4Transport,
    "UDPv6": UDPv6Transport,
    "TCPv4": TCPv4Transport,
}


### Classes
### ============================================================================
class _LoggingMixin:  # pylint: disable=too-few-public-methods
    """Self bound logging methods"""

    _logger: logging.Logger

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


class RulesContainer(_LoggingMixin):
    """Base class for rules based functionality`

    New in `2.0`.

    Attributes:
        rules: registered rules
    """

    def __init__(self) -> None:
        super().__init__()
        self.rules: List[RuleBase] = []
        return

    def register_rule(self, rule: RuleBase) -> None:
        """Register the given rule

        Args:
            rule: the rule to register
        """
        self._debug(f"Registered rule: {rule!r}")
        self.rules.append(rule)
        return

    def rule(self, rule_: Union[Type[RuleBase], str, Pattern], *args, **kwargs):
        """Decorator for registering a function using [`smart_make_rule`][nserver.rules.smart_make_rule].

        Changed in `2.0`: This method now uses `smart_make_rule`.

        Args:
            rule_: rule as per `nserver.rules.smart_make_rule`
            args: extra arguments to provide `smart_make_rule`
            kwargs: extra keyword arguments to provide `smart_make_rule`

        Raises:
            ValueError: if `func` is provided in `kwargs`.
        """

        if "func" in kwargs:
            raise ValueError("Must not provide `func` in kwargs")

        def decorator(func: ResponseFunction):
            nonlocal rule_
            nonlocal args
            nonlocal kwargs
            self.register_rule(smart_make_rule(rule_, *args, func=func, **kwargs))
            return func

        return decorator


class ServerBase(RulesContainer):
    """Base class for shared functionality between `NameServer` and `SubServer`

    New in `2.0`.

    Attributes:
        hook_middleware: hook middleware
        exception_handler_middleware: Query exception handler middleware
    """

    def __init__(self) -> None:
        """
        Args:
            name: The name of the server. This is used for internal logging.
        """
        super().__init__()
        self.hook_middleware = middleware.HookMiddleware()
        self.exception_handler_middleware = middleware.ExceptionHandlerMiddleware()

        self._user_query_middleware: List[middleware.QueryMiddleware] = []
        self._query_middleware_stack: List[
            Union[middleware.QueryMiddleware, middleware.QueryMiddlewareCallable]
        ] = []
        return

    ## Register Methods
    ## -------------------------------------------------------------------------
    def register_subserver(
        self, subserver: "SubServer", rule_: Union[Type[RuleBase], str, Pattern], *args, **kwargs
    ) -> None:
        """Register a `SubServer` using [`smart_make_rule`][nserver.rules.smart_make_rule].

        New in `2.0`.

        Args:
            subserver: the `SubServer` to attach
            rule_: rule as per `nserver.rules.smart_make_rule`
            args: extra arguments to provide `smart_make_rule`
            kwargs: extra keyword arguments to provide `smart_make_rule`

        Raises:
            ValueError: if `func` is provided in `kwargs`.
        """

        if "func" in kwargs:
            raise ValueError("Must not provide `func` in kwargs")
        self.register_rule(smart_make_rule(rule_, *args, func=subserver.entrypoint, **kwargs))
        return

    def register_before_first_query(self, func: middleware.BeforeFirstQueryHook) -> None:
        """Register a function to be run before the first query.

        Args:
            func: the function to register
        """
        self.hook_middleware.before_first_query.append(func)
        return

    def register_before_query(self, func: middleware.BeforeQueryHook) -> None:
        """Register a function to be run before every query.

        Args:
            func: the function to register
                If `func` returns anything other than `None` will stop processing the
                incoming `Query` and continue to result processing with the return value.
        """
        self.hook_middleware.before_query.append(func)
        return

    def register_after_query(self, func: middleware.AfterQueryHook) -> None:
        """Register a function to be run on the result of a query.

        Args:
            func: the function to register
        """
        self.hook_middleware.after_query.append(func)
        return

    def register_middleware(self, query_middleware: middleware.QueryMiddleware) -> None:
        """Add a `QueryMiddleware` to this server.

        New in `2.0`.

        Args:
            query_middleware: the middleware to add
        """
        if self._query_middleware_stack:
            # Note: we can use truthy expression as once processed there will always be at
            # least one item in the stack
            raise RuntimeError("Cannot register middleware after stack is created")
        self._user_query_middleware.append(query_middleware)
        return

    def register_exception_handler(
        self, exception_class: Type[Exception], handler: middleware.ExceptionHandler
    ) -> None:
        """Register an exception handler for the `QueryMiddleware`

        Only one handler can exist for a given exception type.

        New in `2.0`.

        Args:
            exception_class: the type of exception to handle
            handler: the function to call when handling an exception
        """
        if exception_class in self.exception_handler_middleware.exception_handlers:
            raise ValueError("Exception handler already exists for {exception_class}")

        self.exception_handler_middleware.exception_handlers[exception_class] = handler
        return

    # Decorators
    # ..........................................................................
    def before_first_query(self):
        """Decorator for registering before_first_query hook.

        These functions are called when the server receives it's first query, but
        before any further processesing.
        """

        def decorator(func: middleware.BeforeFirstQueryHook):
            self.register_before_first_query(func)
            return func

        return decorator

    def before_query(self):
        """Decorator for registering before_query hook.

        These functions are called before processing each query.
        """

        def decorator(func: middleware.BeforeQueryHook):
            self.register_before_query(func)
            return func

        return decorator

    def after_query(self):
        """Decorator for registering after_query hook.

        These functions are after the rule function is run and may modify the
        response.
        """

        def decorator(func: middleware.AfterQueryHook):
            self.register_after_query(func)
            return func

        return decorator

    def exception_handler(self, exception_class: Type[Exception]):
        """Decorator for registering a function as an exception handler

        New in `2.0`.

        Args:
            exception_class: The `Exception` class to register this handler for
        """

        def decorator(func: middleware.ExceptionHandler):
            nonlocal exception_class
            self.register_exception_handler(exception_class, func)
            return func

        return decorator

    ## Internal Functions
    ## -------------------------------------------------------------------------
    def _prepare_query_middleware_stack(self) -> None:
        """Prepare the `QueryMiddleware` for this server."""
        if self._query_middleware_stack:
            # Note: we can use truthy expression as once processed there will always be at
            # least one item in the stack
            raise RuntimeError("QueryMiddleware stack already exists")

        middleware_stack: List[middleware.QueryMiddleware] = [
            self.exception_handler_middleware,
            *self._user_query_middleware,
            self.hook_middleware,
        ]
        rule_processor = middleware.RuleProcessor(self.rules)

        next_middleware: Optional[middleware.QueryMiddleware] = None
        for query_middleware in middleware_stack[::-1]:
            if next_middleware is None:
                query_middleware.register_next_function(rule_processor)
            else:
                query_middleware.register_next_function(next_middleware)
            next_middleware = query_middleware

        self._query_middleware_stack.extend(middleware_stack)
        self._query_middleware_stack.append(rule_processor)
        return


class NameServer(ServerBase):
    """NameServer for responding to requests."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, name: str, settings: Optional[Settings] = None) -> None:
        """
        Args:
            name: The name of the server. This is used for internal logging.
            settings: settings to use with this `NameServer` instance
        """
        super().__init__()
        self.name = name
        self._logger = logging.getLogger(f"nserver.i.nameserver.{self.name}")

        self.raw_exception_handler_middleware = middleware.RawRecordExceptionHandlerMiddleware()
        self._user_raw_record_middleware: List[middleware.RawRecordMiddleware] = []
        self._raw_record_middleware_stack: List[
            Union[middleware.RawRecordMiddleware, middleware.RawRecordMiddlewareCallable]
        ] = []

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

    ## Register Methods
    ## -------------------------------------------------------------------------
    def register_raw_middleware(self, raw_middleware: middleware.RawRecordMiddleware) -> None:
        """Add a `RawRecordMiddleware` to this server.

        New in `2.0`.

        Args:
            raw_middleware: the middleware to add
        """
        if self._raw_record_middleware_stack:
            # Note: we can use truthy expression as once processed there will always be at
            # least one item in the stack
            raise RuntimeError("Cannot register middleware after stack is created")
        self._user_raw_record_middleware.append(raw_middleware)
        return

    def register_raw_exception_handler(
        self, exception_class: Type[Exception], handler: middleware.RawRecordExceptionHandler
    ) -> None:
        """Register a raw exception handler for the `RawRecordMiddleware`.

        Only one handler can exist for a given exception type.

        New in `2.0`.

        Args:
            exception_class: the type of exception to handle
            handler: the function to call when handling an exception
        """
        if exception_class in self.raw_exception_handler_middleware.exception_handlers:
            raise ValueError("Exception handler already exists for {exception_class}")

        self.raw_exception_handler_middleware.exception_handlers[exception_class] = handler
        return

    # Decorators
    # ..........................................................................
    def raw_exception_handler(self, exception_class: Type[Exception]):
        """Decorator for registering a function as an raw exception handler

        New in `2.0`.

        Args:
            exception_class: The `Exception` class to register this handler for
        """

        def decorator(func: middleware.RawRecordExceptionHandler):
            nonlocal exception_class
            self.register_raw_exception_handler(exception_class, func)
            return func

        return decorator

    ## Public Methods
    ## -------------------------------------------------------------------------
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
            self._prepare_middleware_stacks()
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

    ## Internal Functions
    ## -------------------------------------------------------------------------
    def _process_dns_record(self, message: dnslib.DNSRecord) -> dnslib.DNSRecord:
        """Process the given DNSRecord by sending it into the `RawRecordMiddleware` stack.

        Args:
            message: the DNS query to process

        Returns:
            the DNS response
        """
        if self._raw_record_middleware_stack is None:
            raise RuntimeError(
                "RawRecordMiddleware stack does not exist. Have you called _prepare_middleware?"
            )
        return self._raw_record_middleware_stack[0](message)

    def _prepare_middleware_stacks(self) -> None:
        """Prepare all middleware for this server."""
        self._prepare_query_middleware_stack()
        self._prepare_raw_record_middleware_stack()
        return

    def _prepare_raw_record_middleware_stack(self) -> None:
        """Prepare the `RawRecordMiddleware` for this server."""
        if not self._query_middleware_stack:
            # Note: we can use truthy expression as once processed there will always be at
            # least one item in the stack
            raise RuntimeError("Must prepare QueryMiddleware stack first")

        if self._raw_record_middleware_stack:
            # Note: we can use truthy expression as once processed there will always be at
            # least one item in the stack
            raise RuntimeError("RawRecordMiddleware stack already exists")

        middleware_stack: List[middleware.RawRecordMiddleware] = [
            self.raw_exception_handler_middleware,
            *self._user_raw_record_middleware,
        ]

        query_middleware_processor = middleware.QueryMiddlewareProcessor(
            self._query_middleware_stack[0]
        )

        next_middleware: Optional[middleware.RawRecordMiddleware] = None
        for raw_middleware in middleware_stack[::-1]:
            if next_middleware is None:
                raw_middleware.register_next_function(query_middleware_processor)
            else:
                raw_middleware.register_next_function(next_middleware)
            next_middleware = raw_middleware

        self._raw_record_middleware_stack.extend(middleware_stack)
        self._raw_record_middleware_stack.append(query_middleware_processor)
        return


class SubServer(ServerBase):
    """Class that can replicate many of the functions of a `NameServer`.

    They can be used to construct or extend applications.

    A `SubServer` maintains it's own `QueryMiddleware` stack and list of rules.

    New in `2.0`.
    """

    def __init__(self, name: str) -> None:
        """
        Args:
            name: The name of the server. This is used for internal logging.
        """
        super().__init__()
        self.name = name
        self._logger = logging.getLogger(f"nserver.i.subserver.{self.name}")
        return

    def entrypoint(self, query: Query) -> Response:
        """Entrypoint into this `SubServer`.

        This method should be passed to rules as the function to run.
        """
        if not self._query_middleware_stack:
            self._prepare_query_middleware_stack()
        return self._query_middleware_stack[0](query)


class Blueprint(RulesContainer, RuleBase):
    """A container for rules that can be registered onto a server

    It can be registered as normal rule: `server.register_rule(blueprint_rule)`

    New in `2.0`.
    """

    def __init__(self, name: str) -> None:
        """
        Args:
            name: The name of the server. This is used for internal logging.
        """
        super().__init__()
        self.name = name
        self._logger = logging.getLogger(f"nserver.i.blueprint.{self.name}")
        return

    def get_func(self, query: Query) -> Optional[ResponseFunction]:
        for rule in self.rules:
            func = rule.get_func(query)
            if func is not None:
                self._debug(f"matched {rule}")
                return func
        self._debug("did not match any rule")
        return None
