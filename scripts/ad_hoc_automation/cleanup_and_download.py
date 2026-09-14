import sys, os, json
from config import BASE_URL, COURSE_ID
from src.auth.session import load_canvas_session
from src.api.client import CanvasAPIClient
from src.extractor.pdf_extractor import PDFExtractor
from run_custom_cohorts import get_cohort_users
import fitz

client = CanvasAPIClient(base_url=BASE_URL, session=load_canvas_session(base_url=BASE_URL, validate=False, fallback_to_mock=True))
extractor = PDFExtractor()
users = get_cohort_users(144689, 1, 31)

# Step 1: Delete all old comments for Fri2 1-31 on both assignments
print("=== DELETING OLD COMMENTS ===")
for aid in [316697, 316844]:
    for u in users:
        try:
            client.delete_all_submission_comments(COURSE_ID, aid, u.user_id)
            print(f"  Deleted comments for {u.name} on {aid}")
        except Exception as e:
            print(f"  Skip {u.name} on {aid}: {e}")

# Step 2: Download handwritten PDFs and render page images
print("\n=== DOWNLOADING HANDWRITTEN PDFs ===")
os.makedirs("artifacts/handwritten", exist_ok=True)

handwritten = []
for aid in [316697, 316844]:
    atype = "exp05" if aid == 316697 else "exp06"
    for u in users:
        try:
            raw = client.get_assignment_submission(COURSE_ID, aid, u.user_id)
            if raw.get('workflow_state') == 'unsubmitted' or not raw.get('attachments'):
                continue
            pdf_url = raw['attachments'][0]['url']
            pdf_bytes = client.download_attachment(pdf_url)
            extracted = extractor.extract(pdf_bytes, assignment_type=atype)
            
            if len(extracted.raw_text.strip()) == 0:
                # Handwritten - save PDF and render pages as images
                prefix = f"{u.user_id}_{aid}"
                with open(f"artifacts/handwritten/{prefix}.pdf", "wb") as f:
                    f.write(pdf_bytes)
                
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=200)
                    pix.save(f"artifacts/handwritten/{prefix}_p{i}.png")
                
                handwritten.append({
                    "user_id": u.user_id,
                    "name": u.name,
                    "assignment_id": aid,
                    "assignment_type": atype,
                    "pages": len(doc),
                    "prefix": prefix
                })
                print(f"  Saved {len(doc)} pages for {u.name} ({atype})")
                doc.close()
        except Exception as e:
            print(f"  Error for {u.name} on {aid}: {e}")

with open("artifacts/handwritten/manifest.json", "w") as f:
    json.dump(handwritten, f, indent=2)

print(f"\nTotal handwritten submissions to grade: {len(handwritten)}")
