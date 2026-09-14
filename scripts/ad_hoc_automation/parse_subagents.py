import json, re

# read the entire content as string
with open("/home/m/.gemini/antigravity-cli/brain/17c90019-ff18-4243-ae6d-b7f519d73d89/.system_generated/logs/transcript_full.jsonl", "r") as f:
    text = f.read()

subids = [
    "355bc54f-8d62-468e-ac09-95b4f191518b",
    "5785fb07-0b78-41f0-aff6-4acbc58d233c",
    "a2566bb3-7f14-4f0b-bbb1-548b9c97f60a",
    "bdbef2c6-be75-4072-bcef-0f105a08d621",
    "6d25dc6c-8ac1-4853-9066-2eae470e407c",
    "52ec1378-949c-4d6a-b575-b0153c8daac6",
    "8ac81bb2-d3eb-425f-b8fb-746cf344141d",
    "b128bb6b-07c4-4522-8969-7fce61bedb5d",
    "ad61d26a-2c19-48fb-aeae-f650e5dbe20d",
    "8b8b6ee3-1586-43a8-9ff5-b948df296f23",
    "44b7619f-0af2-4f6e-b3cd-e770ffbab899",
    "2a4a80ce-9132-49b0-ae26-aaa5c3247cda"
]

for sid in subids:
    if sid in text:
        print(f"Found ID {sid}")
