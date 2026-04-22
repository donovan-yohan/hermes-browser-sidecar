from __future__ import annotations

import argparse
import json

from hermes_browser_sidecar.config import SidecarSettings
from hermes_browser_sidecar.service import SidecarService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hermes-browser-sidecar",
        description="Starter local sidecar service for Hermes browser integrations.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("print-config", help="Print normalized sidecar settings as JSON.")
    subparsers.add_parser("probe", help="Probe the configured upstream Hermes surface.")
    subparsers.add_parser("serve", help="Run the local sidecar scaffold HTTP service.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = SidecarSettings.from_env()
    service = SidecarService(settings)

    if args.command == "print-config":
        print(json.dumps(settings.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "probe":
        print(json.dumps(service.build_health_payload(), indent=2, sort_keys=True))
        return 0

    if args.command == "serve":
        service.serve()
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2

