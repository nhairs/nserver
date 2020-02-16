### IMPORTS
### ============================================================================
## Standard Library

## Installed
import dnslib

## Application

### CLASSES
### ============================================================================
class Query:  # pylint: disable=too-few-public-methods
    """Simplified version of a DNS query.
    """

    def __init__(self, type_: str, name: str) -> None:
        type_ = type_.upper()
        if type_ not in dnslib.QTYPE.reverse:
            raise ValueError(f"Unsupported QTYPE {type_!r}")
        self.type = type_
        self.name = name
        return

    @classmethod
    def from_dns_question(cls, question):
        query = cls(dnslib.QTYPE[question.qtype], question.qname.rstrip("."))
        return query


## Response Classes
## -----------------------------------------------------------------------------
class Response:
    pass
