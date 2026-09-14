import urllib.parse
from config import BASE_URL, COURSE_ID
from src.auth.session import load_canvas_session
from src.api.client import CanvasAPIClient

client = CanvasAPIClient(base_url=BASE_URL, session=load_canvas_session(base_url=BASE_URL, validate=False, fallback_to_mock=True))

comment = """
**EXP 06: Thin Spherical Lenses - Breakdown**
- Introduction & Aims: 2.0 / 2.0
- Method 1 (Estimate): 1.0 / 1.0
- Method 2 (Separation): 5.5 / 7.0 (Missing final f & uncertainty calculation from graph)
- Method 3 (Magnification): 5.0 / 5.0
- Discussion: 1.0 / 1.0
- Conclusion: 1.0 / 1.0
- Questions: 3.0 / 3.0
**Final Score: 18.5 / 20.0**
*(Graded from scanned handwriting via Vision OCR)*
"""

client._request("PUT", f"/api/v1/courses/{COURSE_ID}/assignments/316843/submissions/188587", data={"submission[posted_grade]": 18.5, "comment[text_comment]": comment.strip()})
print("Posted Exp06 for Precious!")
