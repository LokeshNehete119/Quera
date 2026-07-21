import pandas as pd
import joblib

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

pipeline = joblib.load(r"C:\Users\Lokesh Nehete\Desktop\Quera\backend\ml\classifier.joblib")

INTENT_GUARD_KEYWORDS = ["db", "database", "table", "schema", "column", "data", "sql"]
WRITE_VERBS = ["delete", "drop", "create", "insert", "update", "remove", "rename", "truncate", "assign", "set", "replace", "archive", "restore", "fill", "make"]
CASUAL_PHRASES = ["explain", "suggest", "how to", "what is a ", "help me", "change the table"]

print("MISCLASSIFIED CASUAL QUERIES (ANALYSIS):")
print("-" * 50)

for _, row in df[df['label'] == 'casual'].iterrows():
    text = row['text']
    msg_lower = text.lower()
    
    # 1. Check what Keyword Guard does
    has_kw = any(kw in msg_lower for kw in INTENT_GUARD_KEYWORDS)
    has_write = any(wv in msg_lower for wv in WRITE_VERBS)
    has_casual = any(cp in msg_lower for cp in CASUAL_PHRASES)
    
    forced_category = None
    if has_kw and not has_write and not has_casual:
        forced_category = "read"
        
    # 2. Check what ML Classifier does
    ml_category = pipeline.predict([text])[0]
    
    # 3. Final Prediction
    final_pred = forced_category if forced_category else ml_category
    
    if final_pred != "casual":
        print(f"Text: \"{text}\"")
        print(f"Final Prediction: {final_pred}")
        if forced_category:
            print(f" -> Reason: Caught by Keyword Guard (Forced to {forced_category})")
        else:
            print(f" -> Reason: Missed by Guard, ML Classifier predicted {ml_category} natively")
        print("-" * 50)
