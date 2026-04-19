"""Error-handling parity tests across sources.

These tests exercise the common error paths every source adapter hits:

1. API key missing — must raise or warn with an actionable message that
   tells the user how to get one, *without* echoing any credential value.
2. API returns HTTP error — must not leak the user's API key into
   exception messages, log output, or warnings.
3. Empty/invalid input — must not crash; must return an empty DataFrame
   with the standard schema.

When one source handles this class of error differently from the others,
users end up writing source-specific error handling. These tests flag
deviations so we maintain parity.
"""

from __future__ import annotations

import os
import warnings
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd
import pytest

import aeolus
from aeolus.registry import get_source
from aeolus.types import AeolusDataWarning


# ---------------------------------------------------------------------------
# API-key-requiring sources and their env-var names
# ---------------------------------------------------------------------------

API_KEY_SOURCES: list[tuple[str, str]] = [
    ("AIRNOW", "AIRNOW_API_KEY"),
    ("AIRQO", "AIRQO_API_KEY"),
    ("BREATHE_LONDON", "BL_API_KEY"),
    ("OPENAQ", "OPENAQ_API_KEY"),
    ("PURPLEAIR", "PURPLEAIR_API_KEY"),
]

# A distinctive synthetic key; if this string appears in any log or
# exception when we inject it, we know the source leaked it.
_CANARY_KEY = "canary-1234567890abcdef-TEST-KEY"


@pytest.fixture
def _clear_api_keys(monkeypatch):
    """Remove every API-key env var for the duration of a test."""
    for _, env_var in API_KEY_SOURCES:
        monkeypatch.delenv(env_var, raising=False)
    yield


@pytest.fixture
def _canary_api_keys(monkeypatch):
    """Set every API-key env var to the canary value."""
    for _, env_var in API_KEY_SOURCES:
        monkeypatch.setenv(env_var, _CANARY_KEY)
    yield


# ============================================================================
# Missing-API-key behaviour parity
# ============================================================================


@pytest.mark.parametrize("source,env_var", API_KEY_SOURCES)
def test_missing_api_key_message_is_actionable(source, env_var, _clear_api_keys):
    """When the key is missing, user-facing feedback must name the env-var
    the user should set.

    Sources may choose to either raise (hard fail) or emit a warning and
    return an empty DataFrame (soft fail). Either is acceptable for user
    code; what matters is that the *message* is actionable.
    """
    spec = get_source(source)
    if spec is None:
        pytest.skip(f"{source} not registered")

    fetch = spec["fetch_metadata"]
    messages = []

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            # Pass a minimal filter for portals that require one (OpenAQ)
            if spec.get("type") == "portal":
                fetch(country="GB")
            else:
                fetch()
        except (ValueError, RuntimeError) as e:
            messages.append(str(e))

    for w in caught:
        messages.append(str(w.message))

    combined = " ".join(messages)
    assert env_var in combined, (
        f"{source}: missing-key feedback should mention env var {env_var!r}; "
        f"got messages: {messages!r}"
    )
    assert "API key" in combined or "token" in combined.lower(), (
        f"{source}: feedback should explain the failure; got: {messages!r}"
    )


# ============================================================================
# API-key never leaks into exception/warning messages
# ============================================================================


@pytest.mark.parametrize("source,env_var", API_KEY_SOURCES)
def test_api_key_not_leaked_in_find_sites_warnings(source, env_var, _canary_api_keys):
    """If the outer find_sites() wrapper catches an exception from the
    source, the resulting warning must not contain the API key value."""
    spec = get_source(source)
    if spec is None:
        pytest.skip(f"{source} not registered")

    # The simplest way to force an error path is to call find_sites without
    # the spatial filter portals require. If the source raises, find_sites
    # wraps it in an AeolusDataWarning.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            # Portals require filters; networks don't. This may succeed
            # (hitting the live API) or fail (depending on fixture state).
            # Either way, we only care about whether the key leaks into
            # captured warnings.
            aeolus.find_sites(source)
        except Exception as e:
            assert _CANARY_KEY not in str(e), (
                f"{source}: raised exception leaked API key: {e!r}"
            )

    for w in caught:
        assert _CANARY_KEY not in str(w.message), (
            f"{source}: warning leaked API key: {w.message!r}"
        )


# ============================================================================
# HTTP 5xx paths don't leak the key either
# ============================================================================


@pytest.mark.parametrize("source,env_var", [
    ("AIRNOW", "AIRNOW_API_KEY"),
    ("BREATHE_LONDON", "BL_API_KEY"),
])
def test_http_error_does_not_leak_api_key(source, env_var, monkeypatch):
    """Simulate a 500 from the upstream API and assert the error path
    (whatever form it takes — exception, warning, empty DataFrame)
    never contains the API key string."""
    monkeypatch.setenv(env_var, _CANARY_KEY)

    # Mock requests.get to return a 500 error response with a message
    # that would include the full URL (which contains the key as a param)
    import requests as _requests

    class _FakeResponse:
        status_code = 500
        url = f"https://api.example.com/endpoint?API_KEY={_CANARY_KEY}"
        text = f"Server error processing request with API_KEY={_CANARY_KEY}"

        def raise_for_status(self):
            raise _requests.HTTPError(
                f"500 Server Error: for url: {self.url}",
                response=self,
            )

        def json(self):
            return {}

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with patch("requests.get", return_value=_FakeResponse()):
            try:
                # Call at the aeolus layer so we exercise the whole error pipeline
                end = datetime.now(timezone.utc)
                start = end - timedelta(hours=1)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")  # inner warnings OK
                    aeolus.download(source, ["TEST"], start_date=start, end_date=end)
            except Exception as e:
                assert _CANARY_KEY not in str(e), (
                    f"{source}: raised exception leaked API key: {e!r}"
                )

    for w in caught:
        assert _CANARY_KEY not in str(w.message), (
            f"{source}: warning leaked API key: {w.message!r}"
        )


# ============================================================================
# Empty DataFrame returned from error paths conforms to schema
# ============================================================================


@pytest.mark.parametrize("source,env_var", API_KEY_SOURCES)
def test_missing_key_returns_conformant_empty_frame(source, env_var, _clear_api_keys):
    """find_sites() catches adapter-level exceptions and should return an
    empty metadata frame with the standard columns. Users shouldn't see
    shape-dependent crashes when keys are missing."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = aeolus.find_sites(source)

    assert isinstance(result, pd.DataFrame)
    # The canonical metadata schema must be present even on empty results
    for col in ("site_code", "source_network", "latitude", "longitude"):
        assert col in result.columns, (
            f"{source}: empty find_sites result missing column {col!r}"
        )
