from config import BASE_URL
from src.auth.session import load_canvas_session
from src.api.client import CanvasAPIClient
from src.extractor.pdf_extractor import PDFExtractor
from src.evaluator.exp05_evaluator import Exp05Evaluator

client = CanvasAPIClient(base_url=BASE_URL, session=load_canvas_session(base_url=BASE_URL, validate=False, fallback_to_mock=True))
raw = client.get_assignment_submission(86326, 316696, 188587)
pdf_url = raw['attachments'][0]['url']
pdf_bytes = client.download_attachment(pdf_url)

extractor = PDFExtractor()
extracted = extractor.extract(pdf_bytes, assignment_type="exp05")
print("Raw Text Snippet:", repr(extracted.raw_text[:100]))
print("Is Valid:", extracted.is_valid)

evaluator = Exp05Evaluator()
res = evaluator.evaluate(extracted)
print("Score:", res.score)
print("Feedback:", res.feedback_lines)
