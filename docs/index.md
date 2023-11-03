# NServer: a high-level Python DNS Name Server Framework.

[![PyPi](https://img.shields.io/pypi/v/nserver.svg)](https://pypi.python.org/pypi/nserver/)
[![PyPI - Status](https://img.shields.io/pypi/status/nserver)](https://pypi.python.org/pypi/nserver/)
[![Python Versions](https://img.shields.io/pypi/pyversions/nserver.svg)](https://github.com/nhairs/nserver)
[![License](https://img.shields.io/github/license/nhairs/nserver.svg)](https://github.com/nhairs/nserver)

## Introduction
NServer is a Python framework for building customised DNS name servers with a focuses on ease of use over completeness. It implements high level APIs for interacting with DNS queries whilst making very few assumptions about how responses are generated.

It is not intended to act like traditional DNS servers such as [BIND](https://www.isc.org/bind/) or [CoreDNS](https://github.com/coredns/coredns) and should not be considered a general DNS resolver.

NServer has been built upon [dnslib](https://github.com/paulc/dnslib) however uses high level abstractions that does not give access to the full DNS specification. If this is your desired behaviour I suggest using dnslib and its [server API](https://github.com/paulc/dnslib/blob/master/dnslib/server.py).

NServer has been inspired by easy to use high level frameworks such as [Flask](https://github.com/pallets/flask) or [Requests](https://github.com/psf/requests).

!!! warning
    NServer is currently Beta software and does not have complete documentation, testing, or implementation of certain features.


## Features

- **Flexibility:** Receive and respond to DNS queries using python functions
- **Speed:** comfortably handle 1000 queries per second on a single thread
- **Protocols:** supports UDP, TCP DNS queries
  - TCP server support request pipelining and connection multiplexing
- **Development:** fully typed for your static analysis / linting needs

## Quick Start

Follow our [Quickstart Guide](quickstart.md).

```python title="TLDR"
from nserver import NameServer, Query, A

server = NameServer("example")

@server.rule("example.com", ["A"])
def example_a_records(query: Query):
    return A(query.name, "1.2.3.4")

if __name__ == "__main__":
    server.run()
```


## Bugs, Feature Requests etc
Please [submit an issue on github](https://github.com/nhairs/nserver/issues).

In the case of bug reports, please help us help you by following best practices [^1^](https://marker.io/blog/write-bug-report/) [^2^](https://www.chiark.greenend.org.uk/~sgtatham/bugs.html).

In the case of feature requests, please provide background to the problem you are trying to solve so to help find a solution that makes the most sense for the library as well as your usecase. Before making a feature request consider looking at my (roughly written) [design notes](https://github.com/nhairs/nserver/blob/master/DESIGN_NOTES.md).

## Contributing
I am still working through open source licencing and contributing, so not taking PRs at this point in time. Instead raise and issue and I'll try get to it as soon a feasible.

## Licence
This project is licenced under the MIT Licence - see [`LICENCE`](https://github.com/nhairs/nserver/blob/master/LICENCE).

This project includes other open source licenced software - see [`NOTICE`](https://github.com/nhairs/nserver/blob/master/NOTICE).

## Authors
A project by Nicholas Hairs - [www.nicholashairs.com](https://www.nicholashairs.com).
