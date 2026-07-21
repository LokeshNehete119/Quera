import json
import os

log_path = r"C:\Users\Lokesh Nehete\.gemini\antigravity\brain\098e064f-85b0-4639-882d-79d1a2b7e0bb\.system_generated\logs\transcript_full.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

latest_content = None

for line in lines:
    try:
        data = json.loads(line)
        if data.get("type") == "PLANNER_RESPONSE":
            calls = data.get("tool_calls", [])
            for call in calls:
                if call.get("name") == "write_to_file":
                    args = call.get("args", {})
                    target = args.get("TargetFile", "")
                    if "page.tsx" in target:
                        latest_content = args.get("CodeContent", "")
                        print(f"Captured write_to_file content from step {data.get('step_index')}")
    except Exception as e:
        pass

if latest_content:
    with open(r"C:\Users\Lokesh Nehete\Desktop\Quera\recovered_page.tsx", "w", encoding="utf-8") as f:
        f.write(latest_content)
    print("Recovered content saved to recovered_page.tsx")
else:
    print("Could not find a write_to_file call for page.tsx")
