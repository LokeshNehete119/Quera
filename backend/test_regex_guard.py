import re
import joblib
import pandas as pd

pipeline = joblib.load(r"C:\Users\Lokesh Nehete\Desktop\Quera\backend\ml\classifier.joblib")

test_cases = [
    "who invented PostgreSQL?",
    "what is MySQL",
    "explain NoSQL databases",
    "tell me about my db",
    "write a sql query to find users"
]

INTENT_GUARD_KEYWORDS = [r"\bdb\b", r"\bdatabase\b", r"\btable\b", r"\bschema\b", r"\bcolumn\b", r"\bdata\b", r"\bsql\b"]
WRITE_VERBS = ["delete", "drop", "create", "insert", "update", "remove", "rename", "truncate", "assign", "set", "replace", "archive", "restore", "fill", "make"]
CASUAL_PHRASES = ["explain", "suggest", "how to", "what is a ", "help me", "change the table"]

print("EXPLICIT TEST QUERIES:")
print("-" * 50)

for text in test_cases:
    msg_lower = text.lower()
    
    # 1. Check what Keyword Guard does
    has_kw = any(re.search(pattern, msg_lower) for pattern in INTENT_GUARD_KEYWORDS)
    has_write = any(wv in msg_lower for wv in WRITE_VERBS)
    has_casual = any(cp in msg_lower for cp in CASUAL_PHRASES)
    
    forced_category = None
    if has_kw and not has_write and not has_casual:
        forced_category = "read"
        
    # 2. Check what ML Classifier does
    ml_category = pipeline.predict([text])[0]
    
    # 3. Final Prediction
    final_pred = forced_category if forced_category else ml_category
    
    print(f"Query: \"{text}\"")
    print(f"Routed to: {final_pred}")
    if forced_category:
        print(f" -> Reason: Caught by Keyword Guard (Forced to {forced_category})")
    else:
        print(f" -> Reason: Missed by Guard, ML Classifier predicted '{ml_category}'")
    print("-" * 50)
