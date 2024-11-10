### IMPORTS
### ============================================================================
## Future
from __future__ import annotations

## Standard Library
import argparse
import importlib

## Installed
import pillar.application

## Application
from . import transport
from . import _version

from .application import BaseApplication, DirectApplication
from .server import NameServer, RawNameServer


### CLASSES
### ============================================================================
class CliApplication(pillar.application.Application):
    """NServer CLI tool for running servers"""

    application_name = "nserver"
    name = "nserver"
    version = _version.VERSION_INFO_FULL
    epilog = "For full information including licence see https://github.com/nhairs/nserver"

    config_args_enabled = False

    def get_argument_parser(self) -> argparse.ArgumentParser:
        parser = super().get_argument_parser()

        ## Server
        ## ---------------------------------------------------------------------
        parser.add_argument(
            "--server",
            action="store",
            help=(
                "Import path of server / factory to run in the form of "
                "package.module.path:attribute"
            ),
        )

        ## Transport
        ## ---------------------------------------------------------------------
        parser.add_argument(
            "--host",
            action="store",
            default="localhost",
            help="Host (IP) to bind to. Defaults to localhost.",
        )

        parser.add_argument(
            "--port",
            action="store",
            default=5300,
            type=int,
            help="Port to bind to. Defaults to 5300.",
        )

        transport_group = parser.add_mutually_exclusive_group()
        transport_group.add_argument(
            "--udp",
            action="store_const",
            const=transport.UDPv4Transport,
            dest="transport",
            help="Use UDPv4 socket for transport. (default)",
        )
        transport_group.add_argument(
            "--udp6",
            action="store_const",
            const=transport.UDPv6Transport,
            dest="transport",
            help="Use UDPv6 socket for transport.",
        )
        transport_group.add_argument(
            "--tcp",
            action="store_const",
            const=transport.TCPv4Transport,
            dest="transport",
            help="Use TCPv4 socket for transport.",
        )

        parser.set_defaults(transport=transport.UDPv4Transport)
        return parser

    def setup(self, *args, **kwargs) -> None:
        super().setup(*args, **kwargs)

        self.server = self.get_server()
        self.application = self.get_application()
        return

    def main(self) -> int | None:
        return self.application.run()

    def get_server(self) -> NameServer | RawNameServer:
        """Factory for getting the server to run based on current settings"""
        module_path, attribute_path = self.args.server.split(":")
        obj: object = importlib.import_module(module_path)

        for attribute_name in attribute_path.split("."):
            obj = getattr(obj, attribute_name)

        if isinstance(obj, (NameServer, RawNameServer)):
            return obj

        # Assume callable (will throw error if not)
        server = obj()  # type: ignore[operator]

        if isinstance(server, (NameServer, RawNameServer)):
            return server

        raise TypeError(f"Imported factory ({obj}) did not return a server ({server})")

    def get_application(self) -> BaseApplication:
        """Factory for getting the application based on current settings"""
        application = DirectApplication(
            self.server,
            self.args.transport(self.args.host, self.args.port),
        )
        return application


### MAIN
### ============================================================================
if __name__ == "__main__":
    app = CliApplication()
    app.run()
