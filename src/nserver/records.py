# pylint: disable=too-few-public-methods

### IMPORTS
### ============================================================================
## Standard Library
from ipaddress import IPv4Address, IPv6Address
import re
from typing import Any, Union, Dict

## Installed
import dnslib

## Application

### CONSTANTS
### ============================================================================
DEFAULT_TTL = 300

### CLASSES
### ============================================================================
class RecordBase:
    """Base class for all DNS records.

    NOT to be used directly.

    Subclasses must set __record_kwargs
    """

    def __init__(self, resource_name: str, ttl: int = None) -> None:
        if self.__class__ is RecordBase:
            raise RuntimeError("Do not instantiate directly - only subclass")

        type_name = self.__class__.__name__
        self.__qtype = getattr(dnslib.QTYPE, type_name)
        self.__class = getattr(dnslib, type_name)
        self.__record_kwargs: Dict[str, Any]
        self.ttl = ttl if ttl is not None else DEFAULT_TTL
        self.resource_name = resource_name
        return

    def to_resource_record(self) -> dnslib.RR:
        resource_record = dnslib.RR(
            rname=self.resource_name,
            rtype=self.__qtype,
            rdata=self.__class(self.__record_kwargs),
            ttl=self.ttl,
        )
        return resource_record


class A(RecordBase):  # pylint: disable=invalid-name
    """A (IPv4) Record.
    """

    def __init__(self, ip: Union[str, IPv4Address], **base_kwargs):
        super().__init__(**base_kwargs)

        if isinstance(ip, str):
            try:
                ip = IPv4Address(ip)
            except ValueError:
                raise ValueError("Invalid IPv4 Address")

        # Consider support int

        self.__record_kwargs = {"data": str(ip)}
        return


class AAAA(RecordBase):
    """AAAA (IPv6) Record.
    """

    def __init__(self, ip: Union[str, IPv6Address], **base_kwargs):
        super().__init__(**base_kwargs)

        if isinstance(ip, str):
            try:
                ip = IPv6Address(ip)
            except ValueError:
                raise ValueError("Invalid IPv6 Address")

        self.__record_kwargs = {"data": str(ip)}
        return


class MX(RecordBase):
    """MX Record.
    """


class TXT(RecordBase):
    """TXT Record.
    """

    def __init__(self, text: str, **base_kwargs):
        super().__init__(**base_kwargs)

        # NOTE: consider converting to bytes to allow for unicode or other.
        # Either that or enforce only ascii characters

        text_length = len(text)  # Don't keep recalculating
        if text_length <= 255:
            data = [text]
        else:
            data = []
            start_slice = 0
            end_slice = 255
            while start_slice < text_length:
                data.append(text[start_slice:end_slice])
                start_slice += 255
                end_slice += 255

        self.__record_kwargs = {"data": data}
        return


class CNAME(RecordBase):
    """CNAME Record.
    """

    regex = re.compile(r"(?:[a-z\-\_]+\.)+(?:[a-z\-\_]+)\.?")

    def __init__(self, domain: str, **base_kwargs):
        super().__init__(**base_kwargs)

        # TODO support converting unicode domains
        if not self.regex.fullmatch(domain):
            raise ValueError(f"{domain!r} is not a valid domain")

        self.__record_kwargs = {"label": domain}
        return


class NS(CNAME):
    """Name Server Record.
    """

    # Functions the same as a CNAME record.
    # https://github.com/paulc/dnslib/blob/master/dnslib/dns.py


class PTR(CNAME):
    """Pointer Record.
    """

    # Functions the same as a CNAME record.
    # https://github.com/paulc/dnslib/blob/master/dnslib/dns.py


class SOA(RecordBase):
    """Start of Authority Record.
    """


class SRV(RecordBase):
    """SRV Record.
    """
