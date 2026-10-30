"""Start ReMu's single-photo layers, back view, and chosen 3D builder.

SiTH is the builder already used on Kaggle. UP2You is the other one.
The photo is the outer layer. ReMu invents the inner layers and a back view.
"""

from __future__ import annotations

import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
INBOX = ROOT / "avatar_studio" / "web" / "garments" / "saved" / "one_photo"
STATUS = INBOX / "status.txt"
MAX_BYTES = 20 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str) -> None:
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/status":
            self._send(404, "not found")
            return
        self._send(200, STATUS.read_text(encoding="utf-8") if STATUS.exists() else "No clothes job yet.")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/from-photo":
            self._send(404, "not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BYTES:
            self._send(413, "The photo is missing or larger than 20 MB.")
            return
        builder = (parse_qs(urlparse(self.path).query).get("builder") or ["sith"])[0]
        if builder not in {"sith", "up2you"}:
            builder = "sith"
        INBOX.mkdir(parents=True, exist_ok=True)
        photo = INBOX / "outer.jpg"
        photo.write_bytes(self.rfile.read(length))
        (INBOX / "builder.txt").write_text(builder, encoding="utf-8")
        STATUS.write_text(
            f"Photo saved. Inventing layers and a back view, then building with {builder}.",
            encoding="utf-8",
        )
        script = "/mnt/c/Users/NADHIR/Desktop/Dressme/ai/remu/from_photo.sh"
        subprocess.Popen(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-lc", f"sed -i 's/\\r$//' {script} && bash {script}"],
        )
        self._send(200, STATUS.read_text(encoding="utf-8"))

    def log_message(self, fmt: str, *args) -> None:
        print(fmt % args)


def main() -> None:
    ThreadingHTTPServer(("127.0.0.1", 8891), Handler).serve_forever()


if __name__ == "__main__":
    main()
