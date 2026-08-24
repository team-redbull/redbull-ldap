"""Unit tests for the AD API client, with requests mocked out."""

import pytest
from requests.exceptions import ConnectTimeout, HTTPError

from app import group_check
from app.errors import NotInGroup, UpstreamUnavailable


class FakeResponse:
    def __init__(self, payload=None, error=None, invalid_json=False):
        self._payload = payload
        self._error = error
        self._invalid_json = invalid_json

    def raise_for_status(self):
        if self._error:
            raise self._error

    def json(self):
        if self._invalid_json:
            raise ValueError("not json")
        return self._payload


def install(monkeypatch, response=None, raises=None):
    """Point group_check at a fake session and return the captured kwargs."""
    captured = {}

    class FakeSession:
        def get(self, url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            if raises:
                raise raises
            return response

    monkeypatch.setattr(group_check, "get_session", FakeSession)
    return captured


def test_member_passes(monkeypatch):
    install(monkeypatch, FakeResponse(payload=True))

    assert group_check.assert_member("jdoe", "api-users") is None


def test_non_member_raises_not_in_group(monkeypatch):
    install(monkeypatch, FakeResponse(payload=False))

    with pytest.raises(NotInGroup):
        group_check.assert_member("jdoe", "api-users")


def test_request_is_shaped_as_the_ad_api_expects(monkeypatch):
    captured = install(monkeypatch, FakeResponse(payload=True))

    group_check.assert_member("jdoe", "api-users")

    assert captured["params"] == {
        "userSamAccountName": "jdoe",
        "groupSamAccountName": "api-users",
    }
    assert captured["headers"]["ClientId"] == "test-client-id"
    # An unbounded call would pin a worker thread for as long as AD hangs.
    assert captured["timeout"] > 0
    assert captured["verify"] is True


def test_transport_failure_is_upstream_unavailable(monkeypatch):
    install(monkeypatch, raises=ConnectTimeout("timed out"))

    with pytest.raises(UpstreamUnavailable):
        group_check.assert_member("jdoe", "api-users")


def test_http_error_is_upstream_unavailable(monkeypatch):
    install(monkeypatch, FakeResponse(error=HTTPError("500 Server Error")))

    with pytest.raises(UpstreamUnavailable):
        group_check.assert_member("jdoe", "api-users")


def test_non_json_body_is_upstream_unavailable(monkeypatch):
    install(monkeypatch, FakeResponse(invalid_json=True))

    with pytest.raises(UpstreamUnavailable):
        group_check.assert_member("jdoe", "api-users")


@pytest.mark.parametrize("payload", [None, "true", {"isMember": True}, 1])
def test_unexpected_payload_fails_as_unknown_not_as_deny(monkeypatch, payload):
    """If the AD API contract changes, say 'I do not know' rather than
    coercing a surprise payload into an allow or a deny."""
    install(monkeypatch, FakeResponse(payload=payload))

    with pytest.raises(UpstreamUnavailable):
        group_check.assert_member("jdoe", "api-users")
