"""Trinket / VPython simulation code extractor for Computer Lab 3.

Ingests source code strings, Python/text file attachments, online URL references,
and Canvas Websnappr PNG snapshots to extract and analyze GlowScript simulation code.
"""

from __future__ import annotations

import ast
import io
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .base import BaseExtractor, ExtractedCode, RawSubmission

logger = logging.getLogger(__name__)


class CodeExtractor(BaseExtractor):
    """Extractor for Computer Lab 3 Final Code submissions and snapshots."""

    def __init__(self) -> None:
        self._font = ImageFont.load_default()
        self._char_templates: dict[str, tuple[int, np.ndarray]] = {}
        self._init_char_templates()

    def _init_char_templates(self) -> None:
        """Pre-compute printable character templates for fast bitmap recognition."""
        for code in range(32, 127):
            ch = chr(code)
            w = round(self._font.getlength(ch))
            if w == 0:
                w = 5
            im = Image.new("L", (w, 15), color=0)
            d = ImageDraw.Draw(im)
            d.text((0, 0), ch, fill=255)
            self._char_templates[ch] = (w, np.array(im))

    def extract(
        self,
        submission: RawSubmission | str | bytes | Path,
        **kwargs: Any,
    ) -> ExtractedCode:
        """Extract and semantically analyze VPython code from submission.
        
        Args:
            submission: RawSubmission, raw code string, PNG image bytes, or Path.
        """
        source_code, source_type = self._resolve_code(submission)
        cleaned_code = self.clean_text(source_code).strip()

        extracted = self.analyze_code(cleaned_code)
        extracted.metadata["source_type"] = source_type

        if isinstance(submission, RawSubmission):
            extracted.metadata["user_id"] = submission.user_id
            extracted.metadata["assignment_id"] = submission.assignment_id
            extracted.metadata["submission_type"] = submission.submission_type

        if not cleaned_code:
            extracted.is_valid = False
            extracted.extraction_warnings.append("Code submission is empty or unreadable.")

        return extracted

    def _resolve_code(
        self, submission: RawSubmission | str | bytes | Path
    ) -> tuple[str, str]:
        """Resolve code string and format type from submission."""
        # 1. Check bytes (e.g. PNG snapshot or text file bytes)
        if isinstance(submission, bytes):
            if submission.startswith(b"\x89PNG\r\n\x1a\n"):
                code = self.extract_from_image(submission)
                return code, "websnappr_png"
            try:
                return submission.decode("utf-8"), "raw_text_bytes"
            except UnicodeDecodeError:
                return "", "binary_unknown"

        # 2. Check filesystem path
        if isinstance(submission, Path) or (
            isinstance(submission, str) and "\n" not in submission and len(submission) < 260
        ):
            try:
                p = Path(submission)
                if p.is_file():
                    if p.suffix.lower() == ".png":
                        return self.extract_from_image(p.read_bytes()), "websnappr_png_file"
                    return p.read_text(encoding="utf-8"), "code_file"
            except (OSError, ValueError):
                pass

        # 3. Check raw string
        if isinstance(submission, str):
            # If string contains typical python code keywords
            if "\n" in submission or "sphere" in submission or "def " in submission or "import " in submission:
                return submission, "raw_string"
            return submission, "text_input"

        # 4. Check RawSubmission
        if isinstance(submission, RawSubmission):
            # Check attachments for PNG snapshot or source files
            for attach in submission.attachments:
                # Check for image bytes or path
                if "bytes" in attach and isinstance(attach["bytes"], bytes):
                    data = attach["bytes"]
                    if data.startswith(b"\x89PNG\r\n\x1a\n"):
                        return self.extract_from_image(data), "websnappr_png_attachment"
                    try:
                        return data.decode("utf-8"), "text_attachment"
                    except UnicodeDecodeError:
                        pass
                if "local_path" in attach and Path(attach["local_path"]).is_file():
                    p = Path(attach["local_path"])
                    if p.suffix.lower() == ".png":
                        return self.extract_from_image(p.read_bytes()), "websnappr_png_attachment"
                    if p.suffix.lower() in [".py", ".txt", ".vpy"]:
                        return p.read_text(encoding="utf-8"), "code_attachment"

            # Check body_html
            if submission.body_html:
                clean = re.sub(r"<[^>]+>", "\n", submission.body_html)
                return clean.strip(), "body_html"

            # If only url is present
            if submission.url:
                return f"# Online URL submission: {submission.url}", "online_url"

        return "", "empty"

    def extract_from_image(self, png_bytes: bytes) -> str:
        """Perform bitmap glyph recognition on Websnappr PNG screenshot."""
        try:
            img = Image.open(io.BytesIO(png_bytes)).convert("L")
        except (OSError, ValueError) as exc:
            logger.warning("Failed to open PNG snapshot: %s", exc)
            return ""

        arr = np.array(img)
        lines: list[str] = []

        # Websnappr layout: header is ~80px, lines start at y=120, line pitch is 40px
        # Code column begins around x=120 (after 3-digit line number and pipe separator)
        start_y = 120
        y = start_y
        max_y = min(arr.shape[0] - 40, 2100)

        # Detect line start x by scanning for vertical divider pipe '|'
        pipe_x = 120
        header_crop = arr[110:150, 40:150]
        # Look for column with vertical line
        for test_x in range(60, 110):
            col = header_crop[:, test_x - 40]
            if (col > 80).sum() > 25:  # '|' character
                pipe_x = test_x + 15
                break

        while y < max_y:
            # Crop 15px high row for text
            crop = arr[y : y + 15, pipe_x : min(arr.shape[1], pipe_x + 1200)]
            # If line is completely uniform / background (no text)
            if crop.shape[1] < 20 or (crop.max() - crop.min()) < 30:
                lines.append("")
                y += 40
                continue

            # Normalize crop range from background (~30) and text (~240) to [0, 255]
            bg_val = float(crop.min())
            fg_val = max(bg_val + 50.0, float(crop.max()))
            crop_norm = np.clip(
                (crop.astype(float) - bg_val) / (fg_val - bg_val) * 255.0, 0, 255
            ).astype(np.uint8)

            decoded_line = self._decode_line(crop_norm)
            lines.append(decoded_line)
            y += 40

        # Strip trailing blank lines
        while lines and not lines[-1].strip():
            lines.pop()

        return "\n".join(lines).strip()

    def _decode_line(self, crop_norm: np.ndarray) -> str:
        """Decode a single text row using character template correlation."""
        x = 0
        decoded: list[str] = []
        max_x = crop_norm.shape[1]

        while x < max_x - 5:
            # If remaining width has no text
            if crop_norm[:, x:].max() < 25:
                break

            best_ch = None
            best_score = float("inf")

            for ch, (cw, t_arr) in self._char_templates.items():
                if x + cw > max_x:
                    continue
                sub = crop_norm[:, x : x + cw]
                diff = np.mean(np.abs(sub.astype(float) - t_arr.astype(float)))
                if diff < best_score:
                    best_score = diff
                    best_ch = ch

            if best_ch and best_score < 18.0:
                decoded.append(best_ch)
                x += self._char_templates[best_ch][0]
            else:
                x += 1

        return "".join(decoded).rstrip()

    def analyze_code(self, code_str: str) -> ExtractedCode:
        """Perform AST and regex inspection on VPython simulation source code."""
        extracted = ExtractedCode(
            assignment_type="lab3_final_code",
            source_code=code_str,
            code_blocks=[code_str] if code_str else [],
            raw_text=code_str,
        )

        if not code_str.strip():
            extracted.syntax_valid = False
            extracted.missing_elements = [
                "Scene Setup",
                "Variables Setup",
                "Animation Loop",
                "Euler Integration",
                "Collision Logic",
            ]
            return extracted

        # 1. AST Validation
        try:
            ast.parse(code_str)
            extracted.syntax_valid = True
        except SyntaxError as exc:
            extracted.syntax_valid = False
            extracted.extraction_warnings.append(f"Syntax error at line {exc.lineno}: {exc.msg}")

        # 2. Objects & Scene Setup
        has_canvas = "canvas(" in code_str or "scene" in code_str
        has_sphere = "sphere(" in code_str
        has_box = "box(" in code_str
        extracted.has_scene = has_canvas
        extracted.has_objects = has_sphere and has_box

        # 3. Variables Setup (Velocity & Timestep)
        has_velocity = "velocity" in code_str and "vector(" in code_str
        has_dt = "deltat" in code_str or "dt" in code_str
        extracted.has_velocity = has_velocity
        extracted.has_timestep = has_dt

        # 4. Animation Loop with rate()
        has_loop = "while" in code_str
        has_rate = "rate(" in code_str
        extracted.has_loop = has_loop
        extracted.has_rate = has_rate

        # 5. Position Euler Integration
        # Matches: ball.pos = ball.pos + ball.velocity * deltat or +=
        has_euler = bool(
            re.search(r"ball\.pos\s*(?:\+|\=)\s*.*?velocity", code_str, re.IGNORECASE)
        )
        extracted.has_euler_integration = has_euler

        # 6. Boundary Collisions (Reflection in X and Y)
        bounce_x = bool(
            re.search(r"(?:ball\.)?velocity\.x\s*=\s*(?:-abs|-|\b-1\b)", code_str, re.IGNORECASE)
            or ("velocity.x" in code_str and "-" in code_str)
        )
        bounce_y = bool(
            re.search(r"(?:ball\.)?velocity\.y\s*=\s*(?:-abs|-|\b-1\b)", code_str, re.IGNORECASE)
            or ("velocity.y" in code_str and "-" in code_str)
        )
        extracted.has_boundary_reflection = bounce_x and bounce_y

        # Populate missing elements for evaluator diagnostics
        missing: list[str] = []
        if not extracted.has_objects:
            missing.append("sphere/box objects")
        if not (extracted.has_velocity and extracted.has_timestep):
            missing.append("velocity vector / deltat")
        if not extracted.has_rate:
            missing.append("rate() function")
        if not extracted.has_euler_integration:
            missing.append("Euler position update")
        if not extracted.has_boundary_reflection:
            missing.append("boundary collision reflections")
        extracted.missing_elements = missing

        return extracted


# Module-level convenience function matching test harness signatures
def parse_vpython_code(
    code_input: RawSubmission | str | bytes | Path
) -> ExtractedCode:
    """Convenience wrapper to extract and analyze VPython code."""
    extractor = CodeExtractor()
    return extractor.extract(code_input)
