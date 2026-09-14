import json, re, sys
from config import BASE_URL, COURSE_ID
from src.auth.session import load_canvas_session
from src.api.client import CanvasAPIClient

client = CanvasAPIClient(base_url=BASE_URL, session=load_canvas_session(base_url=BASE_URL, validate=False, fallback_to_mock=True))

SUBAGENT_MAP = {
    "355bc54f-8d62-468e-ac09-95b4f191518b": 164236, # Khazimla
    "5785fb07-0b78-41f0-aff6-4acbc58d233c": 190927, # Nseketelo
    "a2566bb3-7f14-4f0b-bbb1-548b9c97f60a": 190482, # Linamandla
    "bdbef2c6-be75-4072-bcef-0f105a08d621": 190965, # Kamogelo
    "6d25dc6c-8ac1-4853-9066-2eae470e407c": 195568, # Tatenda
    "52ec1378-949c-4d6a-b575-b0153c8daac6": 189908, # Bonolo
    "8ac81bb2-d3eb-425f-b8fb-746cf344141d": 104588, # Anthocia
    "b128bb6b-07c4-4522-8969-7fce61bedb5d": 191463, # Rethabile
    "ad61d26a-2c19-48fb-aeae-f650e5dbe20d": 190267, # Awakhiwe
    "8b8b6ee3-1586-43a8-9ff5-b948df296f23": 195580, # Onke
    "44b7619f-0af2-4f6e-b3cd-e770ffbab899": 193718, # Amahle
    "2a4a80ce-9132-49b0-ae26-aaa5c3247cda": 192479  # Imange
}

# ALREADY PROCESSED
PROCESSED_USERS = {190482, 195568, 189908, 190965, 104588, 192479, 190267, 191463}

grades_to_post = []

with open("/home/m/.gemini/antigravity-cli/brain/17c90019-ff18-4243-ae6d-b7f519d73d89/.system_generated/logs/transcript_full.jsonl", "r") as f:
    lines = f.readlines()

for line in lines:
    try:
        obj = json.loads(line)
        if obj.get("type") == "SYSTEM_MESSAGE":
            content = obj.get("content", "")
            
            # Find the true sender ID
            sender_id = None
            if "Subagent" in content and "has gone idle" in content:
                m = re.search(r'Subagent ([a-f0-9\-]+) has gone idle', content)
                if m: sender_id = m.group(1)
            elif "sender=" in content:
                m = re.search(r'sender=([a-f0-9\-]+)', content)
                if m and m.group(1) != "system":
                    sender_id = m.group(1)
                
            if sender_id and sender_id in SUBAGENT_MAP:
                user_id = SUBAGENT_MAP[sender_id]
                if user_id in PROCESSED_USERS:
                    continue
                
                json_blocks = re.findall(r'```json\n(.*?)\n```', content, re.DOTALL)
                
                if len(json_blocks) == 2:
                    exp05_data = json.loads(json_blocks[0])
                    exp06_data = json.loads(json_blocks[1])
                    grades_to_post.append({"user_id": user_id, "assignment_id": 316697, "data": exp05_data})
                    grades_to_post.append({"user_id": user_id, "assignment_id": 316844, "data": exp06_data})
                elif len(json_blocks) == 1:
                    data = json.loads(json_blocks[0])
                    if "EXP05" in data and "EXP06" in data:
                        grades_to_post.append({"user_id": user_id, "assignment_id": 316697, "data": data["EXP05"]})
                        grades_to_post.append({"user_id": user_id, "assignment_id": 316844, "data": data["EXP06"]})
                    elif "EXP 05" in data and "EXP 06" in data:
                        grades_to_post.append({"user_id": user_id, "assignment_id": 316697, "data": data["EXP 05"]})
                        grades_to_post.append({"user_id": user_id, "assignment_id": 316844, "data": data["EXP 06"]})
    except Exception as e:
        pass

final_grades = {}
for g in grades_to_post:
    final_grades[(g["user_id"], g["assignment_id"])] = g["data"]

print(f"Found {len(final_grades)} grades to post.")

for (uid, aid), data in final_grades.items():
    total_score = min(20.0, float(data.get("total", 0.0)))
    
    title = "EXP 05: Thermal Expansion" if aid == 316697 else "EXP 06: Thin Spherical Lenses"
    comment = f"**{title} - Breakdown**\n"
    for k, v in data.get("breakdown", {}).items():
        comment += f"- {k}: {v}\n"
    comment += f"**Final Score: {total_score} / 20.0**\n"
    comment += f"*(Graded from scanned handwriting via Vision OCR)*\n\n"
    if "notes" in data:
        comment += f"Notes: {data['notes']}"
        
    print(f"Posting {total_score} for {uid} on {aid}...")
    client._request("PUT", f"/api/v1/courses/{COURSE_ID}/assignments/{aid}/submissions/{uid}", data={
        "submission[posted_grade]": total_score,
        "comment[text_comment]": comment.strip()
    })
print("Done!")
