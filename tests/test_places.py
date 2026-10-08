import json
import os
import unittest
from unittest.mock import patch

from fiber_scout.places import (
    MAX_RADIUS_METERS,
    MAX_RESULT_COUNT,
    PLACES_FIELD_MASK,
    PLACES_SEARCH_URL,
    PlacesAPIError,
    search_nearby,
)


class PlacesSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.response = {
            "places": [
                {
                    "id": "place-123",
                    "displayName": {"text": "Example Business"},
                    "formattedAddress": "12 Main St, Tampa, FL",
                    "location": {"latitude": 27.95, "longitude": -82.46},
                    "primaryTypeDisplayName": {"text": "Business"},
                    "googleMapsUri": "https://maps.google.com/?cid=123",
                }
            ]
        }

    def test_posts_nearby_request_and_normalizes_results(self) -> None:
        with patch(
            "fiber_scout.places.urlopen",
            return_value=MockResponse(self.response),
        ) as mocked_urlopen:
            results = search_nearby(
                27.95,
                -82.46,
                radius_meters=750,
                max_results=8,
                included_types=["restaurant"],
                api_key="test-key",
            )

        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, PLACES_SEARCH_URL)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("X-goog-api-key"), "test-key")
        self.assertEqual(request.get_header("X-goog-fieldmask"), PLACES_FIELD_MASK)
        self.assertEqual(
            json.loads(request.data),
            {
                "maxResultCount": 8,
                "rankPreference": "DISTANCE",
                "locationRestriction": {
                    "circle": {
                        "center": {"latitude": 27.95, "longitude": -82.46},
                        "radius": 750,
                    }
                },
                "includedTypes": ["restaurant"],
            },
        )
        self.assertEqual(
            results,
            [
                {
                    "place_id": "place-123",
                    "name": "Example Business",
                    "address": "12 Main St, Tampa, FL",
                    "latitude": 27.95,
                    "longitude": -82.46,
                    "primary_type": "Business",
                    "google_maps_url": "https://maps.google.com/?cid=123",
                }
            ],
        )
        self.assertEqual(mocked_urlopen.call_args.kwargs["timeout"], 15)

    def test_reads_api_key_from_environment(self) -> None:
        with (
            patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "env-test-key"}),
            patch(
                "fiber_scout.places.urlopen",
                return_value=MockResponse({"places": []}),
            ) as mocked_urlopen,
        ):
            results = search_nearby(27.95, -82.46)

        self.assertEqual(results, [])
        self.assertEqual(
            mocked_urlopen.call_args.args[0].get_header("X-goog-api-key"),
            "env-test-key",
        )

    def test_accepts_empty_places_list(self) -> None:
        with patch(
            "fiber_scout.places.urlopen",
            return_value=MockResponse({"places": []}),
        ):
            self.assertEqual(
                search_nearby(27.95, -82.46, api_key="test-key"),
                [],
            )

    def test_rejects_invalid_coordinates_and_limits(self) -> None:
        cases = [
            ((91, 0), {}, "latitude"),
            ((27, -181), {}, "longitude"),
            ((27, -82), {"radius_meters": MAX_RADIUS_METERS + 1}, "radius"),
            ((27, -82), {"max_results": MAX_RESULT_COUNT + 1}, "max_results"),
            ((27, -82), {"included_types": "restaurant"}, "included_types"),
        ]
        for coordinates, options, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(
                ValueError, message
            ):
                search_nearby(*coordinates, api_key="test-key", **options)

    def test_requires_api_key(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(ValueError, "GOOGLE_MAPS_API_KEY"),
        ):
            search_nearby(27.95, -82.46)

    def test_rejects_malformed_response(self) -> None:
        with (
            patch(
                "fiber_scout.places.urlopen",
                return_value=MockResponse({"unexpected": []}),
            ),
            self.assertRaisesRegex(PlacesAPIError, "places list"),
        ):
            search_nearby(27.95, -82.46, api_key="test-key")

    def test_rejects_incomplete_place_result(self) -> None:
        with (
            patch(
                "fiber_scout.places.urlopen",
                return_value=MockResponse({"places": [{"id": "place-123"}]}),
            ),
            self.assertRaisesRegex(PlacesAPIError, "displayName"),
        ):
            search_nearby(27.95, -82.46, api_key="test-key")


class MockResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "MockResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


if __name__ == "__main__":
    unittest.main()
