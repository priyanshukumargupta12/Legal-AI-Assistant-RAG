"""
app/elasticsearch/elastic_client.py
=====================================
Elasticsearch client factory.

PURPOSE:
    Provides a configured ``Elasticsearch`` (synchronous) client instance
    based on application settings.

AUTHENTICATION PRIORITY (from highest to lowest):
    1. API Key  — if ``elasticsearch_api_key`` is non-empty.
    2. HTTP Basic Auth — if ``elasticsearch_username`` and
       ``elasticsearch_password`` are both non-empty.
    3. No Authentication — for local development with security disabled.

DESIGN:
    - Returns a regular (synchronous) Elasticsearch client.
    - Uses the official ``elasticsearch-py`` v8 client.
    - SSL verification is enabled by default (secure for Elastic Cloud).
    - Retry on timeout is enabled for resilience.
    - Connection timeout is set to 30 s to handle cold-start latency.

SOLID: Single Responsibility — only constructs and returns the ES client.
"""

from __future__ import annotations

from elasticsearch import Elasticsearch

from app.core.config import Settings
from app.core.exceptions import KeywordStoreConnectionError
from app.elasticsearch.elastic_logger import elastic_log


def get_elasticsearch_client(settings: Settings) -> Elasticsearch:
    """
    Build and return a configured Elasticsearch client.

    Authentication strategy (checked in priority order):
        1. API key  (recommended for Elastic Cloud / production)
        2. Basic auth  (username + password)
        3. Anonymous  (local dev with security disabled)

    Args:
        settings: Application Settings instance.

    Returns:
        A connected ``Elasticsearch`` client ready for use.

    Raises:
        KeywordStoreConnectionError: If the client cannot be instantiated.
    """
    url = settings.elasticsearch_url
    api_key = settings.elasticsearch_api_key
    username = settings.elasticsearch_username
    password = settings.elasticsearch_password

    # ── Determine authentication mode ─────────────────────────────────────────
    if api_key:
        auth_mode = "api_key"
    elif username and password:
        auth_mode = "basic_auth"
    else:
        auth_mode = "anonymous"

    elastic_log.info(
        "Initialising Elasticsearch client | url={url} | auth={auth}",
        url=url,
        auth=auth_mode,
    )

    try:
        # ── Build common kwargs ────────────────────────────────────────────────
        client_kwargs: dict = {
            "hosts": [url],
            "request_timeout": 30,
            "retry_on_timeout": True,
            "max_retries": 3,
            # verify_certs=True is the default; keep it on for cloud deployments.
            # Set to False only for self-signed certs in local dev.
        }

        # ── Apply authentication ───────────────────────────────────────────────
        if auth_mode == "api_key":
            client_kwargs["api_key"] = api_key
        elif auth_mode == "basic_auth":
            client_kwargs["basic_auth"] = (username, password)

        client = Elasticsearch(**client_kwargs)

        elastic_log.info(
            "Elasticsearch client initialised | url={url} | auth={auth}",
            url=url,
            auth=auth_mode,
        )
        return client

    except Exception as exc:
        elastic_log.error(
            "Failed to initialise Elasticsearch client | url={url} | error={error}",
            url=url,
            error=str(exc),
        )
        raise KeywordStoreConnectionError(url=url) from exc
