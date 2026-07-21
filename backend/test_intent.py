import joblib
import os

model_path = r"C:\Users\Lokesh Nehete\Desktop\Quera\backend\ml\classifier.joblib"

if os.path.exists(model_path):
    classifier = joblib.load(model_path)
        
    query = "tell me about my db"
    
    INTENT_GUARD_KEYWORDS = ["db", "database", "table", "schema", "column", "data", "sql"]
    
    msg_lower = query.lower()
    if any(kw in msg_lower for kw in INTENT_GUARD_KEYWORDS):
        category = "read"
        print(f"[INTENT CLASSIFIER] Message: '{query}' -> Forced Category: {category} (Source: Keyword Guard)")
    else:
        predicted_labels = classifier.predict([query])
        category = predicted_labels[0]
        print(f"[INTENT CLASSIFIER] Message: '{query}' -> Predicted Category: {category} (Source: Local ML)")
        
else:
    print(f"Model not found at {model_path}")
