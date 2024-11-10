# pylint: disable=missing-class-docstring,missing-function-docstring,protected-access

### IMPORTS
### ============================================================================
## Standard Library
## Installed
import dnslib
import pytest

from nserver import NameServer, RawNameServer, Blueprint, Query, A

## Application

### SETUP
### ============================================================================
IP = "127.0.0.1"
server = NameServer("test_blueprint")
blueprint_1 = Blueprint("blueprint_1")
blueprint_2 = Blueprint("blueprint_2")
blueprint_3 = Blueprint("blueprint_3")
raw_server = RawNameServer(server)


## Rules
## -----------------------------------------------------------------------------
@server.rule("s.com", ["A"])
@blueprint_1.rule("b1.com", ["A"])
@blueprint_2.rule("b2.com", ["A"])
@blueprint_3.rule("b3.b2.com", ["A"])
def dummy_rule(query: Query) -> A:
    return A(query.name, IP)


## Get server ready
## -----------------------------------------------------------------------------
server.register_rule(blueprint_1)
server.register_rule(blueprint_2)
blueprint_2.register_rule(blueprint_3)


### TESTS
### ============================================================================
## Responses
## -----------------------------------------------------------------------------
@pytest.mark.parametrize("question", ["s.com", "b1.com", "b2.com", "b3.b2.com"])
def test_response(question: str):
    response = raw_server.process_request(dnslib.DNSRecord.question(question))
    assert len(response.rr) == 1
    assert response.rr[0].rtype == 1
    assert response.rr[0].rname == question
    return


@pytest.mark.parametrize("question", ["miss.s.com", "miss.b1.com", "miss.b2.com", "miss.b3.b2.com"])
def test_nxdomain(question: str):
    response = raw_server.process_request(dnslib.DNSRecord.question(question))
    assert len(response.rr) == 0
    assert response.header.rcode == dnslib.RCODE.NXDOMAIN
    return
