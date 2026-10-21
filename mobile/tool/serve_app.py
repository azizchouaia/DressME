"""Serve the built Flutter web app and the DressMe API from ONE address, so any browser works (no CORS).

    http://localhost:8090/            -> mobile/build/web (flutter build web)
    http://localhost:8090/m07/...     -> forwarded to the API on http://127.0.0.1:8010 (same for /m14/...)

usage (from mobile/):
    flutter build web --dart-define=API_URL=http://localhost:8090
    python tool/serve_app.py [--port 8090] [--api http://127.0.0.1:8010] [--web <path to build/web>]

The API address is 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 first and every
forwarded call waited ~2 s before falling back to the API, which listens on IPv4 only.
"""

import argparse
import functools
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_PREFIXES = ("/m07/", "/m14/")
HOP_HEADERS = {"connection", "keep-alive", "transfer-encoding", "content-length", "host"}


class Handler(SimpleHTTPRequestHandler):
    api = "http://127.0.0.1:8010"

    def _forward(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_HEADERS}
        req = urllib.request.Request(self.api + self.path, data=body, headers=headers, method=self.command)
        try:
            resp = urllib.request.urlopen(req, timeout=300)  # the first search loads FashionCLIP
        except urllib.error.HTTPError as err:  # 4xx/5xx from the API: pass them through as they are
            resp = err
        except OSError as err:
            self.send_error(502, f"API not reachable at {self.api}: {err}")
            return
        data = resp.read()
        self.send_response(resp.status)
        for k, v in resp.headers.items():
            if k.lower() not in HOP_HEADERS:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith(API_PREFIXES):
            return self._forward()
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith(API_PREFIXES):
            return self._forward()
        self.send_error(405)

    do_PATCH = do_DELETE = do_POST  # M14: accept / decline a hand-off, revoke a client's consent

    def end_headers(self):
        if not self.path.startswith(API_PREFIXES):
            self.send_header("Cache-Control", "no-store")  # always load the latest build
        super().end_headers()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--api", default="http://127.0.0.1:8010")
    ap.add_argument("--web", default=str(Path(__file__).resolve().parents[1] / "build" / "web"))
    args = ap.parse_args()
    Handler.api = args.api.rstrip("/")
    handler = functools.partial(Handler, directory=args.web)
    print(f"DressMe app on http://localhost:{args.port}/#/bo6_local_market (API {Handler.api}, files {args.web})")
    ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()


if __name__ == "__main__":
    main()
