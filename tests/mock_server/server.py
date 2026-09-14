"""
Canvas SpeedGrader Mock Server.
Implements Canvas LMS REST API endpoints and SpeedGrader HTML DOM interface.
"""

from datetime import datetime, timezone
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import re
import socketserver
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .data import ASSIGNMENTS, CURRENT_USER, FRI2_COHORT_DATA, JOACHIM_COHORT
from .fixtures import (
    REFERENCE_VPYTHON_CODE,
    create_exp05_pdf,
    create_exp06_pdf,
    create_lab3_part_a_html,
    create_lab3_part_b_html,
    create_websnappr_png,
)


class MockServerState:
    """Thread-safe state repository for submissions, files, and fault injections."""

    def __init__(self):
        self.lock = threading.Lock()
        self.submissions: Dict[Tuple[int, int], Dict[str, Any]] = {}
        self.file_storage: Dict[int, Tuple[bytes, str, str]] = {}  # file_id -> (bytes, content_type, filename)
        self.file_counter = 1000

        # Fault injection state
        self.rate_limit_active = False
        self.rate_limit_remaining = 100
        self.server_error_active = False
        self.unauthorized_active = False
        self.require_csrf = True
        self.latency_ms = 0

        self._initialize_fixtures()

    def reset(self):
        with self.lock:
            self.submissions.clear()
            self.file_storage.clear()
            self.file_counter = 1000
            self.rate_limit_active = False
            self.rate_limit_remaining = 100
            self.server_error_active = False
            self.unauthorized_active = False
            self.require_csrf = True
            self.latency_ms = 0
            self._initialize_fixtures()

    def store_file(self, content: bytes, content_type: str, filename: str) -> int:
        self.file_counter += 1
        fid = self.file_counter
        self.file_storage[fid] = (content, content_type, filename)
        return fid

    def _initialize_fixtures(self):
        # Generate initial files
        exp05_pdf = create_exp05_pdf()
        f_exp05 = self.store_file(exp05_pdf, "application/pdf", "Exp05_Report_Mbizane.pdf")

        exp06_pdf = create_exp06_pdf()
        f_exp06 = self.store_file(exp06_pdf, "application/pdf", "Exp06_Report_Mbizane.pdf")

        websnappr_png = create_websnappr_png()
        f_websnappr = self.store_file(websnappr_png, "image/png", "websnappr_final_code.png")

        # Initialize default submissions for Joachim's cohort (35 students)
        for student in JOACHIM_COHORT:
            uid = student["id"]

            # 316697: Exp05
            self.submissions[(316697, uid)] = {
                "id": 800000 + uid,
                "user_id": uid,
                "assignment_id": 316697,
                "workflow_state": "submitted",
                "score": None,
                "submission_type": "online_upload",
                "submitted_at": "2026-08-15T14:30:00Z",
                "late": False,
                "attempt": 1,
                "attachments": [
                    {
                        "id": f_exp05,
                        "display_name": "Exp05_Report_Mbizane.pdf",
                        "content_type": "application/pdf",
                        "size": len(exp05_pdf),
                        "url": f"/files/{f_exp05}/download",
                    }
                ],
                "submission_comments": [],
            }

            # 316844: Exp06
            self.submissions[(316844, uid)] = {
                "id": 810000 + uid,
                "user_id": uid,
                "assignment_id": 316844,
                "workflow_state": "submitted",
                "score": None,
                "submission_type": "online_upload",
                "submitted_at": "2026-08-20T10:00:00Z",
                "late": False,
                "attempt": 1,
                "attachments": [
                    {
                        "id": f_exp06,
                        "display_name": "Exp06_Report_Mbizane.pdf",
                        "content_type": "application/pdf",
                        "size": len(exp06_pdf),
                        "url": f"/files/{f_exp06}/download",
                    }
                ],
                "submission_comments": [],
            }

            # 315832: Lab 3 Part A
            self.submissions[(315832, uid)] = {
                "id": 820000 + uid,
                "user_id": uid,
                "assignment_id": 315832,
                "workflow_state": "submitted",
                "score": None,
                "submission_type": "online_text_entry",
                "submitted_at": "2026-08-25T11:15:00Z",
                "body": create_lab3_part_a_html(),
                "attachments": [],
                "submission_comments": [],
            }

            # 315833: Lab 3 Part B
            self.submissions[(315833, uid)] = {
                "id": 830000 + uid,
                "user_id": uid,
                "assignment_id": 315833,
                "workflow_state": "submitted",
                "score": None,
                "submission_type": "online_text_entry",
                "submitted_at": "2026-08-25T12:00:00Z",
                "body": create_lab3_part_b_html(),
                "attachments": [],
                "submission_comments": [],
            }

            # 315831: Lab 3 Final Code
            self.submissions[(315831, uid)] = {
                "id": 840000 + uid,
                "user_id": uid,
                "assignment_id": 315831,
                "workflow_state": "submitted",
                "score": None,
                "submission_type": "online_url",
                "url": "https://trinket.io/glowscript/sim_lab3",
                "submitted_at": "2026-08-25T12:30:00Z",
                "attachments": [
                    {
                        "id": f_websnappr,
                        "display_name": "websnappr_final_code.png",
                        "content_type": "image/png",
                        "size": len(websnappr_png),
                        "url": f"/files/{f_websnappr}/download",
                    }
                ],
                "submission_comments": [],
            }

        # Boundary fixtures:
        # Student 190138 (Dalitso Mpwesiwa, last student in cohort): late submission for Exp05
        if (316697, 190138) in self.submissions:
            self.submissions[(316697, 190138)]["late"] = True
            self.submissions[(316697, 190138)]["seconds_late"] = 3600

        # Student outside cohort (ID 150000): unsubmitted
        self.submissions[(316697, 150000)] = {
            "id": 900000,
            "user_id": 150000,
            "assignment_id": 316697,
            "workflow_state": "unsubmitted",
            "score": None,
            "submission_type": None,
            "attachments": [],
            "submission_comments": [],
        }


# Global state
mock_state = MockServerState()


class CanvasMockHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for Canvas REST API, SpeedGrader HTML UI, and attachments."""

    def log_message(self, format, *args):
        # Suppress noisy stdout logs during test execution
        pass

    def _send_json(self, data: Any, status: int = 200, headers: Optional[Dict[str, str]] = None):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, content: str, status: int = 200):
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _send_bytes(self, data: bytes, content_type: str, filename: Optional[str] = None):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _check_auth(self) -> bool:
        cookie_header = self.headers.get("Cookie", "")
        return "canvas_session=" in cookie_header or "Authorization" in self.headers

    def _check_csrf(self) -> bool:
        if not mock_state.require_csrf:
            return True
        csrf_header = self.headers.get("X-CSRF-Token", "")
        # Accept mock token or any valid non-empty csrf token
        return bool(csrf_header and csrf_header != "invalid_token")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-CSRF-Token, Authorization, Cookie")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Injected latency
        if mock_state.latency_ms > 0:
            time.sleep(mock_state.latency_ms / 1000.0)

        # Fault injections
        if mock_state.rate_limit_active:
            self._send_json(
                {"errors": [{"message": "Rate limit exceeded. Please throttle requests."}]},
                status=429,
                headers={"X-Rate-Limit-Remaining": "0"},
            )
            return

        if mock_state.server_error_active:
            self._send_json({"errors": [{"message": "Internal Server Error"}]}, status=500)
            return

        if mock_state.unauthorized_active:
            self._send_json({"errors": [{"message": "Unauthorized: Session expired or invalid."}]}, status=401)
            return

        # 1. Self User Profile
        if path == "/api/v1/users/self":
            self._send_json(CURRENT_USER)
            return

        # 2. Fri2 Cohort Users
        if path == "/api/v1/courses/86326/groups/144689/users":
            self._send_json(FRI2_COHORT_DATA)
            return

        # 3. List Course Assignments
        if path == "/api/v1/courses/86326/assignments":
            self._send_json(list(ASSIGNMENTS.values()))
            return

        # 4. Get Specific Assignment
        m_assign = re.match(r"^/api/v1/courses/86326/assignments/(\d+)$", path)
        if m_assign:
            aid = int(m_assign.group(1))
            if aid in ASSIGNMENTS:
                self._send_json(ASSIGNMENTS[aid])
            else:
                self._send_json({"errors": [{"message": "Assignment not found."}]}, status=404)
            return

        # 5. Get Student Submission
        m_sub = re.match(r"^/api/v1/courses/86326/assignments/(\d+)/submissions/(\d+)$", path)
        if m_sub:
            aid = int(m_sub.group(1))
            uid = int(m_sub.group(2))
            with mock_state.lock:
                key = (aid, uid)
                if key in mock_state.submissions:
                    sub_copy = dict(mock_state.submissions[key])
                    # Handle query inclusions
                    includes = query.get("include[]", [])
                    if "user" in includes:
                        student = next((s for s in FRI2_COHORT_DATA if s["id"] == uid), {"id": uid, "name": f"Student {uid}"})
                        sub_copy["user"] = student
                    self._send_json(sub_copy)
                else:
                    self._send_json({"errors": [{"message": "Submission not found."}]}, status=404)
            return

        # 6. File Download Endpoint
        m_file = re.match(r"^/files/(\d+)/download$", path)
        if m_file:
            fid = int(m_file.group(1))
            with mock_state.lock:
                if fid in mock_state.file_storage:
                    data, ctype, fname = mock_state.file_storage[fid]
                    self._send_bytes(data, ctype, fname)
                    return
            self._send_json({"errors": [{"message": "File not found."}]}, status=404)
            return

        # 7. SpeedGrader UI HTML Endpoint
        if path == "/courses/86326/gradebook/speed_grader":
            # Check auth: redirect if unauthenticated
            if not self._check_auth():
                self.send_response(302)
                self.send_header("Location", "/login/canvas")
                self.end_headers()
                return

            aid = int(query.get("assignment_id", [316697])[0])
            uid = int(query.get("student_id", [156944])[0])

            html_content = self._render_speedgrader_html(aid, uid)
            self._send_html(html_content)
            return

        # 8. SpeedGrader TinyMCE Iframe
        if path == "/courses/86326/gradebook/speed_grader/tinymce_frame":
            self._send_html(
                """<!DOCTYPE html>
<html>
<head><title>TinyMCE Frame</title></head>
<body id="tinymce" class="mce-content-body" contenteditable="true" style="font-family: sans-serif; padding: 8px;">
<p></p>
</body>
</html>"""
            )
            return

        # 9. SpeedGrader Document Preview Iframe
        if path == "/courses/86326/gradebook/speed_grader/preview_frame":
            aid = int(query.get("assignment_id", [316697])[0])
            uid = int(query.get("student_id", [156944])[0])
            with mock_state.lock:
                sub = mock_state.submissions.get((aid, uid), {})
                body = sub.get("body", "<p>Document Viewer</p>")
            self._send_html(
                f"""<!DOCTYPE html>
<html>
<head><title>Preview Frame</title></head>
<body>
<div id="preview-content">{body}</div>
</body>
</html>"""
            )
            return

        # 10. Login Page
        if path == "/login/canvas":
            self._send_html("<html><body><h1>Canvas Login</h1><form><input name='username'/></form></body></html>")
            return

        # 404 for unknown endpoints
        self._send_json({"errors": [{"message": "Not Found"}]}, status=404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Fault injections
        if mock_state.rate_limit_active:
            self._send_json({"errors": [{"message": "Rate limit exceeded."}]}, status=429)
            return

        if mock_state.server_error_active:
            self._send_json({"errors": [{"message": "Internal Server Error"}]}, status=500)
            return

        if mock_state.unauthorized_active or not self._check_auth():
            self._send_json({"errors": [{"message": "Unauthorized"}]}, status=401)
            return

        # CSRF check
        if not self._check_csrf():
            self._send_json({"errors": [{"message": "CSRF token invalid or missing."}]}, status=403)
            return

        # Read body
        content_len = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_len)

        # Parse form or JSON payload
        grade_val = None
        comment_val = None

        content_type = self.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                body_json = json.loads(post_data.decode("utf-8"))
                grade_val = body_json.get("submission", {}).get("posted_grade")
                comment_val = body_json.get("comment", {}).get("text_comment")
            except Exception:
                pass
        else:
            # application/x-www-form-urlencoded
            parsed_form = parse_qs(post_data.decode("utf-8"))
            if "submission[posted_grade]" in parsed_form:
                grade_val = parsed_form["submission[posted_grade]"][0]
            if "comment[text_comment]" in parsed_form:
                comment_val = parsed_form["comment[text_comment]"][0]

        # Route: PUT /api/v1/courses/86326/assignments/:aid/submissions/:uid
        m_sub = re.match(r"^/api/v1/courses/86326/assignments/(\d+)/submissions/(\d+)$", path)
        if m_sub:
            aid = int(m_sub.group(1))
            uid = int(m_sub.group(2))

            # Validate grade if provided
            parsed_score = None
            if grade_val is not None:
                try:
                    parsed_score = float(grade_val)
                    if parsed_score < 0:
                        self._send_json({"errors": [{"message": "Grade cannot be negative."}]}, status=400)
                        return
                    if aid in ASSIGNMENTS and parsed_score > ASSIGNMENTS[aid]["points_possible"]:
                        self._send_json(
                            {"errors": [{"message": f"Grade exceeds points possible ({ASSIGNMENTS[aid]['points_possible']})."}]},
                            status=400,
                        )
                        return
                except ValueError:
                    self._send_json({"errors": [{"message": "Invalid numeric grade format."}]}, status=400)
                    return

            with mock_state.lock:
                key = (aid, uid)
                if key not in mock_state.submissions:
                    self._send_json({"errors": [{"message": "Submission not found."}]}, status=404)
                    return

                sub = mock_state.submissions[key]
                if parsed_score is not None:
                    sub["score"] = parsed_score
                    sub["workflow_state"] = "graded"
                    sub["graded_at"] = datetime.now(timezone.utc).isoformat()

                if comment_val:
                    sub["submission_comments"].append(
                        {
                            "id": len(sub["submission_comments"]) + 1,
                            "author_id": CURRENT_USER["id"],
                            "author_name": CURRENT_USER["name"],
                            "comment": comment_val,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )

                self._send_json(sub)
                return

        self._send_json({"errors": [{"message": "Not Found"}]}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Utility management endpoints
        if path == "/mock/reset":
            mock_state.reset()
            self._send_json({"status": "reset_complete"})
            return

        if path == "/mock/fault":
            content_len = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_len)
            try:
                faults = json.loads(body_bytes.decode("utf-8"))
                with mock_state.lock:
                    if "rate_limit" in faults:
                        mock_state.rate_limit_active = bool(faults["rate_limit"])
                    if "server_error" in faults:
                        mock_state.server_error_active = bool(faults["server_error"])
                    if "unauthorized" in faults:
                        mock_state.unauthorized_active = bool(faults["unauthorized"])
                    if "require_csrf" in faults:
                        mock_state.require_csrf = bool(faults["require_csrf"])
                    if "latency_ms" in faults:
                        mock_state.latency_ms = int(faults["latency_ms"])
                self._send_json({"status": "fault_applied", "current_state": faults})
            except Exception as e:
                self._send_json({"error": str(e)}, status=400)
            return

        self._send_json({"errors": [{"message": "Not Found"}]}, status=404)

    def _render_speedgrader_html(self, aid: int, uid: int) -> str:
        """Renders realistic Canvas SpeedGrader HTML document conforming to DOM selectors."""
        student_name = "Unknown Student"
        student_idx = 28
        for s in FRI2_COHORT_DATA:
            if s["id"] == uid:
                student_name = s["name"]
                student_idx = s["index"]
                break

        with mock_state.lock:
            sub = mock_state.submissions.get((aid, uid), {})
            score_str = str(sub.get("score")) if sub.get("score") is not None else ""
            graded_count = sum(1 for s in mock_state.submissions.values() if s.get("score") is not None)
            total_students = len(FRI2_COHORT_DATA)
            attachments = sub.get("attachments", [])

        attach_buttons = "".join(
            f'<button id="submission-attachment-link-{a["id"]}" data-testid="submission-attachment-link-{a["id"]}">{html.escape(a["display_name"])}</button>'
            for a in attachments
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>SpeedGrader: Assignment {aid}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; display: flex; flex-direction: column; height: 100vh; }}
        header {{ display: flex; align-items: center; justify-content: space-between; padding: 10px 20px; background: #2D3B45; color: white; }}
        .nav-controls button {{ background: #008EE2; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; }}
        .main-container {{ display: flex; flex: 1; overflow: hidden; }}
        .submission-stage {{ flex: 1; border-right: 1px solid #ccc; display: flex; flex-direction: column; }}
        .grading-sidebar {{ width: 340px; padding: 16px; background: #f5f5f5; display: flex; flex-direction: column; gap: 12px; }}
        .grade-input {{ padding: 8px; font-size: 16px; width: 100px; }}
        .comment-iframe {{ width: 100%; height: 120px; border: 1px solid #ccc; background: white; }}
    </style>
</head>
<body>
    <header>
        <div class="nav-controls">
            <button id="prev-student-button" data-testid="previous-student-button" onclick="navigatePrev()">Prev Student</button>
            <span data-testid="selected-student" style="font-weight: bold; margin: 0 10px;">{html.escape(student_name)}</span>
            <button id="next-student-button" data-testid="next-student-button" onclick="navigateNext()">Next Student</button>
        </div>
        <div>
            <span data-testid="current-student-index">{student_idx + 1}/{total_students}</span>
            <span data-testid="graded-students-count" style="margin-left: 15px;">Graded: {graded_count}/{total_students}</span>
        </div>
    </header>

    <div class="main-container">
        <!-- Submission Viewport -->
        <div class="submission-stage">
            <div id="attachment-list" style="padding: 8px; background: #eee;">
                {attach_buttons}
            </div>
            <iframe name="submission-preview-iframe" src="/courses/86326/gradebook/speed_grader/preview_frame?assignment_id={aid}&student_id={uid}" style="flex: 1; border: none;"></iframe>
        </div>

        <!-- Right Grading Sidebar -->
        <div class="grading-sidebar">
            <h3>Assessment</h3>
            <div>
                <label for="TextInput___0">Grade out of 20:</label><br>
                <input data-testid="grade-input" type="text" id="TextInput___0" class="grade-input" value="{score_str}">
            </div>
            <div>
                <label>Status:</label><br>
                <input data-testid="assignment-submission-status-select" type="text" value="{sub.get('workflow_state', 'submitted')}">
            </div>
            <div>
                <label>Submission Comments:</label>
                <iframe id="rce-tinymce_ifr" name="rce-tinymce_ifr" class="comment-iframe" src="/courses/86326/gradebook/speed_grader/tinymce_frame"></iframe>
                <textarea data-testid="rce-textarea" id="rce-textarea" style="display:none;"></textarea>
            </div>
            <button id="comment_submit_button" data-testid="submit-comment-button" style="padding: 10px; background: #008EE2; color: white; border: none; border-radius: 4px; cursor: pointer;">
                Submit comment
            </button>
        </div>
    </div>

    <script>
        function navigateNext() {{
            const curIdx = {student_idx};
            const nextUid = {FRI2_COHORT_DATA[min(len(FRI2_COHORT_DATA)-1, student_idx+1)]["id"]};
            window.location.href = `/courses/86326/gradebook/speed_grader?assignment_id={aid}&student_id=${{nextUid}}`;
        }}
        function navigatePrev() {{
            const curIdx = {student_idx};
            const prevUid = {FRI2_COHORT_DATA[max(0, student_idx-1)]["id"]};
            window.location.href = `/courses/86326/gradebook/speed_grader?assignment_id={aid}&student_id=${{prevUid}}`;
        }}

        // Sync grade input Enter key to PUT API
        document.getElementById('TextInput___0').addEventListener('keydown', function(e) {{
            if (e.key === 'Enter') {{
                fetch('/api/v1/courses/86326/assignments/{aid}/submissions/{uid}', {{
                    method: 'PUT',
                    headers: {{ 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRF-Token': 'mock_token' }},
                    body: `submission[posted_grade]=${{this.value}}`
                }});
            }}
        }});

        // Sync comment submit
        document.getElementById('comment_submit_button').addEventListener('click', function() {{
            const frame = document.getElementById('rce-tinymce_ifr');
            const comment = frame.contentWindow.document.body.innerText;
            fetch('/api/v1/courses/86326/assignments/{aid}/submissions/{uid}', {{
                method: 'PUT',
                headers: {{ 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRF-Token': 'mock_token' }},
                body: `comment[text_comment]=${{encodeURIComponent(comment)}}`
            }});
        }});
    </script>
</body>
</html>"""


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class MockCanvasServer:
    """Manager for the threaded mock server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.port = port
        self.server: Optional[ThreadedHTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> str:
        self.server = ThreadedHTTPServer((self.host, self.port), CanvasMockHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.base_url

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None

    def reset(self):
        mock_state.reset()
