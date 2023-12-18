### IMPORTS
### ============================================================================
## Standard Library
import inspect
import threading
from typing import Callable, Dict, List, Type, Optional

## Installed
import dnslib

## Application
from .models import Query, Response
from .records import RecordBase
from .rules import RuleBase, RuleResult


### CONSTANTS
### ============================================================================
## Query Middleware
QueryMiddlewareCallable = Callable[[Query], Response]
"""Type alias for functions that can be used with `QueryMiddleware.next_function`"""

ExceptionHandler = Callable[[Query, Exception], Response]
"""Type alias for `ExceptionHandlerMiddleware` exception handler functions"""

# Hooks
BeforeFirstQueryHook = Callable[[], None]
"""Type alias for `HookMiddleware.before_first_query` functions."""

BeforeQueryHook = Callable[[Query], RuleResult]
"""Type alias for `HookMiddleware.before_query` functions."""

AfterQueryHook = Callable[[Response], Response]
"""Type alias for `HookMiddleware.after_query` functions."""

## RawRecordMiddleware
RawRecordMiddlewareCallable = Callable[[dnslib.DNSRecord], dnslib.DNSRecord]
"""Type alias for functions that can be used with `RawRecordMiddleware.next_function`"""

RawRecordExceptionHandler = Callable[[dnslib.DNSRecord, Exception], dnslib.DNSRecord]
"""Type alias for `RawRecordExceptionHandlerMiddleware` exception handler functions"""


### FUNCTIONS
### ============================================================================
def coerce_to_response(result: RuleResult) -> Response:
    """Convert some `RuleResult` to a `Response`

    New in `1.1.0`.

    Args:
        result: the results to convert

    Raises:
        TypeError: unsupported result type
    """
    if isinstance(result, Response):
        return result

    if result is None:
        return Response()

    if isinstance(result, RecordBase) and result.__class__ is not RecordBase:
        return Response(answers=result)

    if isinstance(result, list) and all(isinstance(item, RecordBase) for item in result):
        return Response(answers=result)

    raise TypeError(f"Cannot process result: {result!r}")


### CLASSES
### ============================================================================
## Request Middleware
## -----------------------------------------------------------------------------
class QueryMiddleware:
    """Middleware for interacting with `Query` objects

    New in `1.1.0`.
    """

    def __init__(self) -> None:
        self.next_function: Optional[QueryMiddlewareCallable] = None
        return

    def __call__(self, query: Query) -> Response:
        if self.next_function is None:
            raise RuntimeError("next_function is not set")
        return self.process_query(query, self.next_function)

    def register_next_function(self, next_function: QueryMiddlewareCallable) -> None:
        """Set the `next_function` of this middleware"""
        if self.next_function is not None:
            raise RuntimeError("next_function is already set")
        self.next_function = next_function
        return

    def process_query(self, query: Query, call_next: QueryMiddlewareCallable) -> Response:
        """Handle an incoming query.

        Child classes should override this function (if they do not this middleware will
        simply pass the query onto the next function).

        Args:
            query: the incoming query
            call_next: the next function in the chain
        """
        return call_next(query)


class ExceptionHandlerMiddleware(QueryMiddleware):
    """Middleware for handling exceptions originating from a `QueryMiddleware` stack.

    Allows registering handlers for individual `Exception` types. Only one handler can
    exist for a given `Exception` type.

    When an exception is encountered, the middleware will search for the first handler that
    matches the class or parent class of the exception in method resolution order. If no handler
    is registered will use this classes `self.default_exception_handler`.

    New in `1.1.0`.

    Attributes:
        exception_handlers: registered exception handlers
    """

    def __init__(
        self, exception_handlers: Optional[Dict[Type[Exception], ExceptionHandler]] = None
    ) -> None:
        """
        Args:
            exception_handlers: exception handlers to assign
        """
        super().__init__()
        self.exception_handlers = exception_handlers if exception_handlers is not None else {}
        return

    def process_query(self, query: Query, call_next: QueryMiddlewareCallable) -> Response:
        """Call the next function catching any handling any errors"""
        try:
            response = call_next(query)
        except Exception as e:  # pylint: disable=broad-except
            handler = self.get_exception_handler(e)
            response = handler(query, e)
        return response

    def get_exception_handler(self, exception: Exception) -> ExceptionHandler:
        """Get the exception handler for an `Exception`.

        Args:
            exception: the exception we wish to handle
        """
        for class_ in inspect.getmro(exception.__class__):
            if class_ in self.exception_handlers:
                return self.exception_handlers[class_]
        # No exception handler found - use default handler
        return self.default_exception_handler

    @staticmethod
    def default_exception_handler(query: Query, exception: Exception) -> Response:
        """The default exception handler"""
        # pylint: disable=unused-argument
        return Response(error_code=dnslib.RCODE.SERVFAIL)


class HookMiddleware(QueryMiddleware):
    """Middleware for processing hook functions

    There are three types of hooks:

    `before_first_query` hooks will be run once at the time that the first query
    is received. They take no arguments and return no results. These are guaranteed
    to run at most once - however if any hook fails it will cause no other hooks to
    be run. Subsequent queries will continue to be processed regardless of if all
    `before_first_query` hooks ran or not.

    `before_query` hooks will be run before each request. They receive a `Query`
    as an argument. If a hooks returns a non `None` result, process will skip to
    result processing.

    `after_query` hooks will be run after a result has been returned from a `before_query`
    hook or from the next function in the middleware chain. They take a `Response` input
    and must return a `Response`.

    New in `1.1.0`.

    Attributes:
        before_first_query: `before_first_query` hooks
        before_query: `before_query` hooks
        after_query: `after_query` hooks
        before_first_query_run: have we run the `before_first_query` hooks
        before_first_query_failed: did any `before_first_query` hooks fail
    """

    def __init__(
        self,
        before_first_query: Optional[List[BeforeFirstQueryHook]] = None,
        before_query: Optional[List[BeforeQueryHook]] = None,
        after_query: Optional[List[AfterQueryHook]] = None,
    ) -> None:
        """
        Args:
            before_first_query: initial `before_first_query` hooks to register
            before_query: initial `before_query` hooks to register
            after_query: initial `after_query` hooks to register
        """
        super().__init__()
        self.before_first_query: List[BeforeFirstQueryHook] = (
            before_first_query if before_first_query is not None else []
        )
        self.before_query: List[BeforeQueryHook] = before_query if before_query is not None else []
        self.after_query: List[AfterQueryHook] = after_query if after_query is not None else []

        self.before_first_query_run: bool = False
        self.before_first_query_failed: bool = False
        self._before_first_query_lock = threading.Lock()
        return

    def process_query(self, query: Query, call_next: QueryMiddlewareCallable) -> Response:
        """Process a query running relevant hooks."""
        with self._before_first_query_lock:
            if not self.before_first_query_run:
                # self._debug("Running before_first_query")
                self.before_first_query_run = True
                try:
                    for before_first_query_hook in self.before_first_query:
                        # self._vdebug(f"Running before_first_query func: {hook}")
                        before_first_query_hook()
                except Exception:
                    self.before_first_query_failed = True
                    raise

        result: RuleResult

        for before_query_hook in self.before_query:
            result = before_query_hook(query)
            if result is not None:
                # self._debug(f"Got result from before_hook: {hook}")
                break
        else:
            # No before query hooks returned a response - keep going
            result = call_next(query)

        response = coerce_to_response(result)

        for after_query_hook in self.after_query:
            response = after_query_hook(response)

        return response


# Final callable
# ..............................................................................
# This is not a QueryMiddleware - it is however the end of the line for all QueryMiddleware
class RuleProcessor:
    """Find and run a matching rule function.

    This class serves as the bottom of the `QueryMiddleware` stack.

    New in `1.1.0`.
    """

    def __init__(self, rules: List[RuleBase]) -> None:
        """
        Args:
            rules: rules to run against
        """
        self.rules = rules
        return

    def __call__(self, query: Query) -> Response:
        for rule in self.rules:
            rule_func = rule.get_func(query)
            if rule_func is not None:
                # self._info(f"Matched Rule: {rule}")
                return coerce_to_response(rule_func(query))

        # self._info("Did not match any rule")
        return Response(error_code=dnslib.RCODE.NXDOMAIN)


## Raw Middleware
## -----------------------------------------------------------------------------
class RawRecordMiddleware:
    """Middleware to be run against raw `dnslib.DNSRecord`s.

    New in `1.1.0`.
    """

    def __init__(self) -> None:
        self.next_function: Optional[RawRecordMiddlewareCallable] = None
        return

    def __call__(self, record: dnslib.DNSRecord) -> None:
        if self.next_function is None:
            raise RuntimeError("next_function is not set")
        return self.process_record(record, self.next_function)

    def register_next_function(self, next_function: RawRecordMiddlewareCallable) -> None:
        """Set the `next_function` of this middleware"""
        if self.next_function is not None:
            raise RuntimeError("next_function is already set")
        self.next_function = next_function
        return

    def process_record(
        self, record: dnslib.DNSRecord, call_next: RawRecordMiddlewareCallable
    ) -> dnslib.DNSRecord:
        """Handle an incoming record.

        Child classes should override this function (if they do not this middleware will
        simply pass the record onto the next function).

        Args:
            record: the incoming record
            call_next: the next function in the chain
        """
        return call_next(record)


class RawRecordExceptionHandlerMiddleware(RawRecordMiddleware):
    """Middleware for handling exceptions originating from a `RawRecordMiddleware` stack.

    Allows registering handlers for individual `Exception` types. Only one handler can
    exist for a given `Exception` type.

    When an exception is encountered, the middleware will search for the first handler that
    matches the class or parent class of the exception in method resolution order. If no handler
    is registered will use this classes `self.default_exception_handler`.

    Danger: Important
        Exception handlers are expected to be robust - that is, they must always
        return correctly even if they internally encounter an `Exception`.

    New in `1.1.0`.

    Attributes:
        exception_handlers: registered exception handlers
    """

    def __init__(
        self, exception_handlers: Optional[Dict[Type[Exception], RawRecordExceptionHandler]] = None
    ) -> None:
        super().__init__()
        self.exception_handlers: Dict[Type[Exception], RawRecordExceptionHandler] = (
            exception_handlers if exception_handlers is not None else {}
        )
        return

    def process_record(
        self, record: dnslib.DNSRecord, call_next: RawRecordMiddlewareCallable
    ) -> dnslib.DNSRecord:
        """Call the next function handling any exceptions that arise"""
        try:
            response = call_next(record)
        except Exception as e:  # pylint: disable=broad-except
            handler = self.get_exception_handler(e)
            response = handler(record, e)
        return response

    def get_exception_handler(self, exception: Exception) -> RawRecordExceptionHandler:
        """Get the exception handler for the given exception

        Args:
            exception: the exception we wish to handle
        """
        for class_ in inspect.getmro(exception.__class__):
            if class_ in self.exception_handlers:
                return self.exception_handlers[class_]
        # No exception handler found - use default handler
        return self.default_exception_handler

    @staticmethod
    def default_exception_handler(
        record: dnslib.DNSRecord, exception: Exception
    ) -> dnslib.DNSRecord:
        """Default exception handler"""
        # pylint: disable=unused-argument
        response = record.reply()
        response.header.rcode = dnslib.RCODE.SERVFAIL
        return response


# Final Callable
# ..............................................................................
# This is not a RawRcordMiddleware - it is however the end of the line for all RawRecordMiddleware
class QueryMiddlewareProcessor:
    """Convert an incoming DNS record and pass it to a `QueryMiddleware` stack.

    This class serves as the bottom of the `RawRcordMiddleware` stack.

    New in `1.1.0`.
    """

    def __init__(self, query_middleware: QueryMiddlewareCallable) -> None:
        """
        Args:
            query_middleware: the top of the middleware stack
        """
        self.query_middleware = query_middleware
        return

    def __call__(self, record: dnslib.DNSRecord) -> dnslib.DNSRecord:
        response = record.reply()

        if record.header.opcode != dnslib.OPCODE.QUERY:
            # self._info(f"Received non-query opcode: {record.header.opcode}")
            # This server only response to DNS queries
            response.header.rcode = dnslib.RCODE.NOTIMP
            return response

        if len(record.questions) != 1:
            # self._info(f"Received len(questions_ != 1 ({record.questions})")
            # To simplify things we only respond if there is 1 question.
            # This is apparently common amongst DNS server implementations.
            # For more information see the responses to this SO question:
            # https://stackoverflow.com/q/4082081
            response.header.rcode = dnslib.RCODE.REFUSED
            return response

        try:
            query = Query.from_dns_question(record.questions[0])
        except ValueError:
            # self._warning(e)
            response.header.rcode = dnslib.RCODE.FORMERR
            return response

        result = self.query_middleware(query)

        response.add_answer(*result.get_answer_records())
        response.add_ar(*result.get_additional_records())
        response.add_auth(*result.get_authority_records())
        response.header.rcode = result.error_code
        return response
