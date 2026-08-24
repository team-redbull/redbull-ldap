"""Group-membership lookup against the internal AD API."""

import logging

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util.retry import Retry

from app.config import get_settings
from app.errors import NotInGroup, UpstreamUnavailable

logger = logging.getLogger(__name__)

_session: requests.Session | None = None


def get_session() -> requests.Session:
    """Return the shared HTTP session, creating it on first use.

    One session keeps the TLS connection to the AD API alive across
    requests instead of renegotiating on every authentication.
    """
    global _session
    if _session is None:
        settings = get_settings()
        session = requests.Session()
        # The lookup is a GET and therefore safe to retry; a transient blip
        # in the AD API should not surface as a 502 to callers.
        retry = Retry(
            total=settings.ad_api_retries,
            backoff_factor=0.2,
            status_forcelist=(502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        session.mount("http://", HTTPAdapter(max_retries=retry))
        _session = session
    return _session


def assert_member(username: str, group: str) -> None:
    """Check that ``username`` belongs to ``group``.

    Returns ``None`` when the user is a member.

    Raises:
        NotInGroup: the AD API reported the user is not a member.
        UpstreamUnavailable: the AD API could not be reached or answered
            with something unusable.
    """
    settings = get_settings()

    try:
        response = get_session().get(
            settings.ad_api_url,
            params={
                "userSamAccountName": username,
                "groupSamAccountName": group,
            },
            headers={
                "accept": "application/json",
                "ClientId": settings.ad_api_client_id.get_secret_value(),
            },
            verify=settings.ad_api_verify_ssl,
            timeout=settings.ad_api_timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except RequestException as exc:
        logger.exception("AD API request failed for user %s: %s", username, exc)
        raise UpstreamUnavailable("AD API") from exc
    except ValueError as exc:
        # raise_for_status() passed but the body was not JSON.
        logger.exception("AD API returned a non-JSON body for user %s", username)
        raise UpstreamUnavailable("AD API") from exc

    if not isinstance(payload, bool):
        # The endpoint is documented to return a bare JSON boolean. Anything
        # else means the contract changed; fail closed as "unknown" rather
        # than coercing a surprise payload into a deny (or, worse, an allow).
        logger.error(
            "AD API returned an unexpected payload type %s for user %s",
            type(payload).__name__,
            username,
        )
        raise UpstreamUnavailable("AD API")

    if not payload:
        logger.info("User %s is not a member of group %s", username, group)
        raise NotInGroup(username, group)
