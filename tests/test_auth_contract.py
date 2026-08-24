"""Pins the wire contract that consuming services depend on."""

import pytest

from app import group_check, ldap_auth
from app.errors import InvalidCredentials, NotInGroup, UpstreamUnavailable
from tests.conftest import VALID_BODY


def test_authenticated_user_in_group(client, ldap_ok, group_ok):
    response = client.post("/auth", json=VALID_BODY)

    assert response.status_code == 200
    # Success is exactly one key - no null error fields to confuse callers.
    assert response.json() == {"authenticated": True}


def test_invalid_credentials(client, monkeypatch, group_ok):
    def reject(username, password):
        raise InvalidCredentials()

    monkeypatch.setattr(ldap_auth, "authenticate", reject)

    response = client.post("/auth", json=VALID_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is False
    assert body["error_code"] == "invalid_credentials"
    # The message must not reveal which half was wrong, or echo the username.
    assert "jdoe" not in body["error"]


def test_not_in_group(client, ldap_ok, monkeypatch):
    def reject(username, group):
        raise NotInGroup(username, group)

    monkeypatch.setattr(group_check, "assert_member", reject)

    response = client.post("/auth", json=VALID_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is False
    assert body["error_code"] == "not_in_group"


def test_group_check_is_skipped_when_credentials_fail(client, monkeypatch):
    """A failed bind must not leak group membership for an unverified user."""
    calls = []

    def reject(username, password):
        raise InvalidCredentials()

    monkeypatch.setattr(ldap_auth, "authenticate", reject)
    monkeypatch.setattr(
        group_check, "assert_member", lambda username, group: calls.append(group)
    )

    client.post("/auth", json=VALID_BODY)

    assert calls == []


@pytest.mark.parametrize("dependency", ["LDAP", "AD API"])
def test_upstream_failure_is_not_a_denial(client, monkeypatch, dependency, group_ok):
    """The core fix: an outage must be distinguishable from a rejection."""

    def blow_up(*args, **kwargs):
        raise UpstreamUnavailable(dependency)

    target = ldap_auth if dependency == "LDAP" else group_check
    name = "authenticate" if dependency == "LDAP" else "assert_member"
    monkeypatch.setattr(target, name, blow_up)

    response = client.post("/auth", json=VALID_BODY)

    assert response.status_code == 502
    body = response.json()
    assert body["error_code"] == "upstream_unavailable"
    # No 'authenticated' key at all: a caller that reads it without checking
    # the status gets a KeyError instead of silently denying the user.
    assert "authenticated" not in body


def test_upstream_error_does_not_leak_internals(client, monkeypatch, group_ok):
    def blow_up(username, password):
        raise UpstreamUnavailable("LDAP")

    monkeypatch.setattr(ldap_auth, "authenticate", blow_up)

    body = client.post("/auth", json=VALID_BODY).json()

    for leak in ("ldap.test.invalid", "Traceback", "ldap3", "TESTDOMAIN"):
        assert leak not in body["error"]


@pytest.mark.parametrize(
    "body",
    [
        {"username": "jdoe", "password": "", "group": "api-users"},
        {"username": "", "password": "s3cret", "group": "api-users"},
        {"username": "jdoe", "password": "s3cret", "group": ""},
        {"username": "jdoe", "password": "s3cret"},
    ],
    ids=["empty-password", "empty-username", "empty-group", "missing-group"],
)
def test_malformed_requests_are_rejected(client, monkeypatch, body):
    """An empty password must never reach LDAP: on many directories a simple
    bind with an empty password succeeds as an anonymous session."""
    reached = []
    monkeypatch.setattr(
        ldap_auth, "authenticate", lambda u, p: reached.append(u)
    )

    response = client.post("/auth", json=body)

    assert response.status_code == 422
    assert reached == []


def test_password_is_not_echoed_in_validation_errors(client):
    """SecretStr keeps the password out of the 422 body."""
    response = client.post(
        "/auth", json={"username": "jdoe", "password": "s3cret", "group": ""}
    )

    assert response.status_code == 422
    assert "s3cret" not in response.text


def test_health_does_not_touch_upstreams(client, monkeypatch):
    def blow_up(*args, **kwargs):
        raise AssertionError("health must not call upstreams")

    monkeypatch.setattr(ldap_auth, "authenticate", blow_up)
    monkeypatch.setattr(group_check, "assert_member", blow_up)

    assert client.get("/health").status_code == 200
