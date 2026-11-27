"""Rebuild Unholy Index and serve it on the local network (Python 3, no dependencies)."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PORT = 8888

def local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('192.0.2.1', 80))
            return sock.getsockname()[0]
    except OSError:
        return None

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Expose only the generated database, never the rest of the project.
        if urlsplit(path).path == '/generated/entries.json':
            return str(ROOT / 'generated' / 'entries.json')
        return super().translate_path(path)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def list_directory(self, path):
        self.send_error(404)
        return None

if __name__ == '__main__':
    subprocess.run([sys.executable, str(ROOT / 'build.py')], check=True)
    try:
        with ThreadingHTTPServer(('0.0.0.0', PORT), partial(Handler, directory=str(ROOT / 'site'))) as server:
            print(f'Computer: http://localhost:{PORT}', flush=True)
            ip = local_ip()
            if ip:
                print(f'Phone (same Wi-Fi): http://{ip}:{PORT}', flush=True)
            else:
                print(f'Phone: http://<computer-local-IP>:{PORT}', flush=True)
            print('Local network only. Press Ctrl+C to stop.', flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped.')
    except OSError as exc:
        sys.exit(f'Could not start the server on port {PORT}: {exc}')
