# Quickstart

## Installation

### Install via pip
```bash
pip3 install nserver
```

## Minimal Server

### Preparing our server

```python title="minimal_server.py"
from nserver import NameServer, Query, A

server = NameServer("example")

@server.rule("example.com", ["A"])
def example_a_records(query: Query):
    return A(query.name, "1.2.3.4")

if __name__ == "__main__":
    server.run()
```

Here's what this code does:

1. To start we import:
  - [`NameServer`][nserver.server.NameServer] - an instance of this class will contain our application
  - [`Query`][nserver.models.Query] - instances of this class will be passed to our rule functions so that we can inspect the incoming DNS query
  - [`A`][nserver.records.A] - the class used to create DNS `A` records

2. Next we create a `NameServer` instance for our application to use. The name we give the server will be used to help distinguish it from others that are also running.

3. We then use the [`rule`][nserver.server.NameServer.rule] decorator to tell our server when to trigger our function. In this case we will trigger for `A` queries that exactly match the name `example.com`.

4. When triggered our function will then return a single `A` record as a response.

5. Finally we add code so that we can run our server.

### Running our server

With our server written we can now run it:

```shell
python3 example_server.py
```

```{.none .no-copy}
[INFO] Starting UDPv4Transport(address='localhost', port=9953)
```

We can access it using `dig`.

```shell
dig -p 9953 @localhost A example.com
```

```{.none .no-copy}
; <<>> DiG 9.18.12-0ubuntu0.22.04.3-Ubuntu <<>> -p 9953 @localhost A example.com
; (1 server found)
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 20379
;; flags: qr aa rd ra ad; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

;; QUESTION SECTION:
;example.com.			IN	A

;; ANSWER SECTION:
example.com.		300	IN	A	1.2.3.4

;; Query time: 324 msec
;; SERVER: 127.0.0.1#9953(localhost) (UDP)
;; WHEN: Thu Nov 02 21:27:12 AEDT 2023
;; MSG SIZE  rcvd: 45
```

## Rules

[Rules][nserver.rules] tell our server which queries to send to which functions. NServer ships with a number of rule types.

- [`StaticRule`][nserver.rules.StaticRule] matches on an exact string.
- [`ZoneRule`][nserver.rules.ZoneRule] matches the given domain and all subdomains.
- [`WildcardStringRule`][nserver.rules.WildcardStringRule] which allows writing rules using a shorthand syntax.
- [`RegexRule`][nserver.rules.RegexRule] which uses regular expressions for matching.

The [`NameServer.rule`][nserver.server.NameServer.rule] decorator uses [`smart_make_rule`][nserver.rules.smart_make_rule] to automatically select the "best" matching rule type based on the input. This will result in string (`str`) rules will be used to create either a `WildcardStringRule` or a `StaticRule`, whilst regular expression (`typing.Pattern`) rules will create a `RegexRule`. This decorator also return the original function unchanged meaning it is possible to decorate the same function with multiple rules.

```python
@saerver.rule("google-dns", ["A"])
def this_will_be_a_static_rule(query):
    return A(query.name, "8.8.8.8")

@server.rule("{base_name}", ["A"])
@server.rule("www.{base_name}", ["A"])
@server.rule("mail.{base_name}", ["A"])
def we_only_have_three_servers_for_everything(query):
    return list(A(query.name, f"1.1.1.{i+1}") for i in range(3))
```

Rules can also be added to a server by calling the [`register_rule`][nserver.server.NameServer.register_rule] method with an exiting rule.

```python
from nserver import RegexRule

server.register_rule(
    RegexRule(
        re.compile(r"[0-9a-f]{1-4}\.com"),
        ["A"],
        lambda q: return A(q.name, "1.2.3.4"),
    )
)
```

By default all rules match in a case-insensitive manner. This is the expected behaviour for name servers operating on the internet. You can override this by setting `case_sensitive=True` in the constructors or `rule` decorator.

### The `WildcardStringRule`

The `WildcardStringRule` allows using a shorthand notation for matching DNS names.

- `*` will match a single label in the query domain
- `**` will match one or more labels in the query domain (in a greedy manner)
- `{base_name}` will match the "base" of the query name using the [Public Suffix List](https://publicsuffix.org/). In general this means the "registered" domain for public TLDs or the last label for non-TLDs (e.g. `.local`, `.internal`).

For example:

- `*.example.com.au` will match all first level subdomains of `example.com.au`, but will **not** match `example.com.au` or `foo.bar.example.com.au`.
- `**.example.com.au` will match all subdomains of `example.com.au` but will **not** match `example.com.au`.
- `www.{base_name}` will match `www` on all registered and internal domains (`www.example.com.au`, `www.au`) but will **not** match on other subdomains, or as a registered name (`www.com.au`, `www.foo.au`)

## Responses

Rule functions are expected to return only the following types:

- `None`
- A single record instance (of any type)
- A list of record instances (of any record type, including mixed)
- A [`Response`][nserver.models.Response] instance

When records are returned, these will automatically be added to a `Response` instance as answer records. For simple responses this is usually enough. When `None` is returned it will be converted to an empty response.

However if you wish to return Additional or Authority Records, or change the Error Code you will need to return a `Response` instance.

For example a typical `NS` lookup when our application is the authoritive server for the domain may look like this:

```python
# ... server setup exlcuded

from nserver import Response, NS, A, SOA

MY_SERVERS = {
    "ns1.example.com": "1.2.3.4",
    "ns2.example.com": "1.2.3.5",
    "ns-backup.example.com": "9.8.7.6",
}

@server.rule("example.com", ["NS"])
def name_servers(query: Query) -> Response:
    response = Response()
    for ns, ip in MY_SERVERS.items():
        response.answers.append(NS(query.name, ns))
        response.additional.append(A(ns, ip))
    response.authority.append(SOA(
        "example.com",
        list(MY_SERVERS.keys())[0],
        "admin.example.com",
        1,
    ))
    return response
```
