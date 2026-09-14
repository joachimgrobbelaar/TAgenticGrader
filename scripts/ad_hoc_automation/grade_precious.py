from config import BASE_URL, COURSE_ID
from src.auth.session import load_canvas_session
from src.api.client import CanvasAPIClient

client = CanvasAPIClient(base_url=BASE_URL, session=load_canvas_session(base_url=BASE_URL, validate=False, fallback_to_mock=True))

comment = """
**EXP 05: Thermal Expansion - Breakdown**
- Aims & Methodology: 2.5 / 2.5
- Measurement Tables (Brass & SS): 7.0 / 7.0
- Calculations (Coefficients): 2.0 / 3.0
- Discussion: 1.0 / 1.0
- Conclusion: 0.0 / 2.0 (Missing Kaye & Laby literature comparison)
- Question 1: 2.0 / 2.0
- Question 2: 1.0 / 2.0
- Question 3: 1.0 / 1.0
**Final Score: 16.5 / 20.0**
*(Graded from scanned handwriting via Vision OCR)*
"""
import urllib.parse
client._request("PUT", f"/api/v1/courses/{COURSE_ID}/assignments/316696/submissions/188587", data={"submission[posted_grade]": 16.5, "comment[text_comment]": comment.strip()})
print("Posted Exp05 for Precious!")
