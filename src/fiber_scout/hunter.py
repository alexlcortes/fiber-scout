"""Business-domain contact discovery through Hunter's Domain Search API."""

import json
import math
import os
import re
import socket
from collections.abc import Mapping
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from dotenv import load_dotenv

HUNTER_DOMAIN_SEARCH_URL = "https://api.hunter.io/v2/domain-search"
DEFAULT_TIMEOUT_SECONDS = 15
MAX_RESULTS = 100
DOMAIN_PATTERN = re.compile(
    r"(?=.{1,253}\Z)"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}\Z"
)


class HunterContact(TypedDict):
    """An email contact and the source evidence supplied by Hunter."""

    email: str
    first_name: str | None
    last_name: str | None
    position: str | None
    email_type: str | None
    provider_confidence: int | None
    source_urls: list[str]
    verification_status: str | None


class HunterDomainSearchResult(TypedDict):
    """Contact results and organization details returned by Hunter."""

    domain: str
    organization: str | None
    email_pattern: str | None
    contacts: list[HunterContact]


class HunterAPIError(RuntimeError):
    """Raised when Hunter returns an unsuccessful or invalid response."""


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HunterAPIError(f"Hunter response field {field} must be text")
    return value


def _parse_contact(value: object, index: int) -> HunterContact:
    if not isinstance(value, Mapping):
        raise HunterAPIError(f"Hunter contact {index} must be an object")

    email = value.get("value")
    if not isinstance(email, str) or not email:
        raise HunterAPIError(f"Hunter contact {index} is missing its email address")

    raw_confidence = value.get("confidence")
    if raw_confidence is not None and (
        not isinstance(raw_confidence, int)
        or isinstance(raw_confidence, bool)
        or not 0 <= raw_confidence <= 100
    ):
        raise HunterAPIError(
            f"Hunter contact {index} has an invalid confidence score"
        )

    sources = value.get("sources", [])
    if not isinstance(sources, list):
        raise HunterAPIError(f"Hunter contact {index} sources must be a list")
    source_urls: list[str] = []
    for source_index, source in enumerate(sources):
        if not isinstance(source, Mapping):
            raise HunterAPIError(
                f"Hunter contact {index} source {source_index} must be an object"
            )
        source_url = source.get("uri")
        if source_url is not None:
            if not isinstance(source_url, str):
                raise HunterAPIError(
                    f"Hunter contact {index} source {source_index} URI must be text"
                )
            source_urls.append(source_url)

    verification = value.get("verification")
    if verification is not None and not isinstance(verification, Mapping):
        raise HunterAPIError(f"Hunter contact {index} verification must be an object")
    verification_status = (
        _optional_text(verification.get("status"), "verification.status")
        if isinstance(verification, Mapping)
        else None
    )

    return {
        "email": email,
        "first_name": _optional_text(value.get("first_name"), "first_name"),
        "last_name": _optional_text(value.get("last_name"), "last_name"),
        "position": _optional_text(value.get("position"), "position"),
        "email_type": _optional_text(value.get("type"), "type"),
        "provider_confidence": raw_confidence,
        "source_urls": source_urls,
        "verification_status": verification_status,
    }


def search_domain_contacts(
    domain: str,
    *,
    limit: int = 10,
    email_type: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    api_key: str | None = None,
) -> HunterDomainSearchResult:
    """Search Hunter for source-backed email contacts at a business domain.

    The API key is read from ``HUNTER_API_KEY`` or the project's ``.env`` file
    unless supplied explicitly. Hunter's numeric confidence is returned as
    provided; this function does not convert it into a guessed confidence label.
    """
    if not isinstance(domain, str):
        raise ValueError("domain must be a bare public domain such as example.com")
    domain = domain.strip().lower()
    if not DOMAIN_PATTERN.fullmatch(domain):
        raise ValueError("domain must be a bare public domain such as example.com")
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= MAX_RESULTS
    ):
        raise ValueError(f"limit must be an integer from 1 to {MAX_RESULTS}")
    if email_type is not None and email_type not in {"personal", "generic"}:
        raise ValueError("email_type must be 'personal', 'generic', or None")
    if (
        not isinstance(timeout_seconds, (int, float))
        or isinstance(timeout_seconds, bool)
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise ValueError("timeout_seconds must be a positive finite number")

    if api_key is None:
        load_dotenv(override=False)
        api_key = os.environ.get("HUNTER_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError("Set HUNTER_API_KEY in the environment or .env file")

    query: dict[str, str | int] = {"domain": domain, "limit": limit}
    if email_type is not None:
        query["type"] = email_type
    request = Request(
        f"{HUNTER_DOMAIN_SEARCH_URL}?{urlencode(query)}",
        headers={"X-API-KEY": api_key, "Accept": "application/json"},
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read())
    except HTTPError as error:
        raise HunterAPIError(
            f"Hunter API returned HTTP {error.code}"
        ) from error
    except (URLError, TimeoutError, socket.timeout) as error:
        raise HunterAPIError(f"could not reach Hunter API: {error}") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HunterAPIError("Hunter API returned invalid JSON") from error

    if not isinstance(payload, Mapping):
        raise HunterAPIError("Hunter API response must be a JSON object")
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise HunterAPIError("Hunter API response is missing its data object")
    response_domain = data.get("domain")
    if not isinstance(response_domain, str) or not response_domain:
        raise HunterAPIError("Hunter API response is missing its domain")
    emails = data.get("emails")
    if not isinstance(emails, list):
        raise HunterAPIError("Hunter API response is missing its emails list")

    return {
        "domain": response_domain,
        "organization": _optional_text(data.get("organization"), "organization"),
        "email_pattern": _optional_text(data.get("pattern"), "pattern"),
        "contacts": [
            _parse_contact(contact, index)
            for index, contact in enumerate(emails)
        ],
    }
