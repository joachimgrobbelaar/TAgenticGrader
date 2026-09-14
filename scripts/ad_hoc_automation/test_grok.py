import os
import requests
import fitz
import base64

API_KEY = os.environ.get("GROK_API_KEY")
from config import BASE_URL
from src.auth.session import load_canvas_session
from src.api.client import CanvasAPIClient

# Download Precious Ncwane's PDF (188587)
client = CanvasAPIClient(base_url=BASE_URL, session=load_canvas_session(base_url=BASE_URL, validate=False, fallback_to_mock=True))
raw = client.get_assignment_submission(86326, 316696, 188587)
pdf_url = raw['attachments'][0]['url']
pdf_bytes = client.download_attachment(pdf_url)

doc = fitz.open(stream=pdf_bytes, filetype="pdf")
print(f"Pages: {len(doc)}")

extracted_text = ""
for page in doc:
    pix = page.get_pixmap()
    img_bytes = pix.tobytes("png")
    b64_img = base64.b64encode(img_bytes).decode('utf-8')
    
    payload = {
        "model": "grok-2-vision-1212",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64_img}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "Please transcribe the handwritten text in this lab report image as accurately as possible. Output only the transcribed text."
                    }
                ]
            }
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    resp = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload)
    data = resp.json()
    if 'choices' in data:
        text = data['choices'][0]['message']['content']
        extracted_text += text + "\n\n"
    else:
        print("API Error:", data)
        break

print("Extracted:")
print(extracted_text)
