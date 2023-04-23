# pylint: disable=missing-class-docstring,missing-function-docstring

### IMPORTS
### ============================================================================
## Standard Library
import re

## Installed
import pytest  # type: ignore # pylint: disable=import-error

## Application
from nserver.rules import RegexRule, WildcardStringRule
from nserver.models import Query

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


## RegexRule
## -----------------------------------------------------------------------------
class TestRegexRule:
    def test_qtypes(self):
        rule = RegexRule(re.compile(".*"), ["A", "AAAA"], DUMMY_FUNCTION)

        cases = (
            ("A", True),
            ("AAAA", True),
            ("TXT", False),
        )

        for qtype, matches in cases:
            run_rule(rule, Query(qtype, ""), matches)
        return

    def test_case_insensitive_same_case(self):
        rule = RegexRule(re.compile(r"cat.*\.test\.com"), ["A"], DUMMY_FUNCTION, False)

        cases = (
            ("cat.test.com", True),
            ("cats.test.com", True),
            ("cat.kitten.test.com", True),
            ("cats.kittens.test.com", True),
            ("cat.com", False),
            ("cat.test.coms", False),
            ("dog.test.com", False),
            ("dog.cat.test.com", False),
        )

        for name, matches in cases:
            run_rule(rule, Query("A", name), matches)
        return

    def test_case_insensitive_query_mixed(self):
        rule = RegexRule(re.compile(r"cat.*\.test\.com"), ["A"], DUMMY_FUNCTION, False)

        cases = (
            ("Cat.TEST.com", True),
            ("Cats.TEST.com", True),
            ("Cat.kitten.TEST.com", True),
            ("Cats.kittens.TEST.com", True),
        )

        for name, matches in cases:
            run_rule(rule, Query("A", name), matches)
        return

    @pytest.mark.skip(reason="Implementation can't lower compiled regex")
    def test_case_insensitive_regex_mixed(self):
        rule = RegexRule(re.compile(r"Cat.*\.TEST\.com"), ["A"], DUMMY_FUNCTION, False)

        cases = (
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
        )

        for name, matches in cases:
            run_rule(rule, Query("A", name), matches)
        return

    def test_case_sensitive(self):
        rule = RegexRule(re.compile(r"Cat.*\.TEST\.com"), ["A"], DUMMY_FUNCTION, True)

        cases = (
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
        )

        for name, matches in cases:
            run_rule(rule, Query("A", name), matches)
        return


## WildcardStringRule
## -----------------------------------------------------------------------------
class TestWildcardStringRule:
    def test_qtypes(self):
        rule = WildcardStringRule("**", ["A", "AAAA"], DUMMY_FUNCTION)

        cases = (
            ("A", True),
            ("AAAA", True),
            ("TXT", False),
        )

        for qtype, matches in cases:
            run_rule(rule, Query(qtype, "test"), matches)
        return

    def test_single_wildcard_expansion(self):
        rule = WildcardStringRule("*.test.com", ["A"], DUMMY_FUNCTION, False)

        cases = (
            ("cat.test.com", True),
            ("kitten.test.com", True),
            ("test.com", False),
            ("cat.fail.com", False),
            ("cat.test.fail", False),
            ("fail.cat.test.com", False),
        )

        for name, matches in cases:
            run_rule(rule, Query("A", name), matches)
        return

    def test_double_wildcard_expansion(self):
        rule = WildcardStringRule("**.test.com", ["A"], DUMMY_FUNCTION, False)

        cases = (
            ("cat.kitten.test.com", True),
            ("lion.cat.kitten.test.com", True),
            ("test.com", False),
            ("cat.fail.com", False),
            ("cat.test.fail", False),
        )

        for name, matches in cases:
            run_rule(rule, Query("A", name), matches)
        return

    def test_multi_wildcard_expansion(self):
        rule = WildcardStringRule("cat.**.dog.*.test.com", ["A"], DUMMY_FUNCTION, False)

        cases = (
            ("cat.1.dog.1.test.com", True),
            ("cat.1.2.dog.1.test.com", True),
            ("cat.1.2.3.dog.1.test.com", True),
            ("cat.1.dog.test.com", False),
            ("cat.dog.1.test.com", False),
            ("cat.1.2.dog.1.2.test.com", False),
            ("1.cat.3.dog.1.test.com", False),
        )

        for name, matches in cases:
            run_rule(rule, Query("A", name), matches)
        return

    def test_base_domain_case_insensitive(self):
        rule = WildcardStringRule("{base_domain}", ["A"], DUMMY_FUNCTION, False)

        cases = (
            ("internal", True),
            ("local", True),
            ("tld.com", True),
            ("etld.com.au", True),
            ("nope.test.com", False),
        )

        for name, matches in cases:
            run_rule(rule, Query("A", name), matches)
        return

    def test_base_domain_case_sensitive(self):
        rule = WildcardStringRule("{base_domain}", ["A"], DUMMY_FUNCTION, True)

        cases = (
            ("internal", True),
            ("local", True),
            ("tld.com", True),
            ("etld.com.au", True),
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
        )

        for name, matches in cases:
            run_rule(rule, Query("A", name), matches)
        return

    def test_base_domain_multi_wildcard_expansion(self):
        rule = WildcardStringRule("cat.**.dog.*.{base_domain}", ["A"], DUMMY_FUNCTION, False)

        cases = (
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
        )

        for name, matches in cases:
            run_rule(rule, Query("A", name), matches)
        return

    def test_case_insensitive_same_case(self):
        rule = WildcardStringRule("cat.**.test.com", ["A"], DUMMY_FUNCTION, False)

        cases = (
            ("cat.kitten.test.com", True),
            ("cats.dogs.test.com", False),
            ("cat.com", False),
            ("cat.test.coms", False),
            ("dog.test.com", False),
            ("dog.cat.test.com", False),
        )

        for name, matches in cases:
            run_rule(rule, Query("A", name), matches)
        return

    def test_case_insensitive_query_mixed(self):
        rule = WildcardStringRule("cat.**.test.com", ["A"], DUMMY_FUNCTION, False)

        cases = (
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
        )

        for name, matches in cases:
            run_rule(rule, Query("A", name), matches)
        return

    def test_case_insensitive_expansion_mixed(self):
        rule = WildcardStringRule("Cat.**.TEST.com", ["A"], DUMMY_FUNCTION, False)

        cases = (
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
        )

        for name, matches in cases:
            run_rule(rule, Query("A", name), matches)
        return

    def test_case_sensitive(self):
        rule = WildcardStringRule("Cat.**.TEST.com", ["A"], DUMMY_FUNCTION, True)

        cases = (
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
        )

        for name, matches in cases:
            run_rule(rule, Query("A", name), matches)
        return
