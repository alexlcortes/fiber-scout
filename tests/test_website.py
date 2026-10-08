import unittest
from email.message import Message
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from fiber_scout.website import (
    DEFAULT_TIMEOUT_SECONDS,
    WebsiteFetchError,
    _PublicRedirectHandler,
    extract_html_text,
    fetch_website,
)


class WebsiteFetchTests(unittest.TestCase):
    def test_fetches_html_and_extracts_readable_text(self) -> None:
        body = (
            b"<html><head><title>Example &amp; Co</title>"
            b"<script>tracking()</script></head><body>"
            b"<h1>Welcome</h1><p>Fiber &amp; cloud services.</p>"
            b"<style>.hidden { display: none }</style></body></html>"
        )
        response = MockResponse(
            body,
            content_type="text/html; charset=utf-8",
            final_url="https://example.com/about",
        )
        with patch(
            "fiber_scout.website.build_opener",
            return_value=MockOpener(response),
        ) as mocked_build_opener:
            result = fetch_website("https://example.com", max_bytes=500)

        self.assertEqual(result["requested_url"], "https://example.com")
        self.assertEqual(result["final_url"], "https://example.com/about")
        self.assertEqual(result["title"], "Example & Co")
        self.assertEqual(result["text"], "Welcome Fiber & cloud services.")
        self.assertFalse(result["truncated"])
        self.assertIsInstance(mocked_build_opener.call_args.args[0], _PublicRedirectHandler)
        opener = mocked_build_opener.return_value
        self.assertEqual(opener.open_call[1], DEFAULT_TIMEOUT_SECONDS)
        self.assertEqual(response.read_limit, 501)

    def test_extract_html_text_normalizes_whitespace(self) -> None:
        title, text = extract_html_text(
            "<title>  Example\nSite </title>"
            "<main><p>First&nbsp; paragraph</p><p>Second</p></main>"
        )

        self.assertEqual(title, "Example Site")
        self.assertEqual(text, "First paragraph Second")

    def test_truncates_oversized_response_and_marks_it(self) -> None:
        response = MockResponse(
            b"<html><body>abcdef</body></html>",
            content_type="text/html",
        )
        with patch(
            "fiber_scout.website.build_opener",
            return_value=MockOpener(response),
        ):
            result = fetch_website("https://example.com", max_bytes=18)

        self.assertTrue(result["truncated"])
        self.assertLessEqual(response.read_limit, 19)

    def test_accepts_xhtml(self) -> None:
        response = MockResponse(
            b"<html><body><p>Hello XHTML</p></body></html>",
            content_type="application/xhtml+xml",
        )
        with patch(
            "fiber_scout.website.build_opener",
            return_value=MockOpener(response),
        ):
            result = fetch_website("https://example.com")

        self.assertEqual(result["text"], "Hello XHTML")

    def test_rejects_non_html_content_type(self) -> None:
        response = MockResponse(b'{"ok": true}', content_type="application/json")
        with (
            patch(
                "fiber_scout.website.build_opener",
                return_value=MockOpener(response),
            ),
            self.assertRaisesRegex(WebsiteFetchError, "unsupported content type"),
        ):
            fetch_website("https://example.com")

    def test_reports_http_error(self) -> None:
        with (
            patch(
                "fiber_scout.website.build_opener",
                return_value=MockOpener(
                    error=HTTPError(
                        "https://example.com/missing",
                        404,
                        "Not Found",
                        None,
                        None,
                    )
                ),
            ),
            self.assertRaisesRegex(WebsiteFetchError, "HTTP 404"),
        ):
            fetch_website("https://example.com/missing")

    def test_reports_network_error(self) -> None:
        with (
            patch(
                "fiber_scout.website.build_opener",
                return_value=MockOpener(error=URLError("offline")),
            ),
            self.assertRaisesRegex(WebsiteFetchError, "offline"),
        ):
            fetch_website("https://example.com")

    def test_rejects_invalid_urls_and_limits(self) -> None:
        cases = [
            ("ftp://example.com", {}, "http or https"),
            ("https://user:secret@example.com", {}, "credentials"),
            ("http://localhost", {}, "public hostname"),
            ("http://127.0.0.1", {}, "public IP"),
            ("https://example.com:8443", {}, "standard"),
            ("https://example.com", {"timeout_seconds": 0}, "timeout_seconds"),
            ("https://example.com", {"max_bytes": 0}, "max_bytes"),
        ]
        for url, options, message in cases:
            with self.subTest(url=url, options=options), self.assertRaisesRegex(
                ValueError, message
            ):
                fetch_website(url, **options)

    def test_redirect_handler_rejects_private_target_and_https_downgrade(self) -> None:
        handler = _PublicRedirectHandler()
        request = MockRequest("https://example.com")

        with self.assertRaisesRegex(ValueError, "public IP"):
            handler.redirect_request(
                request, None, 302, "Found", {}, "http://127.0.0.1/admin"
            )
        with self.assertRaisesRegex(WebsiteFetchError, "HTTPS-to-HTTP"):
            handler.redirect_request(
                request, None, 302, "Found", {}, "http://example.com"
            )


class MockResponse:
    def __init__(
        self,
        body: bytes,
        *,
        content_type: str,
        final_url: str = "https://example.com",
    ) -> None:
        self.body = body
        self.final_url = final_url
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.read_limit: int | None = None

    def __enter__(self) -> "MockResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def geturl(self) -> str:
        return self.final_url

    def read(self, limit: int = -1) -> bytes:
        self.read_limit = limit
        return self.body if limit < 0 else self.body[:limit]


class MockOpener:
    def __init__(
        self, response: MockResponse | None = None, error: Exception | None = None
    ) -> None:
        self.response = response
        self.error = error
        self.open_call: tuple[object, float] | None = None

    def open(self, request: object, timeout: float) -> MockResponse:
        self.open_call = (request, timeout)
        if self.error is not None:
            raise self.error
        if self.response is None:
            raise AssertionError("test opener requires a response or an error")
        return self.response


class MockRequest:
    def __init__(self, full_url: str) -> None:
        self.full_url = full_url


if __name__ == "__main__":
    unittest.main()
