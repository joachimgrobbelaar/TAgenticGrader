"""Canvas LMS REST API client.

Handles authenticated API queries, pagination, rate limiting,
retry backoff, student submission retrieval, and grade/comment posting.
"""

from __future__ import annotations

import logging
import time
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from config import BASE_URL, COURSE_ID

from src.auth.session import CanvasSession, load_canvas_session

logger = logging.getLogger(__name__)


class CanvasAPIError(Exception):
    """Raised when a Canvas REST API call fails."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class CanvasAPIClient:
    """Synchronous REST client for Canvas LMS endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        session: CanvasSession | None = None,
        session_cookie: str | None = None,
        csrf_token: str | None = None,
        rate_limit_delay: float = 0.2,
        max_retries: int = 3,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = (base_url or BASE_URL).rstrip("/")
        self.session = session
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.timeout = timeout
        self._last_request_time: float = 0.0

        # Initialize underlying requests session
        self._http = requests.Session()
        self._http.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) UlwaziGradingAgent/1.0",
                "Accept": "application/json",
            }
        )

        # Configure authentication state
        parsed_url = urllib.parse.urlparse(self.base_url)
        target_domain = parsed_url.hostname or "ulwazi.wits.ac.za"

        if self.session:
            self._http.cookies = self.session.to_requests_cookiejar(target_domain=target_domain)
            self._csrf_token = self.session.get_csrf_token()
        else:
            self._csrf_token = csrf_token or ""
            if session_cookie:
                self._http.cookies.set(
                    "canvas_session", session_cookie, domain=target_domain, path="/"
                )
            if self._csrf_token:
                self._http.cookies.set(
                    "_csrf_token", self._csrf_token, domain=target_domain, path="/"
                )

    @classmethod
    def from_saved_session(
        cls,
        firefox_profile_path: str | None = None,
        base_url: str | None = None,
        fallback_to_mock: bool = False,
    ) -> CanvasAPIClient:
        """Instantiate client by loading Canvas session from Firefox or storage state."""
        session = load_canvas_session(
            firefox_profile_path=firefox_profile_path,
            base_url=base_url,
            fallback_to_mock=fallback_to_mock,
        )
        return cls(base_url=base_url or session.base_url, session=session)

    def _throttle(self) -> None:
        """Enforce minimum delay between outgoing requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: Any | None = None,
        json_data: Any | None = None,
        headers: dict[str, str] | None = None,
        stream: bool = False,
    ) -> requests.Response:
        """Execute HTTP request with throttling, retry handling, and CSRF injection."""
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"

        req_headers = dict(headers or {})
        if method.upper() in ("POST", "PUT", "DELETE", "PATCH"):
            csrf = self._csrf_token
            if not csrf and self.session:
                csrf = self.session.get_csrf_token()
            if csrf:
                req_headers["X-CSRF-Token"] = csrf

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                resp = self._http.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=req_headers,
                    stream=stream,
                    timeout=self.timeout,
                )

                # Check Canvas rate limiting header
                remaining = resp.headers.get("X-Rate-Limit-Remaining")
                if remaining is not None:
                    try:
                        if float(remaining) < 5.0:
                            logger.warning(
                                "Canvas rate limit low (%s remaining), sleeping 1.0s", remaining
                            )
                            time.sleep(1.0)
                    except ValueError:
                        pass

                # Retry on rate limit 429 or server errors
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    sleep_time = (2 ** (attempt - 1)) * 0.5
                    logger.warning(
                        "Canvas API returned %s; retrying attempt %d/%d after %.1fs",
                        resp.status_code,
                        attempt,
                        self.max_retries,
                        sleep_time,
                    )
                    time.sleep(sleep_time)
                    continue

                if not resp.ok:
                    raise CanvasAPIError(
                        f"Canvas API request {method.upper()} {url} "
                        f"failed with status {resp.status_code}",
                        status_code=resp.status_code,
                        response_body=resp.text,
                    )

                return resp

            except (requests.RequestException, CanvasAPIError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    sleep_time = (2 ** (attempt - 1)) * 0.5
                    logger.warning(
                        "Canvas API request failed (%s); retrying attempt %d/%d after %.1fs",
                        exc,
                        attempt,
                        self.max_retries,
                        sleep_time,
                    )
                    time.sleep(sleep_time)
                else:
                    break

        if isinstance(last_exc, CanvasAPIError):
            raise last_exc
        raise CanvasAPIError(
            f"Canvas API request {method.upper()} {url} "
            f"failed after {self.max_retries} attempts: {last_exc}"
        ) from last_exc

    def _paginate(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Paginate through multi-page Canvas endpoints following Link headers."""
        items: list[dict[str, Any]] = []
        next_url: str | None = endpoint
        current_params = dict(params or {})
        if "per_page" not in current_params:
            current_params["per_page"] = 100

        while next_url:
            resp = self._request("GET", next_url, params=current_params)
            data = resp.json()
            if isinstance(data, list):
                items.extend(data)
            else:
                items.append(data)

            # Canvas Link header pagination: <...>; rel="next"
            next_url = None
            current_params = None  # Params are already encoded in next link
            if "next" in resp.links:
                next_url = resp.links["next"]["url"]

        return items

    # ==========================================================================
    # API Resource Endpoints
    # ==========================================================================
    def get_current_user(self) -> dict[str, Any]:
        """Fetch authenticated user profile via GET /api/v1/users/self."""
        resp = self._request("GET", "/api/v1/users/self")
        return resp.json()

    def get_user(self, user_id: int) -> dict[str, Any]:
        """Fetch user profile by user ID via GET /api/v1/users/{user_id}."""
        resp = self._request("GET", f"/api/v1/users/{user_id}")
        return resp.json()

    def get_group(self, group_id: int) -> dict[str, Any]:
        """Fetch group details via GET /api/v1/groups/{group_id}."""
        resp = self._request("GET", f"/api/v1/groups/{group_id}")
        return resp.json()

    def get_group_users(
        self,
        group_id: int,
        course_id: int | None = None,
        include_all_pages: bool = True,
    ) -> list[dict[str, Any]]:
        """Fetch student members of a group.

        Queries /api/v1/groups/{group_id}/users (standard Canvas LMS)
        with fallback to /api/v1/courses/{course_id}/groups/{group_id}/users.
        """
        cid = course_id or COURSE_ID
        endpoint = f"/api/v1/groups/{group_id}/users"
        try:
            if include_all_pages:
                return self._paginate(endpoint, params={"per_page": 100})
            resp = self._request("GET", endpoint, params={"per_page": 100})
            return resp.json()
        except CanvasAPIError as exc:
            if exc.status_code == 404:
                alt_endpoint = f"/api/v1/courses/{cid}/groups/{group_id}/users"
                if include_all_pages:
                    return self._paginate(alt_endpoint, params={"per_page": 100})
                resp = self._request("GET", alt_endpoint, params={"per_page": 100})
                return resp.json()
            raise

    def get_assignment(self, course_id: int, assignment_id: int) -> dict[str, Any]:
        """Fetch assignment details via GET /api/v1/courses/{course_id}/assignments/{id}."""
        resp = self._request("GET", f"/api/v1/courses/{course_id}/assignments/{assignment_id}")
        return resp.json()

    def get_assignment_submission(
        self,
        course_id: int,
        assignment_id: int,
        user_id: int,
    ) -> dict[str, Any]:
        """Fetch single student submission with comments and user metadata."""
        endpoint = f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{user_id}"
        params = {
            "include[]": ["submission_comments", "user"],
        }
        resp = self._request("GET", endpoint, params=params)
        return resp.json()

    def get_assignment_submissions(
        self,
        course_id: int,
        assignment_id: int,
        include_all_pages: bool = True,
    ) -> list[dict[str, Any]]:
        """Fetch all submissions for an assignment."""
        endpoint = f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
        params = {
            "include[]": ["submission_comments", "user"],
            "per_page": 100,
        }
        if include_all_pages:
            return self._paginate(endpoint, params=params)
        resp = self._request("GET", endpoint, params=params)
        return resp.json()

    def submit_grade_and_comment(
        self,
        course_id: int,
        assignment_id: int,
        user_id: int,
        score: float,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Post a numeric score and optional feedback comment via PUT /submissions/{user_id}."""
        endpoint = f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{user_id}"
        form_data: dict[str, str] = {
            "submission[posted_grade]": str(score),
        }
        if comment:
            form_data["comment[text_comment]"] = comment

        resp = self._request("PUT", endpoint, data=form_data)
        return resp.json()

    def download_attachment(
        self,
        url: str,
        dest_path: str | Path | None = None,
    ) -> bytes:
        """Download binary attachment content with authentication headers."""
        resp = self._request("GET", url, stream=True)
        content = resp.content
        if dest_path:
            out_file = Path(dest_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_bytes(content)
        return content

    def delete_submission_comment(
        self,
        course_id: int,
        assignment_id: int,
        user_id: int,
        comment_id: int,
    ) -> bool:
        """Delete a single submission comment by ID."""
        endpoint = (
            f"/api/v1/courses/{course_id}/assignments/{assignment_id}"
            f"/submissions/{user_id}/comments/{comment_id}"
        )
        try:
            self._request("DELETE", endpoint)
            return True
        except Exception as exc:
            logger.warning("Failed to delete comment %d: %s", comment_id, exc)
            return False

    def delete_all_submission_comments(
        self,
        course_id: int,
        assignment_id: int,
        user_id: int,
        author_id: int | None = None,
    ) -> int:
        """Delete all submission comments for a student, optionally filtering by author."""
        sub = self.get_assignment_submission(course_id, assignment_id, user_id)
        comments = sub.get("submission_comments", [])
        deleted = 0
        for c in comments:
            cid = c.get("id")
            if not cid:
                continue
            if author_id and c.get("author_id") != author_id:
                continue
            if self.delete_submission_comment(course_id, assignment_id, user_id, cid):
                deleted += 1
        return deleted

