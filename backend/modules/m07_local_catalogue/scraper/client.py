"""Polite HTTP client: honours robots.txt, spaces out requests to one host, retries transient errors."""

import json
import threading
import time
from http.cookiejar import DefaultCookiePolicy
from urllib import robotparser
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 DressMeCatalogueBot/0.1 (student project, ESPRIT)"
)
XHR_JSON = {"Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest"}


class Disallowed(Exception):
    pass


class Http:
    def __init__(self, delay: float = 0.5, timeout: float = 30):
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"})
        # Stateless crawl: Shopify answers 429 on /products.json once its session cookies are set.
        self.session.cookies.set_policy(DefaultCookiePolicy(allowed_domains=[]))
        retry = Retry(
            total=6, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"]
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
        self.session.mount("http://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}
        self._last_hit: dict[str, float] = {}
        self._lock = threading.Lock()

    def _robots_for(self, url: str) -> robotparser.RobotFileParser | None:
        parts = urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        with self._lock:
            if root in self._robots:
                return self._robots[root]
        parser: robotparser.RobotFileParser | None = robotparser.RobotFileParser()
        try:
            resp = self.session.get(root + "/robots.txt", timeout=self.timeout)
            if resp.status_code == 200 and "html" not in resp.headers.get("content-type", ""):
                parser.parse(resp.text.splitlines())
            else:
                parser = None  # no robots.txt -> everything allowed
        except requests.RequestException:
            parser = None
        with self._lock:
            self._robots[root] = parser
        return parser

    def allowed(self, url: str) -> bool:
        parser = self._robots_for(url)
        return parser is None or parser.can_fetch(USER_AGENT, url)

    def _wait(self, url: str) -> None:
        host = urlsplit(url).netloc
        with self._lock:
            wait = self._last_hit.get(host, 0) + self.delay - time.monotonic()
            self._last_hit[host] = time.monotonic() + max(wait, 0)
        if wait > 0:
            time.sleep(wait)

    def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> requests.Response:
        full = requests.Request("GET", url, params=params).prepare().url or url
        if not self.allowed(full):
            raise Disallowed(full)
        self._wait(url)
        resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        return resp

    def check(self, url: str) -> tuple[int, str]:
        """(HTTP status, final URL) without downloading the body; status 0 = network error, -1 = robots."""
        if not self.allowed(url):
            return -1, url
        for attempt in range(4):
            self._wait(url)
            try:
                resp = self.session.head(url, allow_redirects=True, timeout=self.timeout)
                if resp.status_code == 429 and attempt < 3:  # rate limited (Shopify): back off and retry
                    time.sleep(float(resp.headers.get("Retry-After") or 0) or 5 * (attempt + 1))
                    continue
                if resp.status_code in (403, 405, 501) or resp.status_code >= 500:
                    # Some servers refuse HEAD: retry with a streamed GET and close it straight away.
                    with self.session.get(
                        url, stream=True, allow_redirects=True, timeout=self.timeout
                    ) as get:
                        return get.status_code, get.url
                return resp.status_code, resp.url
            except requests.RequestException:
                return 0, url
        return 429, url

    def json(self, url: str, params: dict | None = None, headers: dict | None = None):
        resp = self.get(url, params=params, headers=headers)
        return json.loads(resp.content.decode("utf-8-sig"))

    def text(self, url: str, params: dict | None = None, headers: dict | None = None) -> str:
        resp = self.get(url, params=params, headers=headers)
        resp.encoding = resp.encoding if resp.encoding and resp.encoding.lower() != "iso-8859-1" else "utf-8"
        return resp.text
