"""Run the separately deployable Django Workbench."""

from __future__ import annotations

import argparse
import os
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server


class ThreadedWorkbenchServer(ThreadingMixIn, WSGIServer):
    """Small concurrent WSGI server for the single-user loopback Workbench."""

    daemon_threads = True
    allow_reuse_address = True


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Serve the QHPC Django Workbench")
    value.add_argument("--host", default="127.0.0.1")
    value.add_argument("--port", type=int, default=8080)
    value.add_argument("--api-base", default="http://127.0.0.1:8081")
    return value


def main() -> int:
    args = parser().parse_args()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qhpc_workbench.settings")
    os.environ["QHPC_API_BASE"] = args.api_base.rstrip("/")
    os.environ["QHPC_WORKBENCH_HOST"] = args.host

    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.core.wsgi import get_wsgi_application

    application = StaticFilesHandler(get_wsgi_application())
    with make_server(
        args.host,
        args.port,
        application,
        server_class=ThreadedWorkbenchServer,
        handler_class=WSGIRequestHandler,
    ) as server:
        print(f"QHPC Workbench service: http://{args.host}:{args.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
