# Production Deployment

Although NServer applications can be exposed directly, for production deployments it's recommended that you run your NServer application behind a reverse proxy (similar to how you would run HTTP application with uWSGI or NGINX).

There are a few reasons for this:

- NServer is currently beta software. Although care has been taken when writing the server, it has not been thoroughly tested for bugs, nor has it had a security assessment done.
- The server is single threaded and queries will be handled one at a time.
- The server currently only provides UDP and TCP queries - it does not support DNS-over-HTTPS nor are there plans to do so.
- Public DNS resolvers and name servers are regularly targetted for all kinds of attacks. Rather than re-implementing defences such as rate-limiting we can re-use existing mechanisms.
- NServer does not currently include response caching.

## Deployment using CoreDNS

[CoreDNS](https://coredns.io/) is a extendable DNS server written in Go. It has many plugins available which we can use to quickly configure our public facing servers allowing us to keep our NServer application private.

In order to get the most performance out of our NServer instance we should operate it using the `TCPv4` transport as this will allow CoreDNS to reuse the connection for many queries whilst ensuring that even under high load queries are not lost.

!!! note
    The following Corefile uses [external plugins](https://coredns.io/explugins/) which will require you to [build CoreDNS with the external plugins](https://coredns.io/2017/07/25/compile-time-enabling-or-disabling-plugins/#build-with-compile-time-configuration-file).

```title="sample.corefile"
# send all requests to this block (.) and use standard DNS port (53).
.:53 {
    # bind server to your public IP address
    # note: you likely do NOT want to bind to 0.0.0.0 as this may overwrite
    # your system's DNS resolver crippling it.
    bind <your-public-ip>

    # timeout if we take longer than 5001ms to respond
    cancel

    # request rate-limting
    # plugin.cfg: ratelimit:github.com/milgradesec/ratelimit
    ratelimit 20

    # response rate-limiting
    # (mitigate amplification attacks with response rate limiting)
    # plugin.cfg: rrl:github.com/coredns/rrl/plugins/rrl
    rrl . {
        responses-per-second 10
        requests-per-second  10
    }

    # response cache
    cache 3600 . {
        success 10000 3600 300
        denial   5000 3600 300
    }

    # forward all requests (that miss the cache) to our NServer application
    # running on the default port.
    forward . 127.0.0.1:9953 {
        force_tcp
    }

    # enable error logging
    errors
}
```
