import http.server
import socketserver
import json
import os
import sys

PORT = 8888
# Using python/data/results.json to align with your team's structure
RESULTS_FILE = os.path.join(os.path.dirname(__file__), "data", "results.json")

class StatusHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if not os.path.exists(RESULTS_FILE):
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Error: Results file not found.")
            return

        try:
            with open(RESULTS_FILE, "r") as f:
                data = json.load(f)
            
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            html = "<html><head><title>NetWatch Status</title></head><body>"
            html += "<h1>NetWatch Current Service Status</h1>"
            html += "<table border='1'><tr><th>Hostname</th><th>IP</th><th>Service</th><th>Port</th><th>Status</th></tr>"
            
            for item in data:
                html += f"<tr><td>{item['hostname']}</td><td>{item['ip_address']}</td><td>{item['service']}</td><td>{item['port']}</td><td>{item['state']}</td></tr>"
            
            html += "</table></body></html>"
            self.wfile.write(html.encode("utf-8"))
            print(f"Served status request to {self.client_address[0]}")
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Server Error: {str(e)}".encode("utf-8"))

if __name__ == "__main__":
    try:
        with socketserver.TCPServer(("", PORT), StatusHandler) as httpd:
            print(f"Status server listening on port {PORT}...")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStatus server stopped cleanly.")
        sys.exit(0)
    except OSError as e:
        print(f"Error starting server on port {PORT}: {e}")
        sys.exit(1)
