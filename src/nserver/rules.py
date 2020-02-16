# pylint: disable=too-few-public-methods

### IMPORTS
### ============================================================================
## Standard Library
import re
from typing import Any, Callable, List, Optional, Pattern

## Installed
import tldextract

## Application
from .models import Query

### CLASSES
### ============================================================================
ResponseFunction = Callable[[Query], Any]  # Note: change Any to Union later


class RuleBase:
    """Base class for all Rules to inherit from.
    """

    def get_func(self, query: Query) -> Optional[ResponseFunction]:
        """From the given query return the function to run, if any.

        If no function should be run (i.e. because it does not match the rule),
        then reutrn None.

        This is to allow more efficient methods when determining a match and
        getting the rule function may be expensive (e.g. blueprints).
        """
        raise NotImplementedError()


class RegexRule(RuleBase):
    """Rule that uses the provided regex to attempt to match the query name.
    """

    def __init__(self, regex: Pattern, allowed_qtypes: List, func: ResponseFunction) -> None:
        self.regex = regex
        self.allowed_qtypes = set(allowed_qtypes)
        self.func = func
        return

    def get_func(self, query):
        if query.type not in self.allowed_qtypes:
            return None
        if self.regex.fullmatch(query.name):
            return self.func
        return None


class WildcardStringRule(RuleBase):
    """Rule that allows a more concise way of matching query names.

    Examples:
        _dmarc.{base_domain}
        *._dkim.**
        foo.*.bar.com
    """

    def __init__(self, wildcard_string: str, allowed_qtypes: List, func: ResponseFunction) -> None:
        self.wildcard_string = wildcard_string
        self.allowed_qtypes = allowed_qtypes
        self.func = func
        return

    def get_func(self, query):
        if query.type not in self.allowed_qtypes:
            return None
        regex = self._get_regex(query.name)
        if regex.fullmatch(query.name):
            return self.func
        return None

    def _get_regex(self, query_domain):
        """Given a query domain, produce the regex used for matching.

        A seperate function to make testing easier.
        """
        sub_vars = {}

        domain_parts = tldextract.extract(query_domain)
        if domain_parts.suffix:
            # Public domain
            sub_vars["base_domain"] = domain_parts.registered_domain
        else:
            # Internal / fake domain
            sub_vars["base_domain"] = domain_parts.domain

        regex_parts = []
        for part in self.wildcard_string.format(**sub_vars).split("."):
            if part == "*":
                # Single part match
                regex_parts.append(r"[a-z\-\_]+")
            elif part == "**":
                # Extended part match
                regex_parts.append(r"(?:[a-z\-\_]+\.)+(?:[a-z\-\_]+)")
            else:
                regex_parts.append(re.escape(part))

        regex = re.compile(r"\.".join(regex_parts))
        return regex