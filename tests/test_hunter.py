import json
import os
import unittest
from email.message import Message
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from fiber_scout.hunter import (
    HUNTER_DOMAIN_SEARCH_URL,
    MAX_RESULTS,
    HunterAPIError,
    search_domain_contacts,
)


class HunterDomainSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "data": {
                "domain": "example.com",
                "organization": "Example Company",
                "pattern": "{first}@example.com",
                "emails": [
                    {
                        "value": "jane@example.com",
                        "type": "personal",
                        "confidence": 91,
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "position": "IT Director",
                        "sources": [
                            {
                                "uri": "https://example.com/team",
                                "domain": "example.com",
                            },
                            {"uri": "https://conference.example/speakers/jane"},
                        ],
                        "verification": {"status": "valid"},
                    }
                ],
            }
        }

    def test_sends_bounded_request_and_normalizes_contact_sources(self) -> None:
        response = MockResponse(self.payload)
        with patch(
            "fiber_scout.hunter.urlopen", return_value=response
        ) as mocked_urlopen:
            result = search_domain_contacts(
                "EXAMPLE.COM",
                limit=5,
                email_type="personal",
                api_key="test-api-key",
            )

        request = mocked_urlopen.call_args.args[0]
        parsed_url = urlsplit(request.full_url)
        self.assertEqual(f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}", HUNTER_DOMAIN_SEARCH_URL)
        self.assertEqual(
            parse_qs(parsed_url.query),
            {"domain": ["example.com"], "limit": ["5"], "type": ["personal"]},
        )
        self.assertEqual(request.get_header("X-api-key"), "test-api-key")
        self.assertNotIn("test-api-key", request.full_url)
        self.assertEqual(mocked_urlopen.call_args.kwargs["timeout"], 15)
        self.assertEqual(
            result,
            {
                "domain": "example.com",
                "organization": "Example Company",
                "email_pattern": "{first}@example.com",
                "contacts": [
                    {
                        "email": "jane@example.com",
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "position": "IT Director",
                        "email_type": "personal",
                        "provider_confidence": 91,
                        "source_urls": [
                            "https://example.com/team",
                            "https://conference.example/speakers/jane",
                        ],
                        "verification_status": "valid",
                    }
                ],
            },
        )

    def test_reads_api_key_from_environment(self) -> None:
        with (
            patch.dict(os.environ, {"HUNTER_API_KEY": "environment-key"}),
            patch(
                "fiber_scout.hunter.load_dotenv"
            ) as mocked_load_dotenv,
            patch(
                "fiber_scout.hunter.urlopen",
                return_value=MockResponse({"data": {"domain": "example.com", "emails": []}}),
            ) as mocked_urlopen,
        ):
            result = search_domain_contacts("example.com")

        mocked_load_dotenv.assert_called_once_with(override=False)
        self.assertEqual(result["contacts"], [])
        self.assertEqual(
            mocked_urlopen.call_args.args[0].get_header("X-api-key"),
            "environment-key",
        )

    def test_requires_api_key(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("fiber_scout.hunter.load_dotenv"),
            self.assertRaisesRegex(ValueError, "HUNTER_API_KEY"),
        ):
            search_domain_contacts("example.com")

    def test_accepts_no_contacts(self) -> None:
        with patch(
            "fiber_scout.hunter.urlopen",
            return_value=MockResponse(
                {"data": {"domain": "example.com", "emails": []}}
            ),
        ):
            result = search_domain_contacts("example.com", api_key="test-key")

        self.assertEqual(result["contacts"], [])

    def test_rejects_invalid_domain_and_options(self) -> None:
        cases = [
            ("https://example.com", {}, "bare public domain"),
            ("localhost", {}, "bare public domain"),
            ("example.com/path", {}, "bare public domain"),
            ("example.com", {"limit": 0}, "limit"),
            ("example.com", {"limit": MAX_RESULTS + 1}, "limit"),
            ("example.com", {"email_type": "unknown"}, "email_type"),
            ("example.com", {"timeout_seconds": 0}, "timeout_seconds"),
        ]
        for domain, options, message in cases:
            with self.subTest(domain=domain, options=options), self.assertRaisesRegex(
                ValueError, message
            ):
                search_domain_contacts(domain, api_key="test-key", **options)

    def test_surfaces_http_error_without_including_api_key(self) -> None:
        with (
            patch(
                "fiber_scout.hunter.urlopen",
                side_effect=HTTPError(
                    HUNTER_DOMAIN_SEARCH_URL,
                    401,
                    "Unauthorized",
                    None,
                    None,
                ),
            ),
            self.assertRaisesRegex(HunterAPIError, "HTTP 401") as raised,
        ):
            search_domain_contacts("example.com", api_key="secret-key")

        self.assertNotIn("secret-key", str(raised.exception))

    def test_surfaces_network_errors(self) -> None:
        with (
            patch(
                "fiber_scout.hunter.urlopen",
                side_effect=URLError("offline"),
            ),
            self.assertRaisesRegex(HunterAPIError, "offline"),
        ):
            search_domain_contacts("example.com", api_key="test-key")

    def test_rejects_malformed_provider_response(self) -> None:
        cases = [
            ({"unexpected": {}}, "data object"),
            ({"data": {"domain": "example.com"}}, "emails list"),
            (
                {"data": {"domain": "example.com", "emails": [{"confidence": 101}]}},
                "email address",
            ),
            (
                {
                    "data": {
                        "domain": "example.com",
                        "emails": [{"value": "jane@example.com", "confidence": 101}],
                    }
                },
                "confidence score",
            ),
        ]
        for payload, message in cases:
            with self.subTest(message=message), patch(
                "fiber_scout.hunter.urlopen",
                return_value=MockResponse(payload),
            ), self.assertRaisesRegex(HunterAPIError, message):
                search_domain_contacts("example.com", api_key="test-key")


class MockResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.body = json.dumps(payload).encode("utf-8")
        self.headers = Message()
        self.headers["Content-Type"] = "application/json"

    def __enter__(self) -> "MockResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


if __name__ == "__main__":
    unittest.main()
