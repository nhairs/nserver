# pylint: disable=missing-class-docstring,missing-function-docstring,protected-access

### IMPORTS
### ============================================================================
## Standard Library
from typing import no_type_check, List
import unittest.mock

## Installed
import dnslib
import pytest

from nserver import NameServer, Blueprint, Query, Response, ALL_QTYPES, ZoneRule, A
from nserver.server import Scaffold

## Application

### SETUP
### ============================================================================
IP = "127.0.0.1"
server = NameServer("test_blueprint")
blueprint_1 = Blueprint("blueprint_1")
blueprint_2 = Blueprint("blueprint_2")
blueprint_3 = Blueprint("blueprint_3")


## Rules
## -----------------------------------------------------------------------------
@server.rule("s.com", ["A"])
@blueprint_1.rule("b1.com", ["A"])
@blueprint_2.rule("b2.com", ["A"])
@blueprint_3.rule("b3.b2.com", ["A"])
def dummy_rule(query: Query) -> A:
    return A(query.name, IP)


## Hooks
## -----------------------------------------------------------------------------
def register_hooks(scaff: Scaffold) -> None:
    scaff.register_before_first_query(unittest.mock.MagicMock(wraps=lambda: None))
    scaff.register_before_query(unittest.mock.MagicMock(wraps=lambda q: None))
    scaff.register_after_query(unittest.mock.MagicMock(wraps=lambda r: r))
    return


@no_type_check
def reset_hooks(scaff: Scaffold) -> None:
    scaff.hook_middleware.before_first_query_run = False
    scaff.hook_middleware.before_first_query[0].reset_mock()
    scaff.hook_middleware.before_query[0].reset_mock()
    scaff.hook_middleware.after_query[0].reset_mock()
    return


def reset_all_hooks() -> None:
    reset_hooks(server)
    reset_hooks(blueprint_1)
    reset_hooks(blueprint_2)
    reset_hooks(blueprint_3)
    return


@no_type_check
def check_hook_call_count(scaff: Scaffold, bfq_count: int, bq_count: int, aq_count: int) -> None:
    assert scaff.hook_middleware.before_first_query[0].call_count == bfq_count
    assert scaff.hook_middleware.before_query[0].call_count == bq_count
    assert scaff.hook_middleware.after_query[0].call_count == aq_count
    return


register_hooks(server)
register_hooks(blueprint_1)
register_hooks(blueprint_2)
register_hooks(blueprint_3)


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
server.register_blueprint(blueprint_1, ZoneRule, "b1.com", ALL_QTYPES)
server.register_blueprint(blueprint_2, ZoneRule, "b2.com", ALL_QTYPES)
blueprint_2.register_blueprint(blueprint_3, ZoneRule, "b3.b2.com", ALL_QTYPES)

server._prepare_middleware_stacks()


### TESTS
### ============================================================================
## Responses
## -----------------------------------------------------------------------------
@pytest.mark.parametrize("question", ["s.com", "b1.com", "b2.com", "b3.b2.com"])
def test_response(question: str):
    response = server._process_dns_record(dnslib.DNSRecord.question(question))
    assert len(response.rr) == 1
    assert response.rr[0].rtype == 1
    assert response.rr[0].rname == question
    return


@pytest.mark.parametrize("question", ["miss.s.com", "miss.b1.com", "miss.b2.com", "miss.b3.b2.com"])
def test_nxdomain(question: str):
    response = server._process_dns_record(dnslib.DNSRecord.question(question))
    assert len(response.rr) == 0
    assert response.header.rcode == dnslib.RCODE.NXDOMAIN
    return


## Hooks
## -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "question,hook_counts",
    [
        ("s.com", [1, 5, 5]),
        ("b1.com", [1, 5, 5, 1, 5, 5]),
        ("b2.com", [1, 5, 5, 0, 0, 0, 1, 5, 5]),
        ("b3.b2.com", [1, 5, 5, 0, 0, 0, 1, 5, 5, 1, 5, 5]),
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
        response = server._process_dns_record(dnslib.DNSRecord.question(question))
        assert len(response.rr) == 1
        assert response.rr[0].rtype == 1
        assert response.rr[0].rname == question

    check_hook_call_count(server, *hook_counts[:3])
    check_hook_call_count(blueprint_1, *hook_counts[3:6])
    check_hook_call_count(blueprint_2, *hook_counts[6:9])
    check_hook_call_count(blueprint_3, *hook_counts[9:])
    return
