#!/usr/bin/env python3
"""Simple SPA server for the FireAI frontend dist.
Serves index.html for all non-asset routes (SPA fallback).
Also proxies /api/* to the backend on port 8000.
"""
import http.server
import socketserver
import os
import urllib.request
import urllib.error

DIST_DIR = "/home/z/my-project/frontend/dist"
BACKEND_URL = "http://127.0.0.1:8000"
PORT = 5330


class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/") or self.path.startswith("/health") or self.path.startswith("/openapi"):
            return self._proxy_to_backend()
        if "." not in os.path.basename(self.path.split("?")[0]):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        return self._proxy_to_backend()

    def do_PUT(self):
        return self._proxy_to_backend()

    def do_DELETE(self):
        return self._proxy_to_backend()

    def do_PATCH(self):
        return self._proxy_to_backend()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key, Authorization")
        self.end_headers()

    def _proxy_to_backend(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else None
            url = f"{BACKEND_URL}{self.path}"
            headers = {k: v for k, v in self.headers.items() if k.lower() != "host"}
            req = urllib.request.Request(url, data=body, method=self.command, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                response_body = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(response_body)
        except urllib.error.HTTPError as e:
            response_body = e.read()
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(response_body)
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(f'{{"error":"proxy failed: {str(e)}"}}'.encode())

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), SPAHandler) as httpd:
        print(f"SPA server on http://0.0.0.0:{PORT}")
        httpd.serve_forever()
