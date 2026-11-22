"""SSRF-safe page fetcher + readable-text extraction for saved websites."""
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3


class FetchError(Exception):
    pass


def assert_public_url(url):
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("Only http(s) URLs are allowed.")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except socket.gaierror as e:
        raise FetchError("Could not resolve host.") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            raise FetchError("URL points to a non-public address.")


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "aside"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article"}

    def __init__(self):
        super().__init__()
        self.title, self._in_title, self._skip, self.parts = "", False, 0, []

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        elif tag in self.SKIP:
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip and data.strip():
            self.parts.append(data.strip() + " ")


def html_to_text(html):
    p = _TextExtractor()
    p.feed(html)
    text = "".join(p.parts)
    lines = [" ".join(l.split()) for l in text.splitlines()]
    return " ".join(p.title.split()), "\n\n".join(l for l in lines if l)


def fetch_page(url):
    """Returns (title, text). Re-validates every redirect hop against the public-address rule."""
    current = url
    with httpx.Client(timeout=10, follow_redirects=False, headers={"User-Agent": "PersonalSearchBot/1.0"}) as c:
        for _ in range(MAX_REDIRECTS + 1):
            assert_public_url(current)
            try:
                with c.stream("GET", current) as r:
                    if r.is_redirect:
                        current = urljoin(current, r.headers.get("location", ""))
                        continue
                    r.raise_for_status()
                    ctype = r.headers.get("content-type", "")
                    if "html" not in ctype and "text/plain" not in ctype:
                        raise FetchError("Unsupported content type.")
                    buf = b""
                    for part in r.iter_bytes():
                        buf += part
                        if len(buf) > MAX_BYTES:
                            break
                    html = buf[:MAX_BYTES].decode(r.encoding or "utf-8", errors="replace")
            except httpx.HTTPError as e:
                raise FetchError(f"Fetch failed: {e.__class__.__name__}") from e
            if "text/plain" in ctype:
                return "", html
            return html_to_text(html)
    raise FetchError("Too many redirects.")
