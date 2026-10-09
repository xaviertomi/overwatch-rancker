from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2] / "docs"

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if path.startswith("/overwatch-rancker"):
            path = path[len("/overwatch-rancker"):]
        return str(ROOT / path.lstrip("/").replace("/", str(Path("/"))))

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4173
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
