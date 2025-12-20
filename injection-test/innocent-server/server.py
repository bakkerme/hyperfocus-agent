from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, HTTPServer


MESSAGE = "Thanks for the creds, sucka!\n"


class InnocentBoyHandler(BaseHTTPRequestHandler):
    server_version = "innocent-boy/1.0"

    def do_GET(self) -> None:  # noqa: N802
        self._respond()

    def do_POST(self) -> None:  # noqa: N802
        # Read and ignore any body. We intentionally do nothing with it.
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length > 0:
            _ = self.rfile.read(length)
        self._respond()

    def do_PUT(self) -> None:  # noqa: N802
        self.do_POST()

    def do_PATCH(self) -> None:  # noqa: N802
        self.do_POST()

    def do_DELETE(self) -> None:  # noqa: N802
        self._respond()

    def do_HEAD(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()

    def _respond(self) -> None:
        payload = MESSAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")

    httpd = HTTPServer((host, port), InnocentBoyHandler)
    print(f"innocent-boy listening on http://{host}:{port}/submit")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
