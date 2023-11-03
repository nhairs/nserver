# pylint: disable=missing-class-docstring,missing-function-docstring,protected-access

### IMPORTS
### ============================================================================
## Standard Library
import re
from typing import List
import unittest.mock

## Installed
import dnslib
import pytest

from nserver import NameServer, Query, Response, A, RegexRule, WildcardStringRule

## Application

### SETUP
### ============================================================================
IP = "127.0.0.1"
server = NameServer("tests")


@server.rule("dummy.com", ["A"])
def dummy_rule(query: Query) -> A:
    return A(query.name, IP)


@server.rule("wildcard-rule-expected.com", ["A"])
def wildcard_rule_expected(query: Query) -> A:
    return A(query.name, IP)


@server.rule(re.compile(r"regex-rule-expected\.com"), ["A"])
def regex_rule_expected(query: Query) -> A:
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


hook_before_first_query_nothing = unittest.mock.MagicMock(wraps=lambda: None)
server.register_before_first_query(hook_before_first_query_nothing)

hook_before_query_nothing = unittest.mock.MagicMock(wraps=lambda q: None)
server.register_before_query(hook_before_query_nothing)

hook_after_query_nothing = unittest.mock.MagicMock(wraps=lambda r: r)
server.register_after_query(hook_after_query_nothing)


### TESTS
### ============================================================================
## NameServer.rule
## -----------------------------------------------------------------------------
def test_rule_decorator_type():
    wildcard_tested = False
    regex_tested = False

    for rule in server.rules:
        if rule.func is wildcard_rule_expected:
            wildcard_tested = True
            assert isinstance(rule, WildcardStringRule)
        elif rule.func is regex_rule_expected:
            regex_tested = True
            assert isinstance(rule, RegexRule)

    # Check all tests run
    assert all([wildcard_tested, regex_tested])
    return


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
    server._before_first_query_run = False
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
