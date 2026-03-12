# Benchmarking NServer

On one host run:
```
uv run nserver --server benchmark/sleepy_server.py:server --host 192.168.20.47 --port 5302 --application threads --workers 12
```

On other host run:
```
nsperf -m tcp -s 192.168.20.47 -p 5302 -d ./dnsperf-queries.txt -T 2 -c 20 -n 1000000 -t 10 -q 200 -l 60
```

## Notes

- It's important to run these on different servers, most DNS benchmarking tools do not deal with TCP on the same host.
