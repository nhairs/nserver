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
from .util import is_unsigned_int_size


### CLASSES
### ============================================================================
class RecordBase:
    """Base class for all DNS records.

    Note: MUST NOT be used directly

    Subclasses must set `_record_kwargs`
    """

    def __init__(self, resource_name: str, ttl: int) -> None:
        """
        Args:
            resource_name: DNS resource name
            ttl: record time-to-live in seconds
        """
        if self.__class__ is RecordBase:
            raise RuntimeError("Do not instantiate directly - only subclass")

        type_name = self.__class__.__name__
        self._qtype = getattr(dnslib.QTYPE, type_name)
        self._class = getattr(dnslib, type_name)  # class means python class not RR CLASS
        self._record_kwargs: Dict[str, Any]
        is_unsigned_int_size(ttl, 32, throw_error=True, value_name="ttl")
        self.ttl = ttl
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
    """Ipv4 Address (`A`) Record."""

    def __init__(self, resource_name: str, ip: Union[str, IPv4Address], ttl: int = 300) -> None:
        """
        Args:
            resource_name: DNS resource name
            ip: IPv4 address of the resource
            ttl: record time-to-live in seconds
        """
        super().__init__(resource_name, ttl)

        if isinstance(ip, str):
            ip = IPv4Address(ip)

        # TODO: Consider supporting addresses in `int` form.

        self._record_kwargs = {"data": str(ip)}
        return


class AAAA(RecordBase):
    """Ipv6 Address (`AAAA`) Record."""

    def __init__(self, resource_name: str, ip: Union[str, IPv6Address], ttl: int = 300) -> None:
        """
        Args:
            resource_name: DNS resource name
            ip: IPv6 address of the resource
            ttl: record time-to-live in seconds
        """
        super().__init__(resource_name, ttl)

        if isinstance(ip, str):
            ip = IPv6Address(ip)

        # TODO: Consider supporting addresses in `int` form.

        self._record_kwargs = {"data": str(ip)}
        return


class MX(RecordBase):
    """Mail Exchange (`MX`) Record

    See also:
        - https://datatracker.ietf.org/doc/html/rfc1035#section-3.3.9
        - https://en.wikipedia.org/wiki/MX_record
    """

    def __init__(self, resource_name: str, domain: str, priority: int = 10, ttl: int = 300) -> None:
        """
        Args:
            resource_name: DNS resource name
            domain: DNS name of mail exchange. Note: `domain` must not point to a `CNAME` record.
            priority: mail exchange priority (`0` is highest priority)
            ttl: record time-to-live in seconds
        """
        super().__init__(resource_name, ttl)

        is_unsigned_int_size(priority, 16, throw_error=True, value_name="priority")

        self._record_kwargs = {"label": domain, "preference": priority}
        return


class TXT(RecordBase):
    """Text (`TXT`) Record"""

    def __init__(self, resource_name: str, text: str, ttl: int = 300) -> None:
        """
        Args:
            resource_name: DNS resource name
            text: value of the record
            ttl: record time-to-live in seconds
        """
        super().__init__(resource_name, ttl)

        # TODO: consider converting to bytes to allow for unicode or other.
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
    """Canonical Name (`CNAME`) Record."""

    # We use regex instead of something like tldextract to allow for internal
    # domains that do not end in a "real" TLD.
    _domain_regex = re.compile(r"(?:[a-z0-9\-\_]+\.)+(?:[a-z0-9\-\_]+)\.?")

    def __init__(self, resource_name: str, domain: str, ttl: int = 300) -> None:
        """
        Args:
            resource_name: DNS resource name
            domain: canonical domain for this `name`
            ttl: record time-to-live in seconds
        """
        super().__init__(resource_name, ttl)

        # TODO support converting unicode domains
        if not self._domain_regex.fullmatch(domain):
            raise ValueError(f"{domain!r} is not a valid domain")

        self._record_kwargs = {"label": domain}
        return


class NS(CNAME):
    """Name Server (`NS`) Record.

    See also:
        - https://datatracker.ietf.org/doc/html/rfc1035#section-3.3.11
    """

    def __init__(self, resource_name: str, domain: str, ttl: int = 3600) -> None:
        """
        Args:
            resource_name: DNS resource name
            domain: domain name of the Name Server
            ttl: record time-to-live in seconds
        """
        # Functions the same as a CNAME record.
        # https://github.com/paulc/dnslib/blob/master/dnslib/dns.py
        super().__init__(resource_name, domain, ttl)
        return


class PTR(CNAME):
    """Pointer (`PTR`) Record.

    See also:
        - https://datatracker.ietf.org/doc/html/rfc1035#section-3.3.12
    """

    def __init__(self, resource_name: str, domain: str, ttl: int = 300) -> None:
        """
        Args:
            resource_name: DNS resource name
            domain: domain to point to
            ttl: record time-to-live in seconds
        """
        # Functions the same as a CNAME record.
        # https://github.com/paulc/dnslib/blob/master/dnslib/dns.py
        super().__init__(resource_name, domain, ttl)
        return


class SOA(RecordBase):
    """Start of Authority (`SOA``) Record

    See also:
        - https://datatracker.ietf.org/doc/html/rfc1035#section-3.3.13
        - https://en.wikipedia.org/wiki/SOA_record
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        zone_name: str,
        primary_name_server: str,
        admin_email: str,
        zone_serial: int,
        refresh_period: int = 86400,
        retry_period: int = 7200,
        expires: int = 3600000,
        minimum_ttl: int = 172800,
        ttl: int = 3600,
    ):
        """
        Args:
            zone_name: name of the DNS zone
            primary_name_server: domain name of primary name server for this domain
            admin_email: Domain encoded email address of the administrator responsible for this zone. The part of the email address before the @ becomes the first label of the name; the domain name after the @ becomes the rest of the name. In zone-file format, dots in labels are escaped with backslashes; thus the email address john.doe@example.com would be represented in a zone file as john\\.doe.example.com.)
            zone_serial: Serial number for this zone. If a secondary name server following this one observes an increase in this number, the follower will assume that the zone has been updated and initiate a zone transfer.
            refresh_period: Number of seconds after which secondary name servers should query the master for the SOA record, to detect zone changes. Recommendation for small and stable zones: 86400 seconds (24 hours).
            retry_period: Number of seconds after which secondary name servers should retry to request the serial number from the master if the master does not respond. It must be less than Refresh. Recommendation for small and stable zones: 7200 seconds (2 hours).
            expires: Number of seconds after which secondary name servers should stop answering request for this zone if the master does not respond. This value must be bigger than the sum of Refresh and Retry. Recommendation for small and stable zones: 3600000 seconds (1000 hours).
            minimum_ttl: Used in calculating the time to live for purposes of negative caching. Authoritative name servers take the smaller of the SOA TTL and the SOA MINIMUM to send as the SOA TTL in negative responses. Resolvers use the resulting SOA TTL to understand for how long they are allowed to cache a negative response. Recommendation for small and stable zones: 172800 seconds (2 days)
            ttl: record time-to-live in seconds
        """
        super().__init__(zone_name, ttl)

        is_unsigned_int_size(zone_serial, 32, throw_error=True, value_name="zone_serial")
        is_unsigned_int_size(refresh_period, 32, throw_error=True, value_name="refresh_period")
        is_unsigned_int_size(retry_period, 32, throw_error=True, value_name="retry_period")
        is_unsigned_int_size(expires, 32, throw_error=True, value_name="expires")
        is_unsigned_int_size(minimum_ttl, 32, throw_error=True, value_name="minimum_ttl")

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
    """Service (`SRV`) Record

    See also:
        - https://datatracker.ietf.org/doc/html/rfc2782
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        resource_name: str,
        target: str,
        port: int,
        priority: int,
        weight: int,
        ttl: int = 300,
    ):
        """
        Args:
            resource_name: Full name of service in `_Service._Proto.Name` format.
            target: domain name of target host
            port: port on target host
            priority: priority of target host. `0` is highest.
            weight: relative weight of this `target` for targets with same `priority`. `0` is lowest.
            ttl: record time-to-live in seconds
        """
        super().__init__(resource_name, ttl)

        is_unsigned_int_size(priority, 16, throw_error=True, value_name="priority")
        is_unsigned_int_size(weight, 16, throw_error=True, value_name="weight")
        is_unsigned_int_size(port, 16, throw_error=True, value_name="port")

        self._record_kwargs = {
            "priority": priority,
            "weight": weight,
            "port": port,
            "target": target,
        }
        return


class CAA(RecordBase):
    """Certificate Authority Authorisation (`CAA`) Record

    See also:
        - https://datatracker.ietf.org/doc/html/rfc6844
        - https://support.dnsimple.com/articles/caa-record/
    """

    _VALID_TAGS = {"issue", "issuewild", "iodef"}

    def __init__(
        self, resource_name: str, flags: int, tag: str, value: str, ttl: int = 3600
    ):  # pylint: disable=too-many-arguments
        """
        Args:
            resource_name: domain name this record applies to
            flags: 8bit numbers for flags
            tag: type of CAA record
            value: value for given tag (see RFC for more info)
            ttl: record time-to-live in seconds
        """
        super().__init__(resource_name, ttl)

        is_unsigned_int_size(flags, 8, throw_error=True, value_name="flags")

        if tag not in self._VALID_TAGS:
            raise ValueError(f"invalid tag {tag} must be one of {self._VALID_TAGS}")

        # consider add validation for values

        self._record_kwargs = {
            "flags": flags,
            "tag": tag,
            "value": value,
        }
        return
