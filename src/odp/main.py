"""CLI entrypoint: `odp serve` starts the app and opens a browser tab."""

from __future__ import annotations

import argparse
import webbrowser

import uvicorn

from odp.config import get_settings


def cli() -> None:
    parser = argparse.ArgumentParser(prog="odp", description="Open-Dev-Plan")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Start the local server")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--no-browser", action="store_true")

    args = parser.parse_args()

    if args.command == "serve":
        _serve(host=args.host, port=args.port, open_browser=not args.no_browser)


def _serve(host: str | None, port: int | None, open_browser: bool) -> None:
    settings = get_settings()
    host = host or settings.host
    port = port or settings.port

    if open_browser:
        webbrowser.open(f"http://{host}:{port}")

    uvicorn.run("odp.api.app:create_app", factory=True, host=host, port=port)


if __name__ == "__main__":
    cli()
