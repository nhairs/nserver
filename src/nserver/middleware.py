### IMPORTS
### ============================================================================
## Future
from __future__ import annotations

## Standard Library
import inspect
import threading
from typing import TYPE_CHECKING, Callable, Generic, TypeVar
import sys

if sys.version_info < (3, 10):
    from typing_extensions import TypeAlias
else:
    from typing import TypeAlias

## Installed
import dnslib
from pillar.logging import LoggingMixin

## Application
from .models import Query, Response
from .rules import coerce_to_response, RuleResult

### CONSTANTS
### ============================================================================
# pylint: disable=invalid-name
T_request = TypeVar("T_request")
T_response = TypeVar("T_response")
# pylint: enable=invalid-name

## Query Middleware
## -----------------------------------------------------------------------------
QueryCallable: TypeAlias = Callable[[Query], Response]
"""Type alias for functions that can be used with `QueryMiddleware.next_function`"""

QueryExceptionHandler: TypeAlias = Callable[[Query, Exception], Response]
"""Type alias for `ExceptionHandlerMiddleware` exception handler functions"""

# Hooks
BeforeFirstQueryHook: TypeAlias = Callable[[], None]
"""Type alias for `HookMiddleware.before_first_query` functions."""

BeforeQueryHook: TypeAlias = Callable[[Query], RuleResult]
"""Type alias for `HookMiddleware.before_query` functions."""

AfterQueryHook: TypeAlias = Callable[[Response], Response]
"""Type alias for `HookMiddleware.after_query` functions."""

## RawRecordMiddleware
## -----------------------------------------------------------------------------
if TYPE_CHECKING:

    class RawRecord(dnslib.DNSRecord):
        "Dummy class for type checking as dnslib is not typed"

else:
    RawRecord: TypeAlias = dnslib.DNSRecord
    """Type alias for raw records to allow easy changing of implementation details"""

RawMiddlewareCallable: TypeAlias = Callable[[RawRecord], RawRecord]
"""Type alias for functions that can be used with `RawRecordMiddleware.next_function`"""

RawExceptionHandler: TypeAlias = Callable[[RawRecord, Exception], RawRecord]
"""Type alias for `RawRecordExceptionHandlerMiddleware` exception handler functions"""


### CLASSES
### ============================================================================
## Generic Base Classes
## -----------------------------------------------------------------------------
class MiddlewareBase(Generic[T_request, T_response], LoggingMixin):
    """Generic base class for middleware classes.

    New in `3.0`.
    """

    def __init__(self) -> None:
        self.next_function: Callable[[T_request], T_response] | None = None
        self.logger = self.get_logger()
        return

    def __call__(self, request: T_request) -> T_response:
        """Call this middleware

        Args:
            request: request to process

        Raises:
            RuntimeError: If `next_function` is not set.
        """

        if self.next_function is None:
            raise RuntimeError("next_function is not set. Need to call register_next_function.")
        return self.process_request(request, self.next_function)

    def set_next_function(self, next_function: Callable[[T_request], T_response]) -> None:
        """Set the `next_function` of this middleware

        Args:
            next_function: Callable that this middleware should call next.
        """
        if self.next_function is not None:
            raise RuntimeError(f"next_function is already set to {self.next_function}")
        self.next_function = next_function
        return

    def process_request(
        self, request: T_request, call_next: Callable[[T_request], T_response]
    ) -> T_response:
        """Process a given request

        Child classes should override this method with their own logic.
        """
        return call_next(request)


class ExceptionHandlerBase(MiddlewareBase[T_request, T_response]):
    """Generic base class for middleware exception handlers

    Attributes:
        handlers: registered exception handlers

    New in `3.0`.
    """

    def __init__(
        self,
        handlers: dict[type[Exception], Callable[[T_request, Exception], T_response]] | None = None,
    ) -> None:
        super().__init__()
        self.handlers: dict[type[Exception], Callable[[T_request, Exception], T_response]] = (
            handlers if handlers is not None else {}
        )
        return

    def process_request(self, request, call_next):
        """Call the next function handling any exceptions that arise"""
        try:
            response = call_next(request)
        except Exception as e:  # pylint: disable=broad-except
            handler = self.get_handler(e)
            response = handler(request, e)
        return response

    def set_handler(
        self,
        exception_class: type[Exception],
        handler: Callable[[T_request, Exception], T_response],
        *,
        allow_overwrite: bool = False,
    ) -> None:
        """Add an exception handler for the given exception class

        Args:
            exception_class: Exceptions to associate with this handler.
            handler: The handler to add.
            allow_overwrite: Allow overwriting existing handlers.

        Raises:
            ValueError: If a handler already exists for the given exception and
                `allow_overwrite` is `False`.
        """
        if exception_class in self.handlers and not allow_overwrite:
            raise ValueError(
                f"Exception handler already exists for {exception_class} and allow_overwrite is False"
            )
        self.handlers[exception_class] = handler
        return

    def get_handler(self, exception: Exception) -> Callable[[T_request, Exception], T_response]:
        """Get the exception handler for the given exception

        Args:
            exception: the exception we wish to handle
        """
        for class_ in inspect.getmro(exception.__class__):
            if class_ in self.handlers:
                return self.handlers[class_]
        # No exception handler found - use default handler
        return self.default_handler

    @staticmethod
    def default_handler(request: T_request, exception: Exception) -> T_response:
        """Default exception handler

        Child classes MUST override this method.
        """
        raise NotImplementedError("Must overide this method")


## Request Middleware
## -----------------------------------------------------------------------------
class QueryMiddleware(MiddlewareBase[Query, Response]):
    """Middleware for interacting with `Query` objects

    New in `3.0`.
    """


class QueryExceptionHandlerMiddleware(ExceptionHandlerBase[Query, Response], QueryMiddleware):
    """Middleware for handling exceptions originating from a `QueryMiddleware` stack.

    Allows registering handlers for individual `Exception` types. Only one handler can
    exist for a given `Exception` type.

    When an exception is encountered, the middleware will search for the first handler that
    matches the class or parent class of the exception in method resolution order. If no handler
    is registered will use this classes `self.default_exception_handler`.

    New in `3.0`.
    """

    @staticmethod
    def default_handler(request: Query, exception: Exception) -> Response:
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

    Attributes:
        before_first_query: `before_first_query` hooks
        before_query: `before_query` hooks
        after_query: `after_query` hooks
        before_first_query_run: have we run the `before_first_query` hooks
        before_first_query_failed: did any `before_first_query` hooks fail

    New in `3.0`.
    """

    def __init__(
        self,
        before_first_query: list[BeforeFirstQueryHook] | None = None,
        before_query: list[BeforeQueryHook] | None = None,
        after_query: list[AfterQueryHook] | None = None,
    ) -> None:
        """
        Args:
            before_first_query: initial `before_first_query` hooks to register
            before_query: initial `before_query` hooks to register
            after_query: initial `after_query` hooks to register
        """
        super().__init__()
        self.before_first_query: list[BeforeFirstQueryHook] = (
            before_first_query if before_first_query is not None else []
        )
        self.before_query: list[BeforeQueryHook] = before_query if before_query is not None else []
        self.after_query: list[AfterQueryHook] = after_query if after_query is not None else []

        self.before_first_query_run: bool = False
        self.before_first_query_failed: bool = False
        self._before_first_query_lock = threading.Lock()
        return

    def process_request(self, request: Query, call_next: QueryCallable) -> Response:
        with self._before_first_query_lock:
            if not self.before_first_query_run:
                self.before_first_query_run = True
                try:
                    for before_first_query_hook in self.before_first_query:
                        self.vdebug(f"Running before_first_query_hook: {before_first_query_hook}")
                        before_first_query_hook()
                except Exception:
                    self.before_first_query_failed = True
                    raise

        result: RuleResult

        for before_query_hook in self.before_query:
            self.vdebug(f"Running before_query_hook: {before_query_hook}")
            result = before_query_hook(request)
            if result is not None:
                self.debug(f"Got result from before_query_hook: {before_query_hook}")
                break
        else:
            # No before query hooks returned a response - keep going
            result = call_next(request)

        response = coerce_to_response(result)

        for after_query_hook in self.after_query:
            self.vdebug(f"Running after_query_hook: {after_query_hook}")
            response = after_query_hook(response)

        return response


## Raw Middleware
## -----------------------------------------------------------------------------
class RawMiddleware(MiddlewareBase[RawRecord, RawRecord]):
    """Middleware to be run against raw `dnslib.DNSRecord`s.

    New in `3.0`.
    """


class RawExceptionHandlerMiddleware(ExceptionHandlerBase[RawRecord, RawRecord]):
    """Middleware for handling exceptions originating from a `RawRecordMiddleware` stack.

    Allows registering handlers for individual `Exception` types. Only one handler can
    exist for a given `Exception` type.

    When an exception is encountered, the middleware will search for the first handler that
    matches the class or parent class of the exception in method resolution order. If no handler
    is registered will use this classes `self.default_handler`.

    Danger: Important
        Exception handlers are expected to be robust - that is, they must always
        return correctly even if they internally encounter an `Exception`.

    Attributes:
        handlers: registered exception handlers

    New in `3.0`.
    """

    @staticmethod
    def default_handler(request: RawRecord, exception: Exception) -> RawRecord:
        """Default exception handler"""
        # pylint: disable=unused-argument
        response = request.reply()
        response.header.rcode = dnslib.RCODE.SERVFAIL
        return response


### TYPE_CHECKING
### ============================================================================
if TYPE_CHECKING and False:  # pylint: disable=condition-evals-to-constant
    # pylint: disable=undefined-variable
    q1 = QueryExceptionHandlerMiddleware()
    reveal_type(q1)
    reveal_type(q1.handlers)
    reveal_type(q1.default_handler)
    r1 = RawExceptionHandlerMiddleware()
    reveal_type(r1)
    reveal_type(r1.handlers)
    reveal_type(r1.default_handler)
