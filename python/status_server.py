import json
import os
import sys
import argparse
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_PORT = 8888
DEFAULT_RESULTS_FILE = os.path.join(BASE_DIR, "data", "results.json")

class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        results_file = self.server.results_file
        if not os.path.exists(results_file):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Results file not found")
            return

        try:
            with open(results_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()

            page = ["<html><head><title>NetWatch Status</title></head><body>",
                    "<h1>NetWatch Current Service Status</h1>",
                    "<table border='1'><tr><th>Hostname</th><th>IP</th><th>Service</th><th>Port</th><th>Status</th></tr>"]
            for item in data:
                page.append("<tr>" + "".join(
                    f"<td>{html.escape(str(item.get(field, '')))}</td>"
                    for field in ("hostname", "ip_address", "service", "port", "state")
                ) + "</tr>")
            page.append("</table></body></html>")
            self.wfile.write("".join(page).encode("utf-8"))
            print(f"Served status request to {self.client_address[0]}", flush=True)
        except (OSError, json.JSONDecodeError, TypeError, KeyError) as error:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Server error: {error}".encode("utf-8"))

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serve NetWatch results")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--results", default=DEFAULT_RESULTS_FILE)
    args = parser.parse_args()
    try:
        with ThreadingHTTPServer((args.host, args.port), StatusHandler) as httpd:
            httpd.results_file = args.results
            print(f"Status server listening on {args.host}:{args.port}...")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStatus server stopped cleanly.")
        sys.exit(0)
    except OSError as error:
        print(f"Error starting server on port {args.port}: {error}", file=sys.stderr)
        sys.exit(1)
