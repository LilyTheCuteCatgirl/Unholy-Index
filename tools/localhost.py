"""Build and serve Unholy Index on the local network, on port 8888."""

import socket
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from build import build

ROOT = Path(__file__).resolve().parents[1]
PORT = 8888


def local_ip():
    """Determine the local address used by the default IPv4 route."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


class Handler(SimpleHTTPRequestHandler):
    """Serve only site assets and the generated entry database."""

    def translate_path(self, path):
        requested = urlsplit(path).path
        if requested in ("/generated/entries.json", "/generated/texts.json"):
            return str(ROOT / "generated" / requested.rsplit("/", 1)[-1])
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def list_directory(self, path):
        self.send_error(404)
        return None


def main():
    """Rebuild the database and run the development server."""
    build()
    if not (ROOT / "generated" / "texts.json").exists():
        print("Optional local texts: run python tools/texts.py once.", flush=True)
    handler = partial(Handler, directory=str(ROOT / "site"))
    try:
        with ThreadingHTTPServer(("0.0.0.0", PORT), handler) as server:
            print(f"Computer: http://localhost:{PORT}", flush=True)
            ip = local_ip() or "<computer-local-IP>"
            print(f"Phone (same Wi-Fi): http://{ip}:{PORT}", flush=True)
            print("Local network only. Press Ctrl+C to stop.", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except OSError as exc:
        sys.exit(f"Could not start the server on port {PORT}: {exc}")


if __name__ == "__main__":
    main()
