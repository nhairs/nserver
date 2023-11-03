### IMPORTS
### ============================================================================
## Standard Library
from typing import Optional, Union, List

## Installed
import dnslib

## Application
from .records import RecordBase


### CLASSES
### ============================================================================
class Query:  # pylint: disable=too-few-public-methods
    """Simplified version of a DNS query.

    This class acts as an adaptor for dnslib classes.

    Attributes:
        type: DNS Query Type
        name: DNS query domain name. Note: `.` is stripped by default, as such the "root"
            will be `""` (empty string) rather than `"."`.
    """

    def __init__(self, qtype: str, name: str) -> None:
        """
        Args:
            qtype: The DNS Query Type in string form
            name: The name of the query
        """
        qtype = qtype.upper()
        if qtype not in dnslib.QTYPE.reverse:
            raise ValueError(f"Unsupported QTYPE {qtype!r}")
        self.type = qtype
        self.name = name
        return

    @classmethod
    def from_dns_question(cls, question: dnslib.DNSQuestion) -> "Query":
        """Create a new query from a `dnslib.DNSQuestion`"""
        if question.qtype not in dnslib.QTYPE.forward:
            raise ValueError(f"Invalid QTYPE: {question.qtype}")

        query = cls(dnslib.QTYPE[question.qtype], str(question.qname).rstrip("."))
        return query

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.type!r}, {self.name!r})"

    def __str__(self) -> str:
        return self.__repr__()


## Response Classes
## -----------------------------------------------------------------------------
OptionalRecordList = Optional[Union[RecordBase, List[RecordBase]]]


class Response:
    """Simplified version of a DNS response.

    This class acts as an adaptor for dnslib classes.
    """

    def __init__(
        self,
        answers: OptionalRecordList = None,
        additional: OptionalRecordList = None,
        authority: OptionalRecordList = None,
        error_code: int = dnslib.RCODE.NOERROR,
    ) -> None:
        """
        Args:
            answers: response answer records
            additional: response additional records
            authority: response authority records
            error_code: DNS response error code
        """
        if answers is None:
            answers = []
        elif isinstance(answers, RecordBase):
            answers = [answers]
        self.answers = answers

        if additional is None:
            additional = []
        elif isinstance(additional, RecordBase):
            additional = [additional]
        self.additional = additional

        if authority is None:
            authority = []
        elif isinstance(authority, RecordBase):
            authority = [authority]
        self.authority = authority

        if error_code not in dnslib.RCODE.forward:
            raise ValueError(f"Unknown RCODE: {error_code}")
        self.error_code = error_code
        return

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(answers={self.answers!r}, additional={self.additional!r}, authority={self.authority!r}, error_code={self.error_code!r})"

    def __str__(self) -> str:
        return self.__repr__()

    def get_answer_records(self) -> List[dnslib.RD]:
        """Prepare resource records for answer section"""
        return [record.to_resource_record() for record in self.answers]

    def get_additional_records(self) -> List[dnslib.RD]:
        """Prepare resource records for additional section"""
        return [record.to_resource_record() for record in self.additional]

    def get_authority_records(self) -> List[dnslib.RD]:
        """Prepare resource records for authority section"""
        return [record.to_resource_record() for record in self.authority]
