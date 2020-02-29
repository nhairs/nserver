# Design Notes

### Why only OPCODE == QUERY?
This is what most people do and to avoid a large scope.

### Why Domains Only?
This is designed to be a nameserver as in for domains. This narrow focus allows this library to be much more friendly when handling domains which is the expected use case.

In theory this should support public (e.g. google.com) or private (e.g. acme.corp.internal) domains.

### Why pass query to view function?
Ease of implementation. Whilst I want to do something like Flask.request in the future, this is not in scope for MVP.


## TODO
- Unicode support
- blueprints
