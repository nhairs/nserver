# pylint: disable=missing-class-docstring,missing-function-docstring

### IMPORTS
### ============================================================================
## Standard Library
import re

## Installed
import pytest

from nserver.rules import (
    _wildcard_string_regex,
    smart_make_rule,
    StaticRule,
    ZoneRule,
    RegexRule,
    WildcardStringRule,
)
from nserver.models import Query

## Application

### UTILITY
### ============================================================================
# The actual function does not matter..
DUMMY_FUNCTION = lambda x: x  # pylint: disable=unnecessary-lambda-assignment


def run_rule(rule, query, matches):
    result = rule.get_func(query)
    if matches:
        assert result is DUMMY_FUNCTION
    else:
        assert result is None


### TESTS
### ============================================================================
@pytest.mark.parametrize(
    "rule,expected",
    [
        ("*", True),
        ("**", True),
        ("{base_domain}", True),
        ("*.com", True),
        ("**.com", True),
        ("", False),
        ("foo.com", False),
        ("{something}", False),
    ],
)
def test_wildcard_string_regex(rule, expected):
    assert bool(_wildcard_string_regex.search(rule)) is expected


@pytest.mark.parametrize(
    "rule,expected",
    [
        ("", StaticRule),
        ("foo", StaticRule),
        ("example.com", StaticRule),
        ("foo-bar.com", StaticRule),
        ("__dmarc.foo.com", StaticRule),
        ("*.example.com", WildcardStringRule),
        ("**.example.com", WildcardStringRule),
        ("*.mail.{base_domain}", WildcardStringRule),
        ("**.mail.{base_domain}", WildcardStringRule),
        ("{base_domain}", WildcardStringRule),
        ("*.{base_domain}", WildcardStringRule),
        ("*.{base_domain}", WildcardStringRule),
        (re.compile(".*"), RegexRule),
    ],
)
def test_smart_make_rule_class(rule, expected):
    assert isinstance(smart_make_rule(rule, ["A"], func=DUMMY_FUNCTION), expected)


## StaticRule
## -----------------------------------------------------------------------------
class TestStaticRule:
    @pytest.mark.parametrize(
        "qtype,matches",
        [
            ("A", True),
            ("AAAA", True),
            ("TXT", False),
        ],
    )
    def test_qtypes(self, qtype, matches):
        rule = StaticRule("", ["A", "AAAA"], DUMMY_FUNCTION)
        run_rule(rule, Query(qtype, ""), matches)
        return

    @pytest.mark.parametrize("match_string", ("test.com", "TEST.com", "test.COM", "TeSt.CoM"))
    @pytest.mark.parametrize(
        "name,matches",
        [
            ("test.com", True),
            ("TEST.com", True),
            ("test.COM", True),
            ("TEST.COM", True),
            ("TeSt.CoM", True),
            ("", False),
            ("com", False),
            ("foo.test.com", False),
        ],
    )
    def test_case_insensitive(self, match_string, name, matches):
        rule = StaticRule(match_string, ["A"], DUMMY_FUNCTION, False)
        run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("test.com", True),
            ("TEST.com", False),
            ("test.COM", False),
            ("TEST.COM", False),
            ("TeSt.CoM", False),
            ("", False),
            ("com", False),
            ("foo.test.com", False),
        ],
    )
    def test_case_sensitive(self, name, matches):
        rule = StaticRule("test.com", ["A"], DUMMY_FUNCTION, True)
        run_rule(rule, Query("A", name), matches)
        return


## ZoneRule
## -----------------------------------------------------------------------------
class TestZoneRule:
    @pytest.mark.parametrize(
        "qtype,matches",
        [
            ("A", True),
            ("AAAA", True),
            ("TXT", False),
        ],
    )
    def test_qtypes(self, qtype, matches):
        rule = ZoneRule("", ["A", "AAAA"], DUMMY_FUNCTION)
        run_rule(rule, Query(qtype, ""), matches)
        return

    @pytest.mark.parametrize("zone", ("test.com", "TEST.com", "test.COM", "TeSt.CoM"))
    @pytest.mark.parametrize(
        "name,matches",
        [
            ("test.com", True),
            ("TEST.com", True),
            ("test.COM", True),
            ("TEST.COM", True),
            ("TeSt.CoM", True),
            ("foo.TEST.com", True),
            ("BAR.FOO.test.COM", True),
            ("CAR.bar.FOO.TEST.COM", True),
            ("__dmarc.TeSt.CoM", True),
            ("", False),
            ("com", False),
        ],
    )
    def test_case_insensitive(self, zone, name, matches):
        rule = ZoneRule(zone, ["A"], DUMMY_FUNCTION, False)
        run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("test.com", True),
            ("foo.test.com", True),
            ("FOO.test.com", True),
            ("bar.foo.test.com", True),
            ("BAR.foo.test.com", True),
            ("car.bar.foo.test.com", True),
            ("TEST.com", False),
            ("test.COM", False),
            ("TEST.COM", False),
            ("TeSt.CoM", False),
            ("", False),
            ("com", False),
        ],
    )
    def test_case_sensitive(self, name, matches):
        rule = ZoneRule("test.com", ["A"], DUMMY_FUNCTION, True)
        run_rule(rule, Query("A", name), matches)
        return


## RegexRule
## -----------------------------------------------------------------------------
class TestRegexRule:
    @pytest.mark.parametrize(
        "qtype,matches",
        [
            ("A", True),
            ("AAAA", True),
            ("TXT", False),
        ],
    )
    def test_qtypes(self, qtype, matches):
        rule = RegexRule(re.compile(".*"), ["A", "AAAA"], DUMMY_FUNCTION)
        run_rule(rule, Query(qtype, ""), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("cat.test.com", True),
            ("cats.test.com", True),
            ("cat.kitten.test.com", True),
            ("cats.kittens.test.com", True),
            ("cat.com", False),
            ("cat.test.coms", False),
            ("dog.test.com", False),
            ("dog.cat.test.com", False),
        ],
    )
    def test_case_insensitive_same_case(self, name, matches):
        rule = RegexRule(re.compile(r"cat.*\.test\.com"), ["A"], DUMMY_FUNCTION, False)
        run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("Cat.TEST.com", True),
            ("Cats.TEST.com", True),
            ("Cat.kitten.TEST.com", True),
            ("Cats.kittens.TEST.com", True),
        ],
    )
    def test_case_insensitive_query_mixed(self, name, matches):
        rule = RegexRule(re.compile(r"cat.*\.test\.com"), ["A"], DUMMY_FUNCTION, False)
        run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("cat.test.com", True),
            ("cats.test.com", True),
            ("cat.kitten.test.com", True),
            ("cats.kittens.test.com", True),
            ("Cat.TEST.com", True),
            ("Cats.TEST.com", True),
            ("Cat.kitten.TEST.com", True),
            ("Cats.kittens.TEST.com", True),
            ("cat.com", False),
            ("cat.test.coms", False),
            ("dog.test.com", False),
            ("dog.cat.test.com", False),
        ],
    )
    def test_case_insensitive_regex_mixed(self, name, matches):
        rule = RegexRule(re.compile(r"Cat.*\.TEST\.com"), ["A"], DUMMY_FUNCTION, False)
        run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("cat.test.com", False),
            ("cats.test.com", False),
            ("cat.kitten.test.com", False),
            ("cats.kittens.test.com", False),
            ("Cat.TEST.com", True),
            ("Cats.TEST.com", True),
            ("Cat.kitten.TEST.com", True),
            ("Cats.kittens.TEST.com", True),
            ("cat.com", False),
            ("cat.test.coms", False),
            ("dog.test.com", False),
            ("dog.cat.test.com", False),
        ],
    )
    def test_case_sensitive(self, name, matches):
        rule = RegexRule(re.compile(r"Cat.*\.TEST\.com"), ["A"], DUMMY_FUNCTION, True)
        run_rule(rule, Query("A", name), matches)
        return


## WildcardStringRule
## -----------------------------------------------------------------------------
class TestWildcardStringRule:
    @pytest.mark.parametrize(
        "qtype,matches",
        [
            ("A", True),
            ("AAAA", True),
            ("TXT", False),
        ],
    )
    def test_qtypes(self, qtype, matches):
        rule = WildcardStringRule("**", ["A", "AAAA"], DUMMY_FUNCTION)
        run_rule(rule, Query(qtype, "test"), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("cat.test.com", True),
            ("kitten.test.com", True),
            ("test.com", False),
            ("cat.fail.com", False),
            ("cat.test.fail", False),
            ("fail.cat.test.com", False),
        ],
    )
    def test_single_wildcard_expansion(self, name, matches):
        rule = WildcardStringRule("*.test.com", ["A"], DUMMY_FUNCTION, False)
        run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("cat.kitten.test.com", True),
            ("lion.cat.kitten.test.com", True),
            ("test.com", False),
            ("cat.fail.com", False),
            ("cat.test.fail", False),
        ],
    )
    def test_double_wildcard_expansion(self, name, matches):
        rule = WildcardStringRule("**.test.com", ["A"], DUMMY_FUNCTION, False)
        run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("cat.1.dog.1.test.com", True),
            ("cat.1.2.dog.1.test.com", True),
            ("cat.1.2.3.dog.1.test.com", True),
            ("cat.1.dog.test.com", False),
            ("cat.dog.1.test.com", False),
            ("cat.1.2.dog.1.2.test.com", False),
            ("1.cat.3.dog.1.test.com", False),
        ],
    )
    def test_multi_wildcard_expansion(self, name, matches):
        rule = WildcardStringRule("cat.**.dog.*.test.com", ["A"], DUMMY_FUNCTION, False)
        run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("internal", True),
            ("local", True),
            ("asdfasdfasdf", True),
            ("tld.com", True),
            ("psl.com", True),
            ("etld.com.au", True),
            ("psl.au", True),
            ("nope.test.com", False),
            ("nope.foo.com.au", False),
        ],
    )
    def test_base_domain_case_insensitive(self, name, matches):
        rule = WildcardStringRule("{base_domain}", ["A"], DUMMY_FUNCTION, False)
        run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("internal", True),
            ("local", True),
            ("asdfasdfasdf", True),
            ("tld.com", True),
            ("psl.com", True),
            ("etld.com.au", True),
            ("psl.au", True),
            ("nope.test.com", False),
            # Case changes
            ("INTernal", True),
            ("LocaL", True),
            ("TLD.com", True),
            ("tld.COM", True),
            ("ETLD.com.au", True),
            ("etld.COM.au", True),
            ("etld.com.AU", True),
            ("NOPE.test.com", False),
            ("nope.TEST.com", False),
            ("nope.test.COM", False),
        ],
    )
    def test_base_domain_case_sensitive(self, name, matches):
        rule = WildcardStringRule("{base_domain}", ["A"], DUMMY_FUNCTION, True)
        run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            # local domain
            ("cat.1.dog.1.internal", True),
            ("cat.1.2.dog.1.internal", True),
            ("cat.1.2.3.dog.1.internal", True),
            ("cat.1.dog.internal", False),
            ("cat.dog.1.internal", False),
            ("cat.1.2.dog.1.2.internal", False),
            ("1.cat.3.dog.1.internal", False),
            # TLD domain
            ("cat.1.dog.1.tld.com", True),
            ("cat.1.2.dog.1.tld.com", True),
            ("cat.1.2.3.dog.1.tld.com", True),
            ("cat.1.dog.tld.com", False),
            ("cat.dog.1.tld.com", False),
            ("cat.1.2.dog.1.2.tld.com", False),
            ("1.cat.3.dog.1.tld.com", False),
            # effective TLD
            ("cat.1.dog.1.etld.com.au", True),
            ("cat.1.2.dog.1.etld.com.au", True),
            ("cat.1.2.3.dog.1.etld.com.au", True),
            ("cat.1.dog.etld.com.au", False),
            ("cat.dog.1.etld.com.au", False),
            ("cat.1.2.dog.1.2.etld.com.au", False),
            ("1.cat.3.dog.1.etld.com.au", False),
        ],
    )
    def test_base_domain_multi_wildcard_expansion(self, name, matches):
        rule = WildcardStringRule("cat.**.dog.*.{base_domain}", ["A"], DUMMY_FUNCTION, False)
        run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("cat.kitten.test.com", True),
            ("cats.dogs.test.com", False),
            ("cat.com", False),
            ("cat.test.coms", False),
            ("dog.test.com", False),
            ("dog.cat.test.com", False),
        ],
    )
    def test_case_insensitive_same_case(self, name, matches):
        rule = WildcardStringRule("cat.**.test.com", ["A"], DUMMY_FUNCTION, False)
        run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("cat.kitten.test.com", True),
            ("cat.lion.kitten.test.com", True),
            ("cats.dogs.test.com", False),
            ("cat.com", False),
            ("cat.test.com", False),
            ("cat.test.coms", False),
            ("dog.test.com", False),
            ("dog.cat.test.com", False),
            # Case changes
            ("Cat.kitten.TEST.com", True),
            ("Cat.lion.kitten.TEST.com", True),
            ("Cats.dogs.TEST.com", False),
            ("Cat.com", False),
            ("Cat.TEST.com", False),
            ("Cat.TEST.coms", False),
            ("dog.TEST.com", False),
            ("dog.Cat.TEST.com", False),
        ],
    )
    def test_case_insensitive_query_mixed(self, name, matches):
        rule = WildcardStringRule("cat.**.test.com", ["A"], DUMMY_FUNCTION, False)
        run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("cat.kitten.test.com", True),
            ("cat.lion.kitten.test.com", True),
            ("cats.dogs.test.com", False),
            ("cat.com", False),
            ("cat.test.com", False),
            ("cat.test.coms", False),
            ("dog.test.com", False),
            ("dog.cat.test.com", False),
            # Case changes
            ("Cat.kitten.TEST.com", True),
            ("Cat.lion.kitten.TEST.com", True),
            ("Cats.dogs.TEST.com", False),
            ("Cat.com", False),
            ("Cat.TEST.com", False),
            ("Cat.TEST.coms", False),
            ("dog.TEST.com", False),
            ("dog.Cat.TEST.com", False),
        ],
    )
    def test_case_insensitive_expansion_mixed(self, name, matches):
        rule = WildcardStringRule("Cat.**.TEST.com", ["A"], DUMMY_FUNCTION, False)
        run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.parametrize(
        "name,matches",
        [
            ("cat.kitten.test.com", False),
            ("cat.lion.kitten.test.com", False),
            ("cats.dogs.test.com", False),
            ("cat.com", False),
            ("cat.test.com", False),
            ("cat.test.coms", False),
            ("dog.test.com", False),
            ("dog.cat.test.com", False),
            # Case changes
            ("Cat.kitten.TEST.com", True),
            ("Cat.lion.kitten.TEST.com", True),
            ("Cats.dogs.TEST.com", False),
            ("Cat.com", False),
            ("Cat.TEST.com", False),
            ("Cat.TEST.coms", False),
            ("dog.TEST.com", False),
            ("dog.Cat.TEST.com", False),
        ],
    )
    def test_case_sensitive(self, name, matches):
        rule = WildcardStringRule("Cat.**.TEST.com", ["A"], DUMMY_FUNCTION, True)
        run_rule(rule, Query("A", name), matches)
        return
