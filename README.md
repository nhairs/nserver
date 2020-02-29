# NServer: a high-level Python DNS Name Server Framework.

[![PyPi](https://img.shields.io/pypi/v/nserver.svg)](https://pypi.python.org/pypi/nserver/)
[![Python Versions](https://img.shields.io/pypi/pyversions/nserver.svg)](https://github.com/nhairs/nserver)
[![License](https://img.shields.io/github/license/nhairs/nserver.svg)](https://github.com/nhairs/nserver)

NServer is a Python (3.6+) framework for building customised DNS name servers with a focuses on ease of use over completeness. It implements high level APIs for interacting with DNS queries whilst making very few assumptions about how responses are generated.

It is not intended to act like traditional DNS servers such as [BIND](https://www.isc.org/bind/) or [CoreDNS](https://github.com/coredns/coredns) and should not be considered a general DNS resolver.

NServer has been built upon [dnslib](https://github.com/paulc/dnslib) however uses high level abstractions that does not give access to the full DNS specification. If this is your desired behaviour I suggest using dnslib and its [server API](https://github.com/paulc/dnslib/blob/master/dnslib/server.py).

NServer has been inspired by easy to use high level frameworks such as [Flask](https://github.com/pallets/flask) or [Requests](https://github.com/psf/requests).

NServer is currently Alpha software and does not have complete documentation, testing, or implementation of certain features. Specific APIs may change in the future, but NServer uses semantic versioning so you can have more stable interfaces using version specifiers (e.g. `nserver>=0.0.1,<1.0`).

## Installation
### Install via pip
```shell
pip3 install nserver
```

## Quick Start
```python
from nserver import NameServer, Response, A, NS, TXT

ns = NameServer("example")

# Responses can have answers records, additional records and authority records.
@ns.rule("example.com", ["NS"])
def my_name_servers(query):
    response = Response()
    for i in range(4):
        my_ns = "ns{}.example.com".format(i + 1)
        response.answers.append(NS(query.name, my_ns))
        response.additional.append(A(my_ns, "1.1.1.1"))
    return response


# Rules can use wildcards for both single-segment (*) or many-segment (**)
# wildcards will not match mising segments (equivilent to regex `+`)
# You can also construct simple responses by return records directly.


@ns.rule("**.example.com", ["A"])
def wildcard_example(query):
    """All example.com subdomains are at 1.2.3.4."""
    return A(query.name, "1.2.3.4")


# Rules are processed in the order they are registered so if a query matches
# this rule, it will not reach the `australian_catchall` below.
# Wildcards can appear in names, but the above segment limits apply.


@ns.rule("www.*.com.au", ["A"])
def all_australian_www(query):
    return A(query.name, "5.6.7.8")


# Wildcard domains also allow special substitutions.
# base_name will provide the domain less any subdomains.


@ns.rule("hello.{base_domain}", ["TXT"])
def say_hello(query):
    if query.name.endswith(".com.au"):
        return TXT(query.name, "G'day mate")
    return TXT(query.name, "Hello friend")


# Rules can apply to multiple query types.


@ns.rule("**.com.au", ["A", "AAAA", "ANY"])
def australian_catchall(query):
    return Response()  # Empty response, avoids default NXDOMAIN


# Anything that does not match will return NXDOMAIN

if __name__ == "__main__":
    ns.settings.SERVER_PORT = 9001  # It's over 9000!
    ns.run()
```

Once running, interact using `dig`:

```shell
dig -p 9001 @localhost NS example.com

dig -p 9001 @localhost A foo.example.com
dig -p 9001 @localhost A foo.bar.example.com

dig -p 9001 @localhost A www.foo.com.au
dig -p 9001 @localhost A www.bar.com.au

dig -p 9001 @localhost TXT hello.foo.com
dig -p 9001 @localhost TXT hello.foo.com.au

dig -p 9001 @localhost A foo.com.au
dig -p 9001 @localhost AAAA foo.com.au
dig -p 9001 @localhost ANY foo.com.au
```

## Bugs, Feature Requests etc
TLDR: Please [submit an issue on github](https://github.com/nhairs/nserver/issues).

In the case of bug reports, please help me help you by following best practices [1](https://marker.io/blog/write-bug-report/) [2](https://www.chiark.greenend.org.uk/~sgtatham/bugs.html).

In the case of feature requests, please provide background to the problem you are trying to solve so to help find a solution that makes the most sense for the library as well as your usecase. Before making a feature request consider looking at my (roughly written) [design notes](https://github.com/nhairs/nserver/blob/master/DESIGN_NOTES.md).

## Development
The only development dependency is bash and docker. All actions are run within docker for ease of use. See `./dev.sh help` for commands. Typical commands are `format`, `lint`, `test`, `repl`, `build`.

I am still working through open source licencing and contributing, so not taking PRs at this point in time. Instead raise and issue and I'll try get to it as soon a feasible.

## Licence
This project is licenced under the MIT Licence - see [`LICENCE`](https://github.com/nahirs/nserver/blob/master/LICENCE).

This project may include other open source licenced software - see [`NOTICE`](https://github.com/nhairs/nserver/blob/master/NOTICE).

## Authors
A project by Nicholas Hairs - [www.nicholashairs.com](https://www.nicholashairs.com).
