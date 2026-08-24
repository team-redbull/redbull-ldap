"""Test fixtures.

Everything here mocks the two upstreams: there is no LDAP server or AD API
in CI, and the whole point of the tests is to pin the response contract, not
to exercise the network.
"""

import os

import pytest

# Settings are required and have no defaults, so they must exist before
# app.config is first imported.
os.environ.setdefault("LDAP_SERVER", "ldaps://ldap.test.invalid")
os.environ.setdefault("LDAP_DOMAIN", "TESTDOMAIN")
os.environ.setdefault("AD_API_URL", "https://ad-api.test.invalid/isUserMemberOfSecurityGroup")
os.environ.setdefault("AD_API_CLIENT_ID", "test-client-id")

from fastapi.testclient import TestClient  # noqa: E402

from app import group_check, ldap_auth  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def ldap_ok(monkeypatch):
    """LDAP accepts any credentials."""
    monkeypatch.setattr(ldap_auth, "authenticate", lambda username, password: None)


@pytest.fixture
def group_ok(monkeypatch):
    """The AD API reports the user is a member."""
    monkeypatch.setattr(group_check, "assert_member", lambda username, group: None)


VALID_BODY = {"username": "jdoe", "password": "s3cret", "group": "api-users"}
