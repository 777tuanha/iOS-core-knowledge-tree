"""
serve.py — local HTTP server for iOS Core Knowledge Tree.

Serves site/ as static files and proxies POST /api/notion-sync to notion_sync.py.
Reads NOTION_TOKEN and NOTION_PARENT_PAGE_ID from .env at project root.

Usage:
    python3 scripts/serve.py
Then open http://localhost:8080
"""

import json
import mimetypes
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, TCPServer
from pathlib import Path

# Project root is one level up from scripts/
ROOT = Path(__file__).parent.parent
SITE_DIR = ROOT / "site"
MAP_FILE = ROOT / ".notion-map.json"

# Add scripts/ to path so we can import notion_sync
sys.path.insert(0, str(ROOT / "scripts"))
import notion_sync


# ---------------------------------------------------------------------------
# Minimal .env loader
# ---------------------------------------------------------------------------

def load_dotenv(path: Path):
    if not path.exists():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Suppress default access log; print our own
        print(f"  {self.address_string()} {fmt % args}")

    def do_GET(self):
        # Strip query string
        raw_path = self.path.split("?")[0]

        # Default to index.html
        if raw_path == "/" or raw_path == "":
            raw_path = "/index.html"

        # Path traversal guard
        try:
            file_path = (SITE_DIR / raw_path.lstrip("/")).resolve()
            file_path.relative_to(SITE_DIR.resolve())
        except (ValueError, Exception):
            self._send_error(403, "Forbidden")
            return

        if not file_path.exists():
            self._send_error(404, "Not Found")
            return

        if file_path.is_dir():
            file_path = file_path / "index.html"
            if not file_path.exists():
                self._send_error(404, "Not Found")
                return

        mime, _ = mimetypes.guess_type(str(file_path))
        mime = mime or "application/octet-stream"

        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/api/notion-sync":
            self._send_error(404, "Not Found")
            return

        token = os.environ.get("NOTION_TOKEN", "")
        parent_page_id = os.environ.get("NOTION_PARENT_PAGE_ID", "")

        if not token or not parent_page_id:
            self.send_response(400)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            self._emit({"type": "error", "message": (
                "Missing NOTION_TOKEN or NOTION_PARENT_PAGE_ID. "
                "Copy .env.example to .env and fill in your credentials."
            )})
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        content_dir = ROOT / "content"

        try:
            notion_sync.sync_all(
                token=token,
                parent_page_id=parent_page_id,
                content_dir=content_dir,
                map_file=MAP_FILE,
                progress_callback=self._emit,
            )
        except Exception as exc:
            self._emit({"type": "error", "message": str(exc)})

    def _emit(self, event: dict):
        try:
            line = json.dumps(event) + "\n"
            self.wfile.write(line.encode())
            self.wfile.flush()
        except Exception:
            pass  # client disconnected

    def _send_error(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(message.encode())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    load_dotenv(ROOT / ".env")

    port = 8080
    with TCPServer(("", port), Handler) as server:
        server.allow_reuse_address = True
        print(f"Serving at http://localhost:{port}")
        print(f"Static files from: {SITE_DIR}")
        print(f"Press Ctrl+C to stop.\n")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
