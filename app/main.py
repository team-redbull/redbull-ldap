"""RedBull LDAP Checker.

A policy decision endpoint: other services POST a username, password and
group, and get back whether that user may be let in.

The contract, in one place:

    200 {"authenticated": true}
    200 {"authenticated": false, "error_code": ..., "error": ...}
    502 {"error_code": "upstream_unavailable", "error": ...}
    422 <FastAPI validation error>   malformed request body

200 means a decision was reached. 502 means it was not, and the response
carries no ``authenticated`` field at all so that a caller which reads it
without checking the status fails loudly instead of locking the user out
because LDAP was briefly down.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import group_check, ldap_auth
from app.config import get_settings
from app.errors import AuthDecisionError, ErrorCode, UpstreamUnavailable
from app.schemas import AuthRequest, AuthResponse, ErrorResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Fail fast on a misconfigured deployment rather than on first request."""
    settings = get_settings()
    if settings.ldap_server.startswith("ldap://"):
        logger.warning(
            "LDAP_SERVER uses ldap:// - credentials are sent in cleartext. "
            "Use ldaps:// in any non-local environment."
        )
    if not settings.ad_api_verify_ssl:
        logger.warning("AD_API_VERIFY_SSL is disabled - TLS is not being verified.")
    yield


app = FastAPI(
    title="RedBull LDAP Checker",
    version="1.0.0",
    description=__doc__,
    lifespan=lifespan,
)


@app.exception_handler(AuthDecisionError)
def handle_auth_decision(_: Request, exc: AuthDecisionError) -> JSONResponse:
    """A denial is a successful decision, so it is a 200."""
    return JSONResponse(
        status_code=200,
        content=AuthResponse(
            authenticated=False,
            error_code=exc.error_code,
            error=exc.message,
        ).model_dump(mode="json"),
    )


@app.exception_handler(UpstreamUnavailable)
def handle_upstream_unavailable(_: Request, exc: UpstreamUnavailable) -> JSONResponse:
    """No decision could be made - tell the caller to retry, not to deny."""
    return JSONResponse(
        status_code=502,
        content=ErrorResponse(
            error_code=exc.error_code,
            error=exc.message,
        ).model_dump(mode="json"),
    )


@app.post(
    "/auth",
    response_model=AuthResponse,
    response_model_exclude_none=True,
    responses={502: {"model": ErrorResponse}},
    summary="Authenticate a user and check their group membership",
)
def auth(request: AuthRequest) -> AuthResponse:
    """Bind the credentials against LDAP, then check group membership.

    Defined with ``def`` rather than ``async def`` on purpose: ldap3 and
    requests are both blocking, so FastAPI runs this in its threadpool and
    the event loop stays free. Making it ``async`` would block every other
    request for the duration of the LDAP bind.
    """
    ldap_auth.authenticate(request.username, request.password.get_secret_value())
    group_check.assert_member(request.username, request.group)
    return AuthResponse(authenticated=True)


@app.get("/health", summary="Liveness probe")
def health() -> dict[str, str]:
    """Liveness only. Deliberately does not touch LDAP or the AD API, so an
    upstream outage does not get this instance killed by the orchestrator."""
    return {"status": "ok"}


__all__ = ["app", "ErrorCode"]
