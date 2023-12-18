# pylint: disable=missing-class-docstring,missing-function-docstring,protected-access

### IMPORTS
### ============================================================================
## Standard Library
from typing import List
import unittest.mock

## Installed
import dnslib
import pytest

from nserver import NameServer, Query, Response, A

## Application

### SETUP
### ============================================================================
IP = "127.0.0.1"
server = NameServer("tests")


## Rules
## -----------------------------------------------------------------------------
@server.rule("dummy.com", ["A"])
def dummy_rule(query: Query) -> A:
    return A(query.name, IP)


@server.rule("none-response.com", ["A"])
def none_response(query: Query) -> None:  # pylint: disable=unused-argument
    return None


@server.rule("response-response.com", ["A"])
def response_response(query: Query) -> Response:
    response = Response()
    response.answers.append(A(query.name, IP))
    return response


@server.rule("record-response.com", ["A"])
def record_response(query: Query) -> A:
    return A(query.name, IP)


@server.rule("multi-record-response.com", ["A"])
def multi_record_response(query: Query) -> List[A]:
    return [A(query.name, IP), A(query.name, IP)]


## Hooks
## -----------------------------------------------------------------------------
hook_before_first_query_nothing = unittest.mock.MagicMock(wraps=lambda: None)
server.register_before_first_query(hook_before_first_query_nothing)

hook_before_query_nothing = unittest.mock.MagicMock(wraps=lambda q: None)
server.register_before_query(hook_before_query_nothing)

hook_after_query_nothing = unittest.mock.MagicMock(wraps=lambda r: r)
server.register_after_query(hook_after_query_nothing)


## Exception handling
## -----------------------------------------------------------------------------
class ErrorForTesting(Exception):
    pass


@server.rule("throw-error.com", ["A"])
def throw_error(query: Query) -> None:
    raise ErrorForTesting()


def _query_error_handler(query: Query, exception: Exception) -> Response:
    # pylint: disable=unused-argument
    return Response(error_code=dnslib.RCODE.SERVFAIL)


query_error_handler = unittest.mock.MagicMock(wraps=_query_error_handler)
server.register_exception_handler(ErrorForTesting, query_error_handler)


class ThrowAnotherError(Exception):
    pass


@server.rule("throw-another-error.com", ["A"])
def throw_another_error(query: Query) -> None:
    raise ThrowAnotherError()


def bad_error_handler(query: Query, exception: Exception) -> Response:
    # pylint: disable=unused-argument
    raise ErrorForTesting()


server.register_exception_handler(ThrowAnotherError, bad_error_handler)


def _raw_record_error_handler(record: dnslib.DNSRecord, exception: Exception) -> dnslib.DNSRecord:
    # pylint: disable=unused-argument
    response = record.reply()
    response.header.rcode = dnslib.RCODE.SERVFAIL
    return response


raw_record_error_handler = unittest.mock.MagicMock(wraps=_raw_record_error_handler)
server.register_raw_exception_handler(ErrorForTesting, raw_record_error_handler)

## Get server ready
## -----------------------------------------------------------------------------
server._prepare_middleware_stacks()


### TESTS
### ============================================================================
## NameServer._process_dns_record
## -----------------------------------------------------------------------------
def test_none_response():
    response = server._process_dns_record(dnslib.DNSRecord.question("none-response.com"))
    assert len(response.rr) == 0
    return


def test_response_response():
    response = server._process_dns_record(dnslib.DNSRecord.question("response-response.com"))
    assert len(response.rr) == 1
    assert response.rr[0].rtype == 1
    assert response.rr[0].rname == "response-response.com."
    return


def test_record_response():
    response = server._process_dns_record(dnslib.DNSRecord.question("record-response.com"))
    assert len(response.rr) == 1
    assert response.rr[0].rtype == 1
    assert response.rr[0].rname == "record-response.com."
    return


def test_multi_record_response():
    response = server._process_dns_record(dnslib.DNSRecord.question("multi-record-response.com"))
    assert len(response.rr) == 2
    for record in response.rr:
        assert record.rtype == 1
        assert record.rname == "multi-record-response.com."
    return


## Hooks
## -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "hook,call_count",
    [
        (hook_before_first_query_nothing, 1),
        (hook_before_query_nothing, 5),
        (hook_after_query_nothing, 5),
    ],
)
def test_hook_call_count(hook, call_count):
    # Setup
    server.hook_middleware.before_first_query_run = False
    hook.reset_mock()

    # Test
    for _ in range(5):
        response = server._process_dns_record(dnslib.DNSRecord.question("dummy.com"))
        # Ensure respone returns and unchanged
        assert len(response.rr) == 1
        assert response.rr[0].rtype == 1
        assert response.rr[0].rname == "dummy.com."

    assert hook.call_count == call_count
    return


## Error Handlers
## -----------------------------------------------------------------------------
def test_query_error_handler():
    # Setup
    query_error_handler.reset_mock()
    raw_record_error_handler.reset_mock()

    # Test
    response = server._process_dns_record(dnslib.DNSRecord.question("throw-error.com"))

    assert len(response.rr) == 0
    assert response.header.get_rcode() == dnslib.RCODE.SERVFAIL

    assert query_error_handler.call_count == 1
    assert raw_record_error_handler.call_count == 0
    return


def test_raw_record_error_handler():
    # Setup
    query_error_handler.reset_mock()
    raw_record_error_handler.reset_mock()

    # Test
    response = server._process_dns_record(dnslib.DNSRecord.question("throw-another-error.com"))

    assert len(response.rr) == 0
    assert response.header.get_rcode() == dnslib.RCODE.SERVFAIL

    assert query_error_handler.call_count == 0
    assert raw_record_error_handler.call_count == 1
    return
