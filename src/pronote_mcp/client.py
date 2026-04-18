from __future__ import annotations

import logging
import os
import threading
import time

import pronotepy

from .ent import monlycee_ent

logger = logging.getLogger(__name__)

_CACHE_TTL = 20 * 60

_cached: tuple[pronotepy.Client, float] | None = None
_cache_lock = threading.Lock()


class PronoteConfigError(RuntimeError):
    pass


class PronoteAuthError(RuntimeError):
    pass


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise PronoteConfigError(
            f"Missing required environment variable: {name}. "
            f"Set it in your Claude Desktop config or .env file."
        )
    return val


def _login() -> pronotepy.Client:
    username = _require_env("MONLYCEE_USER")
    password = _require_env("MONLYCEE_PASS")
    pronote_url = _require_env("PRONOTE_URL")

    try:
        client = pronotepy.Client(
            pronote_url,
            username=username,
            password=password,
            ent=monlycee_ent,
        )
    except Exception as e:
        logger.exception("Pronote client init failed")
        raise PronoteAuthError(
            f"Failed to authenticate to Pronote ({type(e).__name__}). "
            f"Check ENT credentials and PRONOTE_URL."
        ) from None

    if not client.logged_in:
        raise PronoteAuthError("Pronote login completed but client is not logged in.")

    logger.info("Pronote login successful, client cached for %d min.", _CACHE_TTL // 60)
    return client


def get_client() -> pronotepy.Client:
    global _cached

    with _cache_lock:
        if _cached is not None:
            client, ts = _cached
            if time.monotonic() - ts < _CACHE_TTL:
                try:
                    client.session_check()
                    logger.info("Reusing cached Pronote session.")
                    return client
                except Exception:
                    logger.info("Cached session invalid, re-logging in.")
                    _cached = None

        client = _login()
        _cached = (client, time.monotonic())
        return client
