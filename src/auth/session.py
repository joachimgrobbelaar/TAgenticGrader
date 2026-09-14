"""Canvas LMS authentication and session state management.

Provides live cookie extraction from Firefox browser profile,
Playwright storage_state.json generation, session validation via Canvas REST API,
and test-mock session synthesis.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from config import (
    BASE_URL,
    DEFAULT_STORAGE_STATE_PATH,
    TA_NAME,
    TA_USER_ID,
    find_firefox_cookies_path,
)

logger = logging.getLogger(__name__)

CANVAS_DOMAINS = (
    "ulwazi.wits.ac.za",
    "wits.ac.za",
    "canvas",
    "instructure",
    "canvas-user-content.com",
)


@dataclass
class CanvasSession:
    """Represents an active, authenticated Canvas LMS session."""

    cookies: list[dict[str, Any]]
    csrf_token: str
    storage_state_path: str
    user_id: int | None = None
    user_name: str | None = None
    base_url: str = BASE_URL

    def get_cookie_header(self) -> str:
        """Return HTTP Cookie header representation of session cookies."""
        return "; ".join(f"{c['name']}={c['value']}" for c in self.cookies)

    def to_requests_cookies(self) -> dict[str, str]:
        """Convert cookies list to a simple name-value dictionary for requests."""
        return {
            c["name"]: c["value"]
            for c in self.cookies
            if any(d in c.get("domain", "") for d in CANVAS_DOMAINS)
        }

    def to_requests_cookiejar(
        self, target_domain: str | None = None
    ) -> requests.cookies.RequestsCookieJar:
        """Convert cookies list to a RequestsCookieJar preserving domains and paths.

        If target_domain is specified (e.g. for mock server 127.0.0.1), sets cookies
        for that domain in addition to the original cookie domains.
        """
        jar = requests.cookies.RequestsCookieJar()
        for c in self.cookies:
            dom = c.get("domain", "")
            jar.set(
                name=c["name"],
                value=c["value"],
                domain=dom,
                path=c.get("path", "/"),
            )
            if (
                target_domain
                and target_domain in ("127.0.0.1", "localhost")
                and dom not in ("127.0.0.1", "localhost")
            ):
                jar.set(
                    name=c["name"],
                    value=c["value"],
                    domain=target_domain,
                    path=c.get("path", "/"),
                )
        return jar

    def to_playwright_storage_state(self, target_domain: str | None = None) -> dict[str, Any]:
        """Generate Playwright compatible storage_state payload."""
        normalized_cookies = []
        for c in self.cookies:
            exp = float(c.get("expires", -1.0)) if c.get("expires") is not None else -1.0
            while exp > 253402300799:
                exp /= 1000.0

            dom = str(c.get("domain", "ulwazi.wits.ac.za"))
            cookie_dict = {
                "name": str(c["name"]),
                "value": str(c["value"]),
                "domain": dom,
                "path": str(c.get("path", "/")),
                "expires": exp,
                "httpOnly": bool(c.get("httpOnly", False)),
                "secure": bool(c.get("secure", True)),
                "sameSite": c.get("sameSite", "None" if c.get("secure", True) else "Lax"),
            }
            normalized_cookies.append(cookie_dict)

            # If targeting a specific local mock domain (like localhost / 127.0.0.1)
            if (
                target_domain
                and target_domain in ("127.0.0.1", "localhost")
                and dom not in ("127.0.0.1", "localhost")
            ):
                alt_cookie = dict(cookie_dict)
                alt_cookie["domain"] = target_domain
                alt_cookie["secure"] = False
                alt_cookie["sameSite"] = "Lax"
                normalized_cookies.append(alt_cookie)

        return {"cookies": normalized_cookies, "origins": []}

    def save_storage_state(self, path: str | None = None, target_domain: str | None = None) -> str:
        """Serialize session state into Playwright storage_state.json format."""
        out_path = Path(path or self.storage_state_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        td = target_domain or urllib.parse.urlparse(self.base_url).hostname
        payload = self.to_playwright_storage_state(target_domain=td)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.storage_state_path = str(out_path)
        return self.storage_state_path

    def get_cookie_value(self, name: str) -> str | None:
        """Retrieve the value of a specific cookie by name."""
        for c in self.cookies:
            if c["name"] == name:
                return c["value"]
        return None

    def get_csrf_token(self) -> str:
        """Return the unquoted CSRF token for HTTP headers."""
        raw_token = self.csrf_token or self.get_cookie_value("_csrf_token") or ""
        return urllib.parse.unquote(raw_token)


def _normalize_expires(raw_expires: Any) -> float:
    """Normalize timestamp from seconds, milliseconds, or microseconds."""
    try:
        exp = float(raw_expires) if raw_expires is not None else -1.0
    except (ValueError, TypeError):
        return -1.0
    while exp > 253402300799:
        exp /= 1000.0
    return exp


def extract_cookies_from_firefox(
    cookie_file: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Extract Canvas authentication cookies from Firefox.

    Tries browser_cookie3 first, with fallback to direct sqlite3 querying.
    """
    db_path = Path(cookie_file) if cookie_file else find_firefox_cookies_path()
    extracted_cookies: list[dict[str, Any]] = []

    # Attempt 1: browser_cookie3 library
    try:
        import browser_cookie3

        cj = (
            browser_cookie3.firefox(cookie_file=str(db_path))
            if db_path
            else browser_cookie3.firefox()
        )
        for c in cj:
            if any(d in c.domain for d in CANVAS_DOMAINS):
                extracted_cookies.append(
                    {
                        "name": c.name,
                        "value": c.value,
                        "domain": c.domain,
                        "path": c.path,
                        "expires": _normalize_expires(c.expires),
                        "httpOnly": bool(
                            c._rest.get("httponly", False) or c._rest.get("HttpOnly", False)
                        ),
                        "secure": bool(c.secure),
                        "sameSite": "None" if c.secure else "Lax",
                    }
                )
    except Exception as exc:
        logger.warning("browser_cookie3 extraction failed (%s); trying direct sqlite", exc)

    # Attempt 2: Direct sqlite3 reading if browser_cookie3 returned nothing or failed
    if not extracted_cookies and db_path and db_path.is_file():
        try:
            with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=True) as tmp_db:
                # Copy file to avoid database lock from running browser
                shutil.copyfile(str(db_path), tmp_db.name)
                conn = sqlite3.connect(tmp_db.name)
                cur = conn.cursor()
                # Query moz_cookies for canvas/wits domains
                query = """
                SELECT name, value, host, path, expiry, isSecure, isHttpOnly, sameSite
                FROM moz_cookies
                WHERE host LIKE '%ulwazi%'
                   OR host LIKE '%wits.ac.za%'
                   OR host LIKE '%canvas%'
                   OR host LIKE '%instructure%'
                """
                cur.execute(query)
                rows = cur.fetchall()
                for row in rows:
                    name, value, host, path, expiry, is_secure, is_http_only, same_site = row
                    same_site_map = {0: "None", 1: "Lax", 2: "Strict"}
                    extracted_cookies.append(
                        {
                            "name": name,
                            "value": value,
                            "domain": host,
                            "path": path,
                            "expires": _normalize_expires(expiry),
                            "httpOnly": bool(is_http_only),
                            "secure": bool(is_secure),
                            "sameSite": same_site_map.get(
                                same_site, "None" if is_secure else "Lax"
                            ),
                        }
                    )
                conn.close()
        except Exception as exc:
            logger.error("Direct sqlite3 cookie extraction failed: %s", exc)

    return extracted_cookies


def validate_session(session: CanvasSession, base_url: str | None = None) -> bool:
    """Validate Canvas session by querying GET /api/v1/users/self."""
    url = f"{base_url or session.base_url}/api/v1/users/self"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) UlwaziGradingAgent/1.0",
        "Accept": "application/json",
    }
    try:
        req_session = requests.Session()
        req_session.cookies = session.to_requests_cookiejar()
        resp = req_session.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            session.user_id = data.get("id")
            session.user_name = data.get("name")
            logger.info(
                "Session validated for user %s (ID: %s)", session.user_name, session.user_id
            )
            return True
        logger.warning(
            "Session validation failed with HTTP status %s: %s", resp.status_code, resp.text
        )
        return False
    except Exception as exc:
        logger.warning("Session validation exception: %s", exc)
        return False


def create_mock_session(
    user_id: int = TA_USER_ID,
    user_name: str = TA_NAME,
    csrf_token: str = "mock_csrf_token_canvas_session_12345",
    storage_state_path: str | None = None,
    base_url: str = BASE_URL,
) -> CanvasSession:
    """Create a mock CanvasSession object for testing or offline environments."""
    mock_cookies = [
        {
            "name": "_csrf_token",
            "value": csrf_token,
            "domain": "ulwazi.wits.ac.za",
            "path": "/",
            "expires": 253402300700.0,
            "httpOnly": False,
            "secure": True,
            "sameSite": "None",
        },
        {
            "name": "canvas_session",
            "value": "mock_canvas_session_token_xyz987",
            "domain": "ulwazi.wits.ac.za",
            "path": "/",
            "expires": 253402300700.0,
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
        },
        {
            "name": "log_session_id",
            "value": "mock_log_session_id_456789",
            "domain": "ulwazi.wits.ac.za",
            "path": "/",
            "expires": 253402300700.0,
            "httpOnly": False,
            "secure": True,
            "sameSite": "None",
        },
    ]

    out_path = storage_state_path or DEFAULT_STORAGE_STATE_PATH
    session = CanvasSession(
        cookies=mock_cookies,
        csrf_token=csrf_token,
        storage_state_path=out_path,
        user_id=user_id,
        user_name=user_name,
        base_url=base_url,
    )
    session.save_storage_state()
    return session


def load_canvas_session(
    firefox_profile_path: str | None = None,
    storage_state_path: str | None = None,
    validate: bool = True,
    base_url: str | None = None,
    fallback_to_mock: bool = False,
) -> CanvasSession:
    """Load and return an authenticated CanvasSession.

    Conforms to interface:
        load_canvas_session(firefox_profile_path: str = None) -> CanvasSession
    """
    target_storage = storage_state_path or DEFAULT_STORAGE_STATE_PATH
    target_base = base_url or BASE_URL

    # Check for mock environment flag
    if os.environ.get("CANVAS_MOCK_SESSION") == "1":
        return create_mock_session(
            storage_state_path=target_storage,
            base_url=target_base,
        )

    # 1. Try loading from existing storage_state_path if valid
    if Path(target_storage).is_file():
        try:
            content = json.loads(Path(target_storage).read_text(encoding="utf-8"))
            cookies = content.get("cookies", [])
            csrf_token = ""
            for c in cookies:
                if c.get("name") == "_csrf_token":
                    csrf_token = c.get("value", "")
                    break

            if cookies:
                session = CanvasSession(
                    cookies=cookies,
                    csrf_token=csrf_token,
                    storage_state_path=target_storage,
                    base_url=target_base,
                )
                if not validate or validate_session(session, base_url=target_base):
                    return session
        except Exception as exc:
            logger.debug("Failed loading from existing storage state: %s", exc)

    # 2. Extract from Firefox
    cookie_db = Path(firefox_profile_path) if firefox_profile_path else find_firefox_cookies_path()
    cookies = extract_cookies_from_firefox(cookie_file=cookie_db)

    csrf_token = ""
    for c in cookies:
        if c.get("name") == "_csrf_token":
            csrf_token = c.get("value", "")
            break

    if cookies:
        session = CanvasSession(
            cookies=cookies,
            csrf_token=csrf_token,
            storage_state_path=target_storage,
            base_url=target_base,
        )
        session.save_storage_state()
        if validate:
            validate_session(session, base_url=target_base)
        return session

    # 3. Fallback to mock session if requested
    if fallback_to_mock:
        logger.warning("No live cookies found; generating mock Canvas session.")
        return create_mock_session(storage_state_path=target_storage, base_url=target_base)

    raise RuntimeError(
        "Could not load Canvas session: No active session cookies discovered in Firefox "
        f"at {cookie_db} and no valid {target_storage} file found."
    )
