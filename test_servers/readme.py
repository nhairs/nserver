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
