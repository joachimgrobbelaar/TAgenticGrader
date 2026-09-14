import requests
from config import BASE_URL
from src.auth.session import load_canvas_session

session = load_canvas_session(base_url=BASE_URL, validate=False, fallback_to_mock=True)

course_id = 86326
mistake_assignments = [316697, 316844]
student_ids = [188587, 190782, 190515, 199432, 161561]

for aid in mistake_assignments:
    for uid in student_ids:
        print(f"Resetting for student {uid} on assignment {aid}")
        requests.put(
            f"{BASE_URL}/api/v1/courses/{course_id}/assignments/{aid}/submissions/{uid}",
            cookies=session.cookies,
            headers={"X-CSRFToken": session.csrf_token} if session.csrf_token else {},
            json={"submission": {"posted_grade": ""}}
        )
print("Done cleaning mistakes.")
