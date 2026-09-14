from config import BASE_URL
from src.auth.session import load_canvas_session
from src.api.client import CanvasAPIClient
from src.extractor.pdf_extractor import PDFExtractor
from src.navigation.cohort import CohortStudent
from run_custom_cohorts import get_cohort_users

client = CanvasAPIClient(base_url=BASE_URL, session=load_canvas_session(base_url=BASE_URL, validate=False, fallback_to_mock=True))
extractor = PDFExtractor()
users = get_cohort_users(144689, 1, 31)

handwritten_tasks = []

for aid in [316697, 316844]:
    for u in users:
        try:
            raw = client.get_assignment_submission(86326, aid, u.user_id)
            if raw.get('workflow_state') == 'unsubmitted': continue
            if not raw.get('attachments'): continue
            
            pdf_url = raw['attachments'][0]['url']
            pdf_bytes = client.download_attachment(pdf_url)
            extracted = extractor.extract(pdf_bytes, assignment_type="exp05" if aid==316697 else "exp06")
            
            if len(extracted.raw_text.strip()) == 0:
                print(f"Student {u.name} ({u.user_id}) on assignment {aid} is handwritten!")
                handwritten_tasks.append((aid, u.user_id, u.name))
        except Exception as e:
            pass

print(f"Found {len(handwritten_tasks)} handwritten assignments.")
