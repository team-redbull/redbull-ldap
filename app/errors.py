"""Domain errors.

The important distinction in this service is between *a decision was made*
and *no decision could be made*:

``AuthDecisionError``   the user was denied. That is a normal, successful
                        outcome of the endpoint and is reported as
                        HTTP 200 with ``authenticated: false``.

``UpstreamUnavailable`` LDAP or the AD API could not be reached, so we do
                        not know whether the user should be let in. Reported
                        as HTTP 502 so callers can retry instead of treating
                        an outage as a denial.
"""

from enum import Enum


class ErrorCode(str, Enum):
    """Stable, machine-readable reason codes for callers to branch on."""

    INVALID_CREDENTIALS = "invalid_credentials"
    NOT_IN_GROUP = "not_in_group"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"


class AuthDecisionError(Exception):
    """Base for outcomes where the user is knowingly denied access."""

    error_code: ErrorCode

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidCredentials(AuthDecisionError):
    """The username/password pair did not bind."""

    error_code = ErrorCode.INVALID_CREDENTIALS

    def __init__(self) -> None:
        # Deliberately does not say which of the two was wrong, and never
        # echoes the submitted username back.
        super().__init__("Invalid username or password")


class NotInGroup(AuthDecisionError):
    """Credentials were valid but the user is not a member of the group."""

    error_code = ErrorCode.NOT_IN_GROUP

    def __init__(self, username: str, group: str) -> None:
        super().__init__(f"User {username} is not a member of group {group}")


class UpstreamUnavailable(Exception):
    """A dependency failed, so no authentication decision could be made."""

    error_code = ErrorCode.UPSTREAM_UNAVAILABLE

    def __init__(self, dependency: str) -> None:
        # The message is returned to callers, so it names the dependency but
        # carries no exception detail (hostnames, stack traces, LDAP result
        # codes). The underlying error is logged server-side instead.
        super().__init__(f"{dependency} is unavailable, try again later")
        self.dependency = dependency
        self.message = f"{dependency} is unavailable, try again later"
