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

    Subclasses must set _record_kwargs
    """

    def __init__(self, resource_name: str, ttl: int = None) -> None:
        if self.__class__ is RecordBase:
            raise RuntimeError("Do not instantiate directly - only subclass")

        type_name = self.__class__.__name__
        self._qtype = getattr(dnslib.QTYPE, type_name)
        self._class = getattr(dnslib, type_name)
        self._record_kwargs: Dict[str, Any]
        self.ttl = ttl if ttl is not None else DEFAULT_TTL
        self.resource_name = resource_name
        return

    def to_resource_record(self) -> dnslib.RR:
        """Convert Record to a dnslib Resource Record"""
        resource_record = dnslib.RR(
            rname=self.resource_name,
            rtype=self._qtype,
            rdata=self._class(**self._record_kwargs),
            ttl=self.ttl,
        )
        return resource_record


class A(RecordBase):  # pylint: disable=invalid-name
    """A (IPv4) Record."""

    def __init__(self, name: str, ip: Union[str, IPv4Address], ttl: int = None):
        super().__init__(name, ttl)

        if isinstance(ip, str):
            ip = IPv4Address(ip)

        # Consider support int

        self._record_kwargs = {"data": str(ip)}
        return


class AAAA(RecordBase):
    """AAAA (IPv6) Record."""

    def __init__(self, name: str, ip: Union[str, IPv6Address], ttl: int = None):
        super().__init__(name, ttl)

        if isinstance(ip, str):
            ip = IPv6Address(ip)

        self._record_kwargs = {"data": str(ip)}
        return


class MX(RecordBase):
    """MX Record."""

    def __init__(self, name: str, domain: str, priority: int = 10, ttl: int = None):
        super().__init__(name, ttl)

        self._record_kwargs = {"label": domain, "preference": priority}
        return


class TXT(RecordBase):
    """TXT Record."""

    def __init__(self, name: str, text: str, ttl: int = None):
        super().__init__(name, ttl)

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

        self._record_kwargs = {"data": data}
        return


class CNAME(RecordBase):
    """CNAME Record."""

    # We use regex instead of something like tldextract to allow for internal
    # domains that do not end in a "real" TLD.
    regex = re.compile(r"(?:[a-z0-9\-\_]+\.)+(?:[a-z0-9\-\_]+)\.?")

    def __init__(self, name: str, domain: str, ttl: int = None):
        super().__init__(name, ttl)

        # TODO support converting unicode domains
        if not self.regex.fullmatch(domain):
            raise ValueError(f"{domain!r} is not a valid domain")

        self._record_kwargs = {"label": domain}
        return


class NS(CNAME):
    """Name Server Record."""

    # Functions the same as a CNAME record.
    # https://github.com/paulc/dnslib/blob/master/dnslib/dns.py


class PTR(CNAME):
    """Pointer Record."""

    # Functions the same as a CNAME record.
    # https://github.com/paulc/dnslib/blob/master/dnslib/dns.py


class SOA(RecordBase):
    """Start of Authority Record.

    See also:
        - https://en.wikipedia.org/wiki/SOA_record#Structure
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        name: str,
        primary_name_server: str,
        admin_email: str,
        zone_serial: int,
        refresh_period: int,
        retry_period: int,
        expires: int,
        minimum_ttl: int,
        ttl: int = None,
    ):
        super().__init__(name, ttl)

        self._record_kwargs = {
            "mname": primary_name_server,
            "rname": admin_email,  # TODO: parse this for usability
            "times": (
                zone_serial,
                refresh_period,
                retry_period,
                expires,
                minimum_ttl,
            ),
        }
        return


class SRV(RecordBase):
    """SRV Record."""

    def __init__(  # pylint: disable=too-many-arguments
        self, name: str, priority: int, weight: int, port: int, target: str, ttl: int = None
    ):
        super().__init__(name, ttl)

        self._record_kwargs = {
            "priority": priority,
            "weight": weight,
            "port": port,
            "target": target,
        }
        return


class CAA(RecordBase):
    """Certificate Authority Authorisation Record

    refs:
        - https://tools.ietf.org/html/rfc6844
        - https://support.dnsimple.com/articles/caa-record/
    """

    VALID_TAGS = {"issue", "issuewild", "iodef"}

    def __init__(
        self, name: str, flags: int, tag: str, value: str, ttl: int = None
    ):  # pylint: disable=too-many-arguments
        """Create a new CAA Record

        name: domain name this record applies to
        flags: 8bit numbers for flags
        tag: type of CAA record
        value: value for given tag (see RFC for more info)
        """
        super().__init__(name, ttl)

        if tag not in self.VALID_TAGS:
            raise ValueError(f"invalid tag {tag} must be one of {self.VALID_TAGS}")

        # consider add validation for values

        self._record_kwargs = {
            "flags": flags,
            "tag": tag,
            "value": value,
        }
        return
