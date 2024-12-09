### IMPORTS
### ============================================================================
## Future
from __future__ import annotations

## Standard Library
from typing import TypeVar, Generic, Pattern

## Installed
import dnslib
from pillar.logging import LoggingMixin

## Application
from .models import Query, Response
from .rules import coerce_to_response, smart_make_rule, RuleBase, ResponseFunction

from . import middleware as m

### CONSTANTS
### ============================================================================
# pylint: disable=invalid-name
T_middleware = TypeVar("T_middleware", bound=m.MiddlewareBase)
T_exception_handler = TypeVar("T_exception_handler", bound=m.ExceptionHandlerBase)
# pylint: enable=invalid-name


### Classes
### ============================================================================
class MiddlewareMixin(Generic[T_middleware, T_exception_handler]):
    """Generic mixin for building a middleware stack in a server.

    Should not be used directly, instead use the servers that implement it:
    `NameServer`, `RawNameServer`.

    New in `3.0`.
    """

    _exception_handler: T_exception_handler

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._middleware_stack_final: list[T_middleware] | None = None
        self._middleware_stack_user: list[T_middleware] = []
        return

    ## Middleware
    ## -------------------------------------------------------------------------
    def middleware_is_prepared(self) -> bool:
        """Check if the middleware has been prepared."""
        return self._middleware_stack_final is not None

    def append_middleware(self, middleware: T_middleware) -> None:
        """Append this middleware to the middleware stack

        Args:
            middleware: middleware to append
        """
        if self.middleware_is_prepared():
            raise RuntimeError("Cannot append middleware once prepared")
        self._middleware_stack_user.append(middleware)
        return

    def prepare_middleware(self) -> None:
        """Prepare middleware for consumption

        Child classes should wrap this method to set the `next_function` on the
        final middleware in the stack.
        """
        if self.middleware_is_prepared():
            raise RuntimeError("Middleware is already prepared")

        middleware_stack = self._prepare_middleware_stack()

        next_middleware: T_middleware | None = None

        for middleware in middleware_stack[::-1]:
            if next_middleware is not None:
                middleware.set_next_function(next_middleware)
            next_middleware = middleware

        self._middleware_stack_final = middleware_stack
        return

    def _prepare_middleware_stack(self) -> list[T_middleware]:
        """Create final stack of middleware.

        Child classes may override this method to customise the final middleware stack.
        """
        return [self._exception_handler, *self._middleware_stack_user]  # type: ignore[list-item]

    @property
    def middleware(self) -> list[T_middleware]:
        """Accssor for this servers middleware.

        If the server has been prepared then returns a copy of the prepared middleware.
        Otherwise returns a mutable list of the registered middleware.
        """
        if self.middleware_is_prepared():
            return self._middleware_stack_final.copy()  # type: ignore[union-attr]
        return self._middleware_stack_user

    ## Exception Handler
    ## -------------------------------------------------------------------------
    def register_exception_handler(self, *args, **kwargs) -> None:
        """Shortcut for `self.exception_handler.set_handler`"""
        self.exception_handler_middleware.set_handler(*args, **kwargs)
        return

    @property
    def exception_handler_middleware(self) -> T_exception_handler:
        """Read only accessor for this server's middleware exception handler"""
        return self._exception_handler

    def exception_handler(self, exception_class: type[Exception]):
        """Decorator for registering a function as an raw exception handler

        Args:
            exception_class: The `Exception` class to register this handler for
        """

        def decorator(func):
            nonlocal exception_class
            self.register_raw_exception_handler(exception_class, func)
            return func

        return decorator


## Mixins
## -----------------------------------------------------------------------------
class RulesMixin(LoggingMixin):
    """Base class for rules based functionality`

    Attributes:
        rules: reistered rules

    New in `3.0`.
    """

    def __init__(self) -> None:
        super().__init__()
        self.rules: list[RuleBase] = []
        return

    def register_rule(self, rule: RuleBase) -> None:
        """Register the given rule

        Args:
            rule: the rule to register
        """
        self.vdebug(f"Registered rule: {rule!r}")
        self.rules.append(rule)
        return

    def rule(self, rule_: type[RuleBase] | str | Pattern, *args, **kwargs):
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


## Servers
## -----------------------------------------------------------------------------
class RawNameServer(
    MiddlewareMixin[m.RawMiddleware, m.RawExceptionHandlerMiddleware], LoggingMixin
):
    """Server that handles raw `dnslib.DNSRecord` queries.

    This allows interacting with the underlying DNS messages from our dns library.
    As such this server is implementation dependent and may change from time to time.

    In general you should use `NameServer` as it is implementation independent.

    New in `3.0`.
    """

    def __init__(self, nameserver: NameServer) -> None:
        self._exception_handler = m.RawExceptionHandlerMiddleware()
        super().__init__()
        self.nameserver: NameServer = nameserver
        self.logger = self.get_logger()
        return

    def process_request(self, request: m.RawRecord) -> m.RawRecord:
        """Process a request using this server.

        This will pass the request through the middleware stack.
        """
        if not self.middleware_is_prepared():
            self.prepare_middleware()
        return self.middleware[0](request)

    def send_request_to_nameserver(self, record: m.RawRecord) -> m.RawRecord:
        """Send a request to the `NameServer` of this instance.

        Although this is the final step after passing a request through all middleware,
        it can be called directly to avoid using middleware such as when testing.
        """
        response = record.reply()

        if record.header.opcode != dnslib.OPCODE.QUERY:
            self.debug(f"Received non-query opcode: {record.header.opcode}")
            # This server only response to DNS queries
            response.header.rcode = dnslib.RCODE.NOTIMP
            return response

        if len(record.questions) != 1:
            self.debug(f"Received len(questions_ != 1 ({record.questions})")
            # To simplify things we only respond if there is 1 question.
            # This is apparently common amongst DNS server implementations.
            # For more information see the responses to this SO question:
            # https://stackoverflow.com/q/4082081
            response.header.rcode = dnslib.RCODE.REFUSED
            return response

        try:
            query = Query.from_dns_question(record.questions[0])
        except ValueError:
            # TODO: should we embed raw DNS query? Maybe this should be configurable.
            self.warning("Failed to parse Query from request", exc_info=True)
            response.header.rcode = dnslib.RCODE.FORMERR
            return response

        result = self.nameserver.process_request(query)

        response.add_answer(*result.get_answer_records())
        response.add_ar(*result.get_additional_records())
        response.add_auth(*result.get_authority_records())
        response.header.rcode = result.error_code
        return response

    def prepare_middleware(self) -> None:
        super().prepare_middleware()
        self.middleware[-1].set_next_function(self.send_request_to_nameserver)
        return


class NameServer(
    MiddlewareMixin[m.QueryMiddleware, m.QueryExceptionHandlerMiddleware], RulesMixin, LoggingMixin
):
    """High level DNS Name Server for responding to DNS queries.

    *Changed in `3.0`*:

    - "Raw" functionality removed and moved to `RawNameServer`.
    - "Transport" and "Application" functionality removed.
    """

    def __init__(self, name: str) -> None:
        """
        Args:
            name: The name of the server. This is used for internal logging.
        """
        self.name = name
        self._exception_handler = m.QueryExceptionHandlerMiddleware()
        super().__init__()
        self.hooks = m.HookMiddleware()
        self.logger = self.get_logger()
        return

    def _prepare_middleware_stack(self) -> list[m.QueryMiddleware]:
        stack = super()._prepare_middleware_stack()
        stack.append(self.hooks)
        return stack

    ## Register Methods
    ## -------------------------------------------------------------------------
    def register_subserver(
        self, nameserver: NameServer, rule_: type[RuleBase] | str | Pattern, *args, **kwargs
    ) -> None:
        """Register a `NameServer` using [`smart_make_rule`][nserver.rules.smart_make_rule].

        This allows for composing larger applications.

        Args:
            subserver: the `SubServer` to attach
            rule_: rule as per `nserver.rules.smart_make_rule`
            args: extra arguments to provide `smart_make_rule`
            kwargs: extra keyword arguments to provide `smart_make_rule`

        Raises:
            ValueError: if `func` is provided in `kwargs`.

        New in `3.0`.
        """

        if "func" in kwargs:
            raise ValueError("Must not provide `func` in kwargs")
        self.register_rule(smart_make_rule(rule_, *args, func=nameserver.process_request, **kwargs))
        return

    def register_before_first_query(self, func: m.BeforeFirstQueryHook) -> None:
        """Register a function to be run before the first query.

        Args:
            func: the function to register
        """
        self.hooks.before_first_query.append(func)
        return

    def register_before_query(self, func: m.BeforeQueryHook) -> None:
        """Register a function to be run before every query.

        Args:
            func: the function to register
                If `func` returns anything other than `None` will stop processing the
                incoming `Query` and continue to result processing with the return value.
        """
        self.hooks.before_query.append(func)
        return

    def register_after_query(self, func: m.AfterQueryHook) -> None:
        """Register a function to be run on the result of a query.

        Args:
            func: the function to register
        """
        self.hooks.after_query.append(func)
        return

    # Decorators
    # ..........................................................................
    def before_first_query(self):
        """Decorator for registering before_first_query hook.

        These functions are called when the server receives it's first query, but
        before any further processesing.
        """

        def decorator(func: m.BeforeFirstQueryHook):
            self.register_before_first_query(func)
            return func

        return decorator

    def before_query(self):
        """Decorator for registering before_query hook.

        These functions are called before processing each query.
        """

        def decorator(func: m.BeforeQueryHook):
            self.register_before_query(func)
            return func

        return decorator

    def after_query(self):
        """Decorator for registering after_query hook.

        These functions are after the rule function is run and may modify the
        response.
        """

        def decorator(func: m.AfterQueryHook):
            self.register_after_query(func)
            return func

        return decorator

    ## Internal Functions
    ## -------------------------------------------------------------------------
    def process_request(self, query: Query) -> Response:
        """Process a query passing it through all middleware."""
        if not self.middleware_is_prepared():
            self.prepare_middleware()
        return self.middleware[0](query)

    def prepare_middleware(self) -> None:
        super().prepare_middleware()
        self.middleware[-1].set_next_function(self.send_query_to_rules)
        return

    def send_query_to_rules(self, query: Query) -> Response:
        """Send a query to be processed by the rules of this instance.

        Although intended to be the final step after passing a query through all middleware,
        this method can be used to bypass the middleware of this server such as for testing.
        """
        for rule in self.rules:
            rule_func = rule.get_func(query)
            if rule_func is not None:
                self.debug(f"Matched Rule: {rule}")
                return coerce_to_response(rule_func(query))

        self.debug("Did not match any rule")
        return Response(error_code=dnslib.RCODE.NXDOMAIN)


class Blueprint(RulesMixin, RuleBase, LoggingMixin):
    """A container for rules that can be registered onto a server

    It can be registered as normal rule: `server.register_rule(blueprint_rule)`

    New in `3.0`.
    """

    def __init__(self, name: str) -> None:
        """
        Args:
            name: The name of the server. This is used for internal logging.
        """
        super().__init__()
        self.name = name
        self.logger = self.get_logger()
        return

    def get_func(self, query: Query) -> ResponseFunction | None:
        for rule in self.rules:
            func = rule.get_func(query)
            if func is not None:
                self.debug(f"matched {rule}")
                return func
        self.debug("did not match any rule")
        return None
