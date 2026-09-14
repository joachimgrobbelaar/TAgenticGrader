"""Playwright SpeedGrader browser navigation and DOM interaction engine.

Provides automated headless browsing, SpeedGrader URL resolution,
iframe handling, student advancement, and UI-level grading inputs.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from config import (
    BASE_URL,
    COURSE_ID,
    DEFAULT_STORAGE_STATE_PATH,
    HEADLESS,
    SELECTORS,
    get_speedgrader_url,
)
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from src.auth.session import CanvasSession, load_canvas_session

logger = logging.getLogger(__name__)


class SpeedGraderNavigator:
    """Automates Playwright browser navigation through Canvas SpeedGrader."""

    def __init__(
        self,
        session: CanvasSession | None = None,
        storage_state_path: str | None = None,
        headless: bool | None = None,
        slow_mo: float | None = None,
        base_url: str | None = None,
        course_id: int = COURSE_ID,
    ) -> None:
        self.session = session
        self.storage_state_path = storage_state_path or (
            session.storage_state_path if session else DEFAULT_STORAGE_STATE_PATH
        )
        self.headless = HEADLESS if headless is None else headless
        self.slow_mo = slow_mo if slow_mo is not None else (100.0 if not self.headless else 0.0)
        self.base_url = (base_url or (session.base_url if session else BASE_URL)).rstrip("/")
        self.course_id = course_id

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def page(self) -> Page:
        """Return the active Playwright page, starting browser if not already running."""
        if self._page is None or self._page.is_closed():
            self.start()
        return self._page

    def start(self) -> Page:
        """Launch Chromium browser with authenticated storage state."""
        if self._playwright is None:
            self._playwright = sync_playwright().start()

        if self._browser is None:
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
            )

        # Ensure valid storage_state exists
        state_file = Path(self.storage_state_path)
        if not state_file.is_file():
            if self.session:
                self.session.save_storage_state(self.storage_state_path)
            else:
                loaded = load_canvas_session(
                    storage_state_path=self.storage_state_path,
                    fallback_to_mock=True,
                )
                self.session = loaded

        self._context = self._browser.new_context(
            storage_state=str(state_file) if state_file.is_file() else None,
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )

        self._page = self._context.new_page()
        self._page.set_default_timeout(20000)
        return self._page

    def close(self) -> None:
        """Gracefully terminate Playwright browser session."""
        try:
            if self._page and not self._page.is_closed():
                self._page.close()
        except Exception:
            pass
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

    def __enter__(self) -> SpeedGraderNavigator:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def navigate_to_assignment(
        self,
        assignment_id: int,
        student_id: int | None = None,
        timeout: int = 30000,
        wait_until: str = "networkidle",
    ) -> str:
        """Load SpeedGrader page for the specified assignment and optional student."""
        url = get_speedgrader_url(
            course_id=self.course_id,
            assignment_id=assignment_id,
            student_id=student_id,
            base_url=self.base_url,
        )
        logger.info("Navigating to SpeedGrader: %s", url)

        page = self.page
        page.goto(url, timeout=timeout, wait_until=wait_until)

        # Check for authentication redirection
        current_url = page.url
        if "/login" in current_url:
            raise RuntimeError(
                f"Canvas authentication required; redirected to login page: {current_url}"
            )

        self.wait_for_speedgrader_ready()
        return page.url

    def wait_for_speedgrader_ready(self, timeout_ms: int = 15000) -> bool:
        """Wait for key SpeedGrader elements to be visible or attached."""
        page = self.page
        start_time = time.time()
        timeout_s = timeout_ms / 1000.0

        selectors_to_check = [
            'input[data-testid="grade-input"]',
            "#grading-box-extended",
            'iframe[name="submission-preview-iframe"]',
            "#speedgrader_iframe",
            'button[data-testid="next-student-button"]',
            "#next-student-button",
            'span[data-testid="selected-student"]',
        ]

        while time.time() - start_time < timeout_s:
            for selector in selectors_to_check:
                try:
                    locator = page.locator(selector).first
                    if locator.count() > 0 and locator.is_visible():
                        return True
                except Exception:
                    continue
            page.wait_for_timeout(250)

        # Even if specific selectors didn't turn visible, check if page title indicates SpeedGrader
        if "SpeedGrader" in (page.title() or ""):
            return True

        logger.warning("SpeedGrader readiness timed out after %d ms", timeout_ms)
        return False

    def get_current_student_info(self) -> dict[str, str | None]:
        """Extract active student display name, index indicator, and graded count."""
        page = self.page

        # Student Name
        student_name = None
        for sel in ('span[data-testid="selected-student"]', "#students_selectmenu-button"):
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    student_name = loc.inner_text().strip()
                    if student_name:
                        break
            except Exception:
                continue

        # Current Student Index (e.g. "28/113")
        current_index = None
        try:
            loc = page.locator('span[data-testid="current-student-index"]').first
            if loc.count() > 0:
                current_index = loc.inner_text().strip()
        except Exception:
            pass

        # Graded Students Count (e.g. "23/113")
        graded_count = None
        try:
            loc = page.locator('span[data-testid="graded-students-count"]').first
            if loc.count() > 0:
                graded_count = loc.inner_text().strip()
        except Exception:
            pass

        return {
            "student_name": student_name,
            "student_index": current_index,
            "graded_count": graded_count,
            "current_url": page.url,
        }

    def next_student(self, timeout_ms: int = 10000) -> bool:
        """Advance SpeedGrader view to next student."""
        page = self.page
        initial_url = page.url

        next_btn = page.locator(SELECTORS.NEXT_STUDENT_BUTTON).first
        if next_btn.count() == 0 or not next_btn.is_enabled():
            logger.warning("Next student button not available or disabled.")
            return False

        next_btn.click()
        # Wait for URL or active student to change
        start = time.time()
        timeout_s = timeout_ms / 1000.0
        while time.time() - start < timeout_s:
            if page.url != initial_url:
                page.wait_for_timeout(500)
                return True
            page.wait_for_timeout(200)

        return True

    def prev_student(self, timeout_ms: int = 10000) -> bool:
        """Retreat SpeedGrader view to previous student."""
        page = self.page
        initial_url = page.url

        prev_btn = page.locator(SELECTORS.PREV_STUDENT_BUTTON).first
        if prev_btn.count() == 0 or not prev_btn.is_enabled():
            logger.warning("Prev student button not available or disabled.")
            return False

        prev_btn.click()
        start = time.time()
        timeout_s = timeout_ms / 1000.0
        while time.time() - start < timeout_s:
            if page.url != initial_url:
                page.wait_for_timeout(500)
                return True
            page.wait_for_timeout(200)

        return True

    def enter_grade(self, score: float, press_enter: bool = True) -> bool:
        """Fill numeric grade into the SpeedGrader grade input field."""
        page = self.page
        grade_input = page.locator(SELECTORS.GRADE_INPUT).first
        if grade_input.count() == 0:
            logger.error("Grade input element not found in DOM.")
            return False

        grade_input.fill(str(score))
        if press_enter:
            grade_input.press("Enter")
        else:
            grade_input.blur()
        page.wait_for_timeout(500)
        return True

    def enter_comment(self, comment_text: str) -> bool:
        """Inject feedback comment into the SpeedGrader TinyMCE RCE iframe or textarea."""
        page = self.page

        # Strategy A: TinyMCE iframe
        try:
            rce_frame = page.frame_locator('iframe[id$="_ifr"]').first
            tinymce = rce_frame.locator("body#tinymce").first
            if tinymce.count() > 0:
                tinymce.fill(comment_text)
                return True
        except Exception as exc:
            logger.debug("TinyMCE iframe fill attempt skipped: %s", exc)

        # Strategy B: Fallback textarea
        try:
            comment_ta = page.locator(SELECTORS.COMMENT_TEXTAREA).first
            if comment_ta.count() > 0:
                comment_ta.fill(comment_text)
                return True
        except Exception as exc:
            logger.debug("Textarea comment fill attempt skipped: %s", exc)

        logger.warning("Could not find suitable comment input element.")
        return False

    def submit_comment(self) -> bool:
        """Click the submit comment button."""
        page = self.page
        btn = page.locator(SELECTORS.COMMENT_SUBMIT_BUTTON).first
        if btn.count() == 0:
            logger.error("Submit comment button not found.")
            return False

        btn.click()
        page.wait_for_timeout(800)
        return True

    def take_screenshot(
        self,
        output_path: str | Path,
        full_page: bool = False,
    ) -> str:
        """Capture screenshot of current SpeedGrader view for audit trails."""
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(out_file), full_page=full_page)
        return str(out_file)
