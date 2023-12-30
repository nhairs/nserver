# pylint: disable=missing-class-docstring,missing-function-docstring,protected-access

### IMPORTS
### ============================================================================
## Standard Library
from typing import no_type_check, List
import unittest.mock

## Installed
import dnslib
import pytest

from nserver import NameServer, SubServer, Query, Response, ALL_QTYPES, ZoneRule, A
from nserver.server import ServerBase

## Application

### SETUP
### ============================================================================
IP = "127.0.0.1"
nameserver = NameServer("test_subserver")
subserver_1 = SubServer("subserver_1")
subserver_2 = SubServer("subserver_2")
subserver_3 = SubServer("subserver_3")


## Rules
## -----------------------------------------------------------------------------
@nameserver.rule("s.com", ["A"])
@subserver_1.rule("sub1.com", ["A"])
@subserver_2.rule("sub2.com", ["A"])
@subserver_3.rule("sub3.sub2.com", ["A"])
def dummy_rule(query: Query) -> A:
    return A(query.name, IP)


## Hooks
## -----------------------------------------------------------------------------
def register_hooks(server: ServerBase) -> None:
    server.register_before_first_query(unittest.mock.MagicMock(wraps=lambda: None))
    server.register_before_query(unittest.mock.MagicMock(wraps=lambda q: None))
    server.register_after_query(unittest.mock.MagicMock(wraps=lambda r: r))
    return


@no_type_check
def reset_hooks(server: ServerBase) -> None:
    server.hook_middleware.before_first_query_run = False
    server.hook_middleware.before_first_query[0].reset_mock()
    server.hook_middleware.before_query[0].reset_mock()
    server.hook_middleware.after_query[0].reset_mock()
    return


def reset_all_hooks() -> None:
    reset_hooks(nameserver)
    reset_hooks(subserver_1)
    reset_hooks(subserver_2)
    reset_hooks(subserver_3)
    return


@no_type_check
def check_hook_call_count(server: ServerBase, bfq_count: int, bq_count: int, aq_count: int) -> None:
    assert server.hook_middleware.before_first_query[0].call_count == bfq_count
    assert server.hook_middleware.before_query[0].call_count == bq_count
    assert server.hook_middleware.after_query[0].call_count == aq_count
    return


register_hooks(nameserver)
register_hooks(subserver_1)
register_hooks(subserver_2)
register_hooks(subserver_3)


## Exception handling
## -----------------------------------------------------------------------------
class ErrorForTesting(Exception):
    pass


@nameserver.rule("throw-error.com", ["A"])
def throw_error(query: Query) -> None:
    raise ErrorForTesting()


def _query_error_handler(query: Query, exception: Exception) -> Response:
    # pylint: disable=unused-argument
    return Response(error_code=dnslib.RCODE.SERVFAIL)


query_error_handler = unittest.mock.MagicMock(wraps=_query_error_handler)
nameserver.register_exception_handler(ErrorForTesting, query_error_handler)


class ThrowAnotherError(Exception):
    pass


@nameserver.rule("throw-another-error.com", ["A"])
def throw_another_error(query: Query) -> None:
    raise ThrowAnotherError()


def bad_error_handler(query: Query, exception: Exception) -> Response:
    # pylint: disable=unused-argument
    raise ErrorForTesting()


nameserver.register_exception_handler(ThrowAnotherError, bad_error_handler)


def _raw_record_error_handler(record: dnslib.DNSRecord, exception: Exception) -> dnslib.DNSRecord:
    # pylint: disable=unused-argument
    response = record.reply()
    response.header.rcode = dnslib.RCODE.SERVFAIL
    return response


raw_record_error_handler = unittest.mock.MagicMock(wraps=_raw_record_error_handler)
nameserver.register_raw_exception_handler(ErrorForTesting, raw_record_error_handler)

## Get server ready
## -----------------------------------------------------------------------------
nameserver.register_subserver(subserver_1, ZoneRule, "sub1.com", ALL_QTYPES)
nameserver.register_subserver(subserver_2, ZoneRule, "sub2.com", ALL_QTYPES)
subserver_2.register_subserver(subserver_3, ZoneRule, "sub3.sub2.com", ALL_QTYPES)

nameserver._prepare_middleware_stacks()


### TESTS
### ============================================================================
## Responses
## -----------------------------------------------------------------------------
@pytest.mark.parametrize("question", ["s.com", "sub1.com", "sub2.com", "sub3.sub2.com"])
def test_response(question: str):
    response = nameserver._process_dns_record(dnslib.DNSRecord.question(question))
    assert len(response.rr) == 1
    assert response.rr[0].rtype == 1
    assert response.rr[0].rname == question
    return


@pytest.mark.parametrize(
    "question", ["miss.s.com", "miss.sub1.com", "miss.sub2.com", "miss.sub3.sub2.com"]
)
def test_nxdomain(question: str):
    response = nameserver._process_dns_record(dnslib.DNSRecord.question(question))
    assert len(response.rr) == 0
    assert response.header.rcode == dnslib.RCODE.NXDOMAIN
    return


## Hooks
## -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "question,hook_counts",
    [
        ("s.com", [1, 5, 5]),
        ("sub1.com", [1, 5, 5, 1, 5, 5]),
        ("sub2.com", [1, 5, 5, 0, 0, 0, 1, 5, 5]),
        ("sub3.sub2.com", [1, 5, 5, 0, 0, 0, 1, 5, 5, 1, 5, 5]),
    ],
)
def test_hooks(question: str, hook_counts: List[int]):
    ## Setup
    # fill unset hook_counts
    hook_counts += [0] * (12 - len(hook_counts))
    assert len(hook_counts) == 12
    # reset hooks
    reset_all_hooks()

    ## Test
    for _ in range(5):
        response = nameserver._process_dns_record(dnslib.DNSRecord.question(question))
        assert len(response.rr) == 1
        assert response.rr[0].rtype == 1
        assert response.rr[0].rname == question

    check_hook_call_count(nameserver, *hook_counts[:3])
    check_hook_call_count(subserver_1, *hook_counts[3:6])
    check_hook_call_count(subserver_2, *hook_counts[6:9])
    check_hook_call_count(subserver_3, *hook_counts[9:])
    return
