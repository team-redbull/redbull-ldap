"""Credential verification against LDAP / Active Directory."""

import logging

from ldap3 import NONE, Connection, Server
from ldap3.core.exceptions import (
    LDAPBindError,
    LDAPExceptionError,
    LDAPPasswordIsMandatoryError,
)

from app.config import get_settings
from app.errors import InvalidCredentials, UpstreamUnavailable

logger = logging.getLogger(__name__)


def authenticate(username: str, password: str) -> None:
    """Verify ``username``/``password`` with an LDAP simple bind.

    Returns ``None`` when the credentials are valid.

    Raises:
        InvalidCredentials: the bind was rejected.
        UpstreamUnavailable: LDAP could not be reached or failed.
    """
    # Defence in depth against the anonymous-bind hole: an empty password
    # makes a simple bind succeed as an unauthenticated session on many
    # directories. The schema already rejects this, so reaching here means a
    # caller bypassed it.
    if not password:
        logger.warning("Rejected bind attempt with an empty password")
        raise InvalidCredentials()

    settings = get_settings()
    server = Server(
        settings.ldap_server,
        get_info=NONE,
        connect_timeout=settings.ldap_connect_timeout,
    )

    conn = None
    try:
        conn = Connection(
            server,
            user=f"{settings.ldap_domain}\\{username}",
            password=password,
            auto_bind=True,
            read_only=True,
            receive_timeout=settings.ldap_receive_timeout,
        )
    except (LDAPBindError, LDAPPasswordIsMandatoryError):
        logger.info("LDAP bind rejected for user %s", username)
        raise InvalidCredentials() from None
    except LDAPExceptionError as exc:
        # Connection refused, TLS failure, timeout, referral problems...
        logger.exception("LDAP request failed for user %s: %s", username, exc)
        raise UpstreamUnavailable("LDAP") from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected LDAP failure for user %s", username)
        raise UpstreamUnavailable("LDAP") from exc
    finally:
        if conn is not None:
            try:
                conn.unbind()
            except Exception:  # noqa: BLE001 - cleanup must never mask the result
                logger.debug("Failed to unbind LDAP connection", exc_info=True)
