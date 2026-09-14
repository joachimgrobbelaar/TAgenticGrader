from config import BASE_URL
from src.auth.session import load_canvas_session
from src.api.client import CanvasAPIClient
from src.extractor.pdf_extractor import PDFExtractor

client = CanvasAPIClient(base_url=BASE_URL, session=load_canvas_session(base_url=BASE_URL, validate=False, fallback_to_mock=True))
extractor = PDFExtractor()

for uid in [188587, 190782, 190515, 199432, 161561]:
    raw = client.get_assignment_submission(86326, 316696, uid)
    if not raw.get('attachments'): continue
    pdf_url = raw['attachments'][0]['url']
    pdf_bytes = client.download_attachment(pdf_url)
    extracted = extractor.extract(pdf_bytes, assignment_type="exp05")
    print(f"Student {uid} raw text length: {len(extracted.raw_text.strip())}")
