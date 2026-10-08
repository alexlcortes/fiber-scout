"""Bounded fetching and readable-text extraction for business websites."""

import ipaddress
import math
from html.parser import HTMLParser
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_RESPONSE_BYTES = 2_000_000
DEFAULT_TIMEOUT_SECONDS = 15
BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "dd",
    "div",
    "dl",
    "dt",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "section",
    "table",
    "td",
    "th",
    "tr",
    "ul",
}
IGNORED_TAGS = {"head", "title", "script", "style", "noscript", "svg", "template"}


class WebsiteContent(TypedDict):
    """Readable content extracted from an HTML website response."""

    requested_url: str
    final_url: str
    title: str
    text: str
    truncated: bool


class WebsiteFetchError(RuntimeError):
    """Raised when a website cannot be safely fetched or parsed."""


class _ReadableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.ignored_depth = 0
        self.in_title = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del attrs
        if tag == "title":
            self.in_title = True
        if tag in IGNORED_TAGS:
            self.ignored_depth += 1
        if self.ignored_depth == 0 and tag in BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag in IGNORED_TAGS and self.ignored_depth:
            self.ignored_depth -= 1
        if self.ignored_depth == 0 and tag in BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.ignored_depth == 0:
            self.text_parts.append(data)


def extract_html_text(html: str) -> tuple[str, str]:
    """Return the document title and normalized visible text from HTML."""
    parser = _ReadableTextParser()
    parser.feed(html)
    parser.close()
    title = " ".join(" ".join(parser.title_parts).split())
    text = " ".join(" ".join(parser.text_parts).split())
    return title, text


def _validate_public_http_url(url: str) -> None:
    try:
        parsed_url = urlsplit(url)
        hostname = parsed_url.hostname
        port = parsed_url.port
    except ValueError as error:
        raise ValueError(f"invalid website URL: {error}") from error

    if parsed_url.scheme not in {"http", "https"} or not hostname:
        raise ValueError("website URL must be an absolute http or https URL")
    if parsed_url.username is not None or parsed_url.password is not None:
        raise ValueError("website URL must not contain embedded credentials")
    if port is not None and port not in {80, 443}:
        raise ValueError("website URL must use the standard HTTP or HTTPS port")
    if hostname.lower() == "localhost" or hostname.lower().endswith(
        (".localhost", ".local", ".internal")
    ):
        raise ValueError("website URL must use a public hostname")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("website URL must use a public IP address")


class _PublicRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        target_url = urljoin(request.full_url, new_url)
        _validate_public_http_url(target_url)
        if (
            urlsplit(request.full_url).scheme == "https"
            and urlsplit(target_url).scheme != "https"
        ):
            raise WebsiteFetchError("refusing HTTPS-to-HTTP redirect")
        return super().redirect_request(
            request, file, code, message, headers, target_url
        )


def fetch_website(
    url: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> WebsiteContent:
    """Fetch a public HTML page and return its title and readable text.

    Fetching is limited to standard HTTP(S) ports and ``max_bytes`` of
    response data. URLs and redirect targets must not use local hostnames or
    non-public IP literals. Network/DNS policies should also restrict outbound
    traffic when this tool is exposed to untrusted callers.
    """
    _validate_public_http_url(url)
    if (
        not isinstance(timeout_seconds, (int, float))
        or isinstance(timeout_seconds, bool)
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise ValueError("timeout_seconds must be a positive finite number")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")

    request = Request(
        url,
        headers={"User-Agent": "FiberScout/0.1 (business research)"},
    )
    opener = build_opener(_PublicRedirectHandler())

    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            final_url = response.geturl()
            _validate_public_http_url(final_url)
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise WebsiteFetchError(
                    f"unsupported content type: {content_type}"
                )
            body = response.read(max_bytes + 1)
            truncated = len(body) > max_bytes
            if truncated:
                body = body[:max_bytes]
            charset = response.headers.get_content_charset() or "utf-8"
    except HTTPError as error:
        raise WebsiteFetchError(
            f"website returned HTTP {error.code}: {url}"
        ) from error
    except URLError as error:
        raise WebsiteFetchError(f"could not fetch website: {error.reason}") from error

    try:
        html = body.decode(charset, errors="replace")
    except LookupError as error:
        raise WebsiteFetchError(f"unsupported response character encoding: {charset}") from error
    title, text = extract_html_text(html)
    return {
        "requested_url": url,
        "final_url": final_url,
        "title": title,
        "text": text,
        "truncated": truncated,
    }
