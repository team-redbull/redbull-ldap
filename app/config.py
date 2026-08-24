"""Application settings, loaded from the environment.

All connection details are required: this service talks to internal
infrastructure, so there are deliberately no defaults to fall back on. A
missing variable fails at startup instead of silently pointing somewhere
unexpected.
"""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LDAP. Prefer ldaps:// -- a plain ldap:// bind sends the password in
    # cleartext over the wire.
    ldap_server: str
    ldap_domain: str
    ldap_connect_timeout: int = Field(default=5, ge=1)
    ldap_receive_timeout: int = Field(default=10, ge=1)

    # Group-membership API.
    ad_api_url: str
    ad_api_client_id: SecretStr
    ad_api_verify_ssl: bool = True
    ad_api_timeout: float = Field(default=10.0, gt=0)
    ad_api_retries: int = Field(default=2, ge=0)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, built once on first use.

    Cached so that importing a module does not read the environment; tests
    can call ``get_settings.cache_clear()`` after changing it.
    """
    return Settings()
