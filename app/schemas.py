"""Request and response models for the public API."""

from typing import Optional

from pydantic import BaseModel, Field, SecretStr

from app.errors import ErrorCode


class AuthRequest(BaseModel):
    username: str = Field(min_length=1, max_length=256)
    # SecretStr keeps the password out of tracebacks, log lines and any
    # accidental model repr. min_length=1 blocks the empty password that can
    # otherwise turn an LDAP simple bind into an anonymous one.
    password: SecretStr = Field(min_length=1, max_length=1024)
    group: str = Field(min_length=1, max_length=256)


class AuthResponse(BaseModel):
    """Returned with HTTP 200 whenever a decision was reached.

    ``error_code``/``error`` are omitted on success
    (``response_model_exclude_none``).
    """

    authenticated: bool
    error_code: Optional[ErrorCode] = None
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    """Returned when no decision could be reached (HTTP 502).

    Note the absence of an ``authenticated`` field: a caller that reads it
    without checking the status code gets a KeyError rather than silently
    treating an outage as a denial.
    """

    error_code: ErrorCode
    error: str
