from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, HTTPServer


ROUTE = "/r/nextgengaming"


def _read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


class FakeRedditHandler(BaseHTTPRequestHandler):
    server_version = "fake-reddit/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        # Keep logs readable in docker.
        super().log_message(format, *args)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in (ROUTE, ROUTE + "/"):
            self._serve_etest()
            return

        if self.path in ("/", ""):
            self._text(
                200,
                "text/plain; charset=utf-8",
                "Fake Reddit test server. Try /r/nextgengaming\n",
            )
            return

        self._text(404, "text/plain; charset=utf-8", "Not found\n")

    def do_HEAD(self) -> None:  # noqa: N802
        if self.path in (ROUTE, ROUTE + "/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def _serve_etest(self) -> None:
        html_path = os.path.join(os.path.dirname(__file__), "etest.html")
        try:
            payload = _read_file_bytes(html_path)
        except FileNotFoundError:
            self._text(500, "text/plain; charset=utf-8", "etest.html missing\n")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _text(self, status: int, content_type: str, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")

    httpd = HTTPServer((host, port), FakeRedditHandler)
    print(f"fake-reddit listening on http://{host}:{port}{ROUTE}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
