### IMPORTS
### ============================================================================
## Standard Library
import re

## Installed
from nserver import NameServer, Response, A, TXT, CAA

## Application

### MAIN
### ============================================================================
if __name__ == "__main__":
    ns = NameServer("foo")

    @ns.rule("*.nicholashairs.com", ["A"])
    def catchall_a(query):
        return A(query.name, "1.2.3.4")

    @ns.rule(re.compile(r".*\.nicholashairs\.com"), ["TXT"])
    def catchall_txt(query):
        return Response(TXT(query.name, "A" * 255 + "B" * 255 + "C" * 100))

    @ns.rule("*.nicholashairs.com", ["CAA"])
    def catchall_caa(query):
        return Response(CAA(query.name, 0, "issue", "test.com; foo=bar"))

    ns.run()
