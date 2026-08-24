"""Unit tests for the LDAP bind, with ldap3 mocked out."""

import pytest
from ldap3.core.exceptions import (
    LDAPBindError,
    LDAPPasswordIsMandatoryError,
    LDAPSocketOpenError,
)

from app import ldap_auth
from app.errors import InvalidCredentials, UpstreamUnavailable


@pytest.fixture(autouse=True)
def fake_server(monkeypatch):
    monkeypatch.setattr(ldap_auth, "Server", lambda *args, **kwargs: object())


class FakeConnection:
    """Records that unbind() was called so we can assert we do not leak."""

    def __init__(self, *args, **kwargs):
        self.unbound = False
        FakeConnection.last = self

    def unbind(self):
        self.unbound = True


def test_valid_credentials_bind_and_unbind(monkeypatch):
    monkeypatch.setattr(ldap_auth, "Connection", FakeConnection)

    assert ldap_auth.authenticate("jdoe", "s3cret") is None
    assert FakeConnection.last.unbound is True


def test_username_is_qualified_with_the_domain(monkeypatch):
    seen = {}

    def capture(server, **kwargs):
        seen.update(kwargs)
        return FakeConnection()

    monkeypatch.setattr(ldap_auth, "Connection", capture)
    ldap_auth.authenticate("jdoe", "s3cret")

    assert seen["user"] == "TESTDOMAIN\\jdoe"
    assert seen["read_only"] is True
    # A bind with no timeout can hang a worker thread indefinitely.
    assert seen["receive_timeout"] > 0


@pytest.mark.parametrize(
    "error", [LDAPBindError("bad creds"), LDAPPasswordIsMandatoryError("empty")]
)
def test_rejected_bind_is_invalid_credentials(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(ldap_auth, "Connection", fail)

    with pytest.raises(InvalidCredentials):
        ldap_auth.authenticate("jdoe", "wrong")


@pytest.mark.parametrize(
    "error", [LDAPSocketOpenError("refused"), RuntimeError("something odd")]
)
def test_infrastructure_failure_is_upstream_unavailable(monkeypatch, error):
    """An unreachable directory is not a wrong password."""

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(ldap_auth, "Connection", fail)

    with pytest.raises(UpstreamUnavailable):
        ldap_auth.authenticate("jdoe", "s3cret")


def test_empty_password_never_reaches_ldap(monkeypatch):
    """Defence in depth behind the schema's min_length=1."""

    def fail(*args, **kwargs):
        raise AssertionError("must not attempt a bind with an empty password")

    monkeypatch.setattr(ldap_auth, "Connection", fail)

    with pytest.raises(InvalidCredentials):
        ldap_auth.authenticate("jdoe", "")


def test_unbind_failure_does_not_break_a_successful_auth(monkeypatch):
    class RudeConnection(FakeConnection):
        def unbind(self):
            raise RuntimeError("connection reset during unbind")

    monkeypatch.setattr(ldap_auth, "Connection", RudeConnection)

    assert ldap_auth.authenticate("jdoe", "s3cret") is None
