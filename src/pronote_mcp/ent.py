from __future__ import annotations

import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.cookies import RequestsCookieJar

logger = logging.getLogger(__name__)

PSN_URL = "https://psn.monlycee.net/"
DEFAULT_TIMEOUT = 15
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class ENTAuthError(RuntimeError):
    pass


def monlycee_ent(username: str, password: str, pronote_url: str, **_) -> RequestsCookieJar:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})

    try:
        r_initial = s.get(PSN_URL, allow_redirects=True, timeout=DEFAULT_TIMEOUT)
        if not r_initial.ok or "auth.monlycee.net" not in r_initial.url:
            raise ENTAuthError("Could not reach Monlycée login page.")

        soup = BeautifulSoup(r_initial.text, "html.parser")
        form = soup.find("form")
        if form is None:
            raise ENTAuthError("Login form not found on Monlycée page.")

        form_action_url = form.get("action")
        if not form_action_url:
            raise ENTAuthError("No action URL on Monlycée login form.")

        if not form_action_url.startswith("http"):
            form_action_url = urljoin(r_initial.url, form_action_url)

        form_data = {
            tag.get("name"): tag.get("value", "")
            for tag in form.find_all("input")
            if tag.get("name")
        }
        form_data["username"] = username
        form_data["password"] = password

        r_login = s.post(
            form_action_url,
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            allow_redirects=True,
            timeout=DEFAULT_TIMEOUT,
        )
        if not r_login.ok:
            raise ENTAuthError("Monlycée login rejected.")

        r_pronote = s.get(pronote_url, allow_redirects=True, timeout=DEFAULT_TIMEOUT)
        if not r_pronote.ok:
            raise ENTAuthError("Could not reach Pronote after ENT login.")

        logger.info("ENT authentication successful.")
        return s.cookies

    except requests.RequestException as e:
        logger.exception("Network error during ENT auth")
        raise ENTAuthError(f"Network error during ENT authentication: {type(e).__name__}") from None
