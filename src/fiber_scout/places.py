"""Nearby business discovery through Google Places API (New)."""

import json
import math
import os
from collections.abc import Sequence
from typing import TypedDict
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
PLACES_FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.location,"
    "places.primaryTypeDisplayName,"
    "places.googleMapsUri"
)
MAX_RADIUS_METERS = 50_000
MAX_RESULT_COUNT = 20


class PlaceResult(TypedDict):
    """Candidate place details returned by the nearby-search tool."""

    place_id: str
    name: str
    address: str
    latitude: float
    longitude: float
    primary_type: str | None
    google_maps_url: str | None


class PlacesAPIError(RuntimeError):
    """Raised when Google Places returns an unsuccessful or invalid response."""


def _required_text(value: object, field: str, place_index: int) -> str:
    if not isinstance(value, str) or not value:
        raise PlacesAPIError(
            f"Google Places result {place_index} is missing {field}"
        )
    return value


def _parse_place(place: object, place_index: int) -> PlaceResult:
    if not isinstance(place, dict):
        raise PlacesAPIError(f"Google Places result {place_index} is not an object")

    display_name = place.get("displayName")
    if not isinstance(display_name, dict):
        raise PlacesAPIError(
            f"Google Places result {place_index} is missing displayName"
        )

    location = place.get("location")
    if not isinstance(location, dict):
        raise PlacesAPIError(f"Google Places result {place_index} is missing location")

    latitude = location.get("latitude")
    longitude = location.get("longitude")
    if (
        not isinstance(latitude, (int, float))
        or not isinstance(longitude, (int, float))
        or not math.isfinite(latitude)
        or not math.isfinite(longitude)
    ):
        raise PlacesAPIError(
            f"Google Places result {place_index} has invalid coordinates"
        )

    primary_type_display_name = place.get("primaryTypeDisplayName")
    primary_type = None
    if primary_type_display_name is not None:
        if not isinstance(primary_type_display_name, dict):
            raise PlacesAPIError(
                f"Google Places result {place_index} has invalid primaryTypeDisplayName"
            )
        primary_type = _required_text(
            primary_type_display_name.get("text"),
            "primaryTypeDisplayName.text",
            place_index,
        )

    google_maps_url = place.get("googleMapsUri")
    if google_maps_url is not None:
        google_maps_url = _required_text(
            google_maps_url, "googleMapsUri", place_index
        )

    return {
        "place_id": _required_text(place.get("id"), "id", place_index),
        "name": _required_text(display_name.get("text"), "displayName.text", place_index),
        "address": _required_text(
            place.get("formattedAddress"), "formattedAddress", place_index
        ),
        "latitude": float(latitude),
        "longitude": float(longitude),
        "primary_type": primary_type,
        "google_maps_url": google_maps_url,
    }


def search_nearby(
    latitude: float,
    longitude: float,
    *,
    radius_meters: float = 1_000,
    max_results: int = 20,
    included_types: Sequence[str] | None = None,
    api_key: str | None = None,
) -> list[PlaceResult]:
    """Find candidate places around a coordinate using Google Places API.

    Coordinates and radius are in decimal degrees and meters. The key is read
    from ``GOOGLE_MAPS_API_KEY`` unless supplied explicitly. Returned places
    are discovery leads, not independently verified business facts.
    """
    if (
        not isinstance(latitude, (int, float))
        or isinstance(latitude, bool)
        or not math.isfinite(latitude)
        or not -90 <= latitude <= 90
    ):
        raise ValueError("latitude must be a finite number from -90 to 90")
    if (
        not isinstance(longitude, (int, float))
        or isinstance(longitude, bool)
        or not math.isfinite(longitude)
        or not -180 <= longitude <= 180
    ):
        raise ValueError("longitude must be a finite number from -180 to 180")
    if (
        not isinstance(radius_meters, (int, float))
        or isinstance(radius_meters, bool)
        or not math.isfinite(radius_meters)
        or not 0 < radius_meters <= MAX_RADIUS_METERS
    ):
        raise ValueError(f"radius_meters must be greater than 0 and at most {MAX_RADIUS_METERS}")
    if (
        not isinstance(max_results, int)
        or isinstance(max_results, bool)
        or not 1 <= max_results <= MAX_RESULT_COUNT
    ):
        raise ValueError(f"max_results must be an integer from 1 to {MAX_RESULT_COUNT}")
    if included_types is not None and (
        isinstance(included_types, str)
        or any(not isinstance(place_type, str) or not place_type for place_type in included_types)
    ):
        raise ValueError("included_types must contain non-empty strings")

    if api_key is None:
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError(
            "Set GOOGLE_MAPS_API_KEY or pass api_key to search_nearby"
        )

    request_body: dict[str, object] = {
        "maxResultCount": max_results,
        "rankPreference": "DISTANCE",
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": radius_meters,
            }
        },
    }
    if included_types is not None:
        request_body["includedTypes"] = list(included_types)

    request = Request(
        PLACES_SEARCH_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": PLACES_FIELD_MASK,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read())
    except HTTPError as error:
        raise PlacesAPIError(
            f"Google Places API returned HTTP {error.code}"
        ) from error

    if not isinstance(payload, dict) or not isinstance(payload.get("places"), list):
        raise PlacesAPIError("Google Places API response must contain a places list")

    return [_parse_place(place, index) for index, place in enumerate(payload["places"])]
