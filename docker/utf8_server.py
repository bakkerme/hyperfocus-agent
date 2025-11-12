#!/usr/bin/env python3
"""
UTF-8 HTTP server for serving test assets with proper encoding headers.

The default Python http.server module doesn't send charset in Content-Type headers,
causing requests library to default to ISO-8859-1, which breaks UTF-8 content.

This server explicitly sets charset=utf-8 for text files.
"""
import http.server
import socketserver
from pathlib import Path


class UTF8HTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler that sets proper UTF-8 charset for text files."""
    
    # Override extensions_map to include charset for text files
    extensions_map = {
        '.html': 'text/html; charset=utf-8',
        '.htm': 'text/html; charset=utf-8',
        '.txt': 'text/plain; charset=utf-8',
        '.css': 'text/css; charset=utf-8',
        '.js': 'application/javascript; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
        '.xml': 'application/xml; charset=utf-8',
        '.csv': 'text/csv; charset=utf-8',
        '.md': 'text/markdown; charset=utf-8',
        # Binary files (no charset)
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
        '.pdf': 'application/pdf',
        '.zip': 'application/zip',
    }
    
    def end_headers(self):
        """Add CORS headers to allow cross-origin requests."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()
    
    def log_message(self, format, *args):
        """Override to add more informative logging."""
        print(f"[{self.log_date_time_string()}] {self.address_string()} - {format % args}")


def run_server(port=8080, directory="."):
    """Run the UTF-8 HTTP server."""
    import os
    os.chdir(directory)
    
    with socketserver.TCPServer(("", port), UTF8HTTPRequestHandler) as httpd:
        print(f"UTF-8 HTTP Server running on port {port}")
        print(f"Serving files from: {Path(directory).absolute()}")
        print(f"All text files will be served with charset=utf-8")
        print(f"\nPress Ctrl+C to stop the server\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
