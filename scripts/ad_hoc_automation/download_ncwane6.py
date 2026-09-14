from config import BASE_URL
from src.auth.session import load_canvas_session
from src.api.client import CanvasAPIClient

client = CanvasAPIClient(base_url=BASE_URL, session=load_canvas_session(base_url=BASE_URL, validate=False, fallback_to_mock=True))
raw = client.get_assignment_submission(86326, 316843, 188587)
pdf_url = raw['attachments'][0]['url']
pdf_bytes = client.download_attachment(pdf_url)
with open('artifacts/ncwane_exp06.pdf', 'wb') as f:
    f.write(pdf_bytes)
print("Saved to artifacts/ncwane_exp06.pdf")
