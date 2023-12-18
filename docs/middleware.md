# Middleware

Middleware can be used to modify the behaviour of a server seperate to the individual rules that are registered to the server. Middleware is run on all requests and can modify both the input and response of a request.

Middleware requires `nserver>=1.1.0`

## Middleware Stacks

Middleware operates in a stack with each middleware calling the middleware below it until one returns and the result is propagated back up the chain. NServer uses two stacks, the outmost stack deals with raw DNS records (`RawRecordMiddleware`), which will eventually convert the record to a `Query` which will then be passed to the main `QueryMiddleware` stack.

Middleware can be added to the application until it is run. Once the server begins running the middleware cannot be modified. The ordering of middleware is kept in the order in which it is added to the server; that is the first middleware registered will be called before the second and so on.

Some middleware is automatically added when the stacks are processed.

## `QueryMiddleware`

For most use cases you likely want to use [`QueryMiddleware`][nserver.middleware.QueryMiddleware]. This middleware uses the high-level `Query` and `Response` objects.

### Registering `QueryMiddleware`

```python
from nserver import NameServer
from nserver.middleware import QueryMiddleware

server = NameServer("example")
server.register_middleware(QueryMiddleware())
```

### Creating your own `QueryMiddleware`

Using an unmodified `QueryMiddleware` isn't very interesting as it just passes the request onto the next middleware. To add your own middleware you should subclass `QueryMiddleware` and override the `process_query` method.

```python
# ...
from typing import Callable
from nserver import Query, Response

class MyLoggingMiddleware(QueryMiddleware):
    def __init__(self, logging_name: str):
        super().__init__()
        self.logger = logging.getLogger(f"my-awesome-app.{name}")
        return

    def process_query(
        query: Query, call_next: Callable[[Query], Response]
    ) -> Response:
        self.logger.info(f"processing {query.name}")
        response = call_next(query)
        self.logger.info(f"done processing, returning {response.error_code}")
        return response

server.register_middleware(MyLoggingMiddleware("foo"))
server.register_middleware(MyLoggingMiddleware("bar"))
```

### Default `QueryMiddleware` stack

Once processed the `QueryMiddleware` stack will look as follows:

- [`ExceptionHandlerMiddleware`][nserver.middleware.ExceptionHandlerMiddleware]
  - Customisable error handler for `Exception`s originating from within the stack.
- `<registered middleware>`
- [`HookMiddleware`][nserver.middleware.HookMiddleware]
  - Runs hooks registered to the server. This can be considered a simplified version of middleware.
- [`RuleProcessor`][nserver.middleware.RuleProcessor]
  - The entry point into our rule processing.


## `RawRecordMiddleware`

[`RawRecordMiddleware`][nserver.middleware.RawRecordMiddleware] allows for modifying the raw `dnslib.DNSRecord`s that are recevied and sent by the server.

### Registering `RawRecordMiddleware`

```python
# ...
from nserver.middleware import RawRecordMiddleware

server.register_raw_middleware(RawRecordMiddleware())
```

### Creating your own `RawRecordMiddleware`

Using an unmodified `RawRecordMiddleware` isn't very interesting as it just passes the request onto the next middleware. To add your own middleware you should subclass `RawRecordMiddleware` and override the `process_record` method.

```python
# ...

class SizeLimiterMiddleware(RawRecordMiddleware):
    def __init__(self, max_size: int):
        super().__init__()
        self.max_size = max_size
        return

    def process_record(
        record: dnslib.DNSRecord,
        call_next: Callable[[dnslib.DNSRecord], dnslib.DNSRecord],
    ) -> dnslib.DNSRecord:
        refused = record.reply()
        refused.header.rcode = dnslib.RCODE.REFUSED

        if len(record.pack()) > self.max_size:
            return refused

        response = call_next(query)

        if len(response.pack()) > self.max_size:
            return refused

        return response

server.register_raw_middleware(SizeLimiterMiddleware(1400))
```

### Default `RawRecordMiddleware` stack

Once processed the `RawRecordMiddleware` stack will look as follows:

- [`RawRecordExceptionHandlerMiddleware`][nserver.middleware.RawRecordExceptionHandlerMiddleware]
  - Customisable error handler for `Exception`s originating from within the stack.
- `<registered raw middleware>`
- [`QueryMiddlewareProcessor`][nserver.middleware.QueryMiddlewareProcessor]
  - entry point into the `QueryMiddleware` stack.
