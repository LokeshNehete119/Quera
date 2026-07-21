import pandas as pd

import pandas as pd

manual_data = []
with open(r"C:\Users\Lokesh Nehete\Desktop\Quera\backend\ml\manual_eval_set.csv", 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        parts = line.rsplit(',', 1)
        if len(parts) == 2:
            text, label = parts[0].strip(), parts[1].strip()
            if text.startswith('"') and text.endswith('"'): text = text[1:-1]
            if label.startswith('"') and label.endswith('"'): label = label[1:-1]
            if "PLACEHOLDER" not in text and text != "text":
                manual_data.append({"text": text, "label": label})
df = pd.DataFrame(manual_data)

db_kws = ["db", "database", "table", "schema", "column", "data", "sql"]
write_verbs = ["delete", "drop", "create", "insert", "update", "remove", "rename", "truncate", "assign", "set", "replace", "archive", "restore", "fill", "make"]
casual_phrases = ["explain", "suggest", "how to", "what is a ", "help me", "change the table"]

def test_guard(text):
    msg = text.lower()
    if not any(kw in msg for kw in db_kws): return False
    if any(wv in msg for wv in write_verbs): return False
    if any(cp in msg for cp in casual_phrases): return False
    return True

print("Cases that the guard forces to READ:")
for _, row in df.iterrows():
    if test_guard(row['text']):
        print(f"[{row['label']}] {row['text']}")

