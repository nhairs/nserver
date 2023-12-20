# Error Handling

Custom exception handling is handled through the [`ExceptionHandlerMiddleware`][nserver.middleware.ExceptionHandlerMiddleware] and [`RawRecordExceptionHandlerMiddleware`][nserver.middleware.RawRecordExceptionHandlerMiddleware] [Middleware][middleware]. These middleware will catch any `Exception`s raised by their respective middleware stacks.

Error handling requires `nserver>=2.0`

In general you are probably able to use the `ExceptionHandlerMiddleware` as the `RawRecordExceptionHandlerMiddleware` is only needed to catch exceptions resulting from `RawRecordMiddleware` or broken exception handlers in the `ExceptionHandlerMiddleware`. If you only write `QueryMiddleware` and your `ExceptionHandlerMiddleware` handlers never raise exceptions then you'll be good to go with just the `ExceptionHandlerMiddleware`.

Both of these middleware have a default exception handler that will be used for anything not matching a registered handler. The default handler can be overwritten by registering a handler for the `Exception` class.

Handlers are chosen by finding a handler for the most specific parent class of the thrown exception (including the class of the exception). These classes are searched in method resolution order.

!!! note
    These handlers only handle exceptions that are subclasses of (and including) `Exception`. Exceptions that are only children of `BaseException` (e.g. `SystemExit`) will not be caught by these handlers.

## Registering Exception Handlers

```python
import dnslib
from nserver import NameServer, Query, Response

server = NameServer("example")

@server.exception_handler(NotImplementedError)
def not_implemented_handler(exception: NotImplementedError, query: Query) -> Response:
    return Response(error_code=dnslib.RCODE.NOTIMPL)

@server.raw_exception_handler(Exception)
def print_debugger(exception: Exception, record: dnslib.DNSRecord) -> dnslib.DNSRecord:
    print(f"failed to process {record} due to {exception!r})
    response = record.reply()
    response.header.rcode =dnslib.RCODE.SERVFAIL
    return response
```
