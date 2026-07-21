import os
import pandas as pd
import joblib
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

def main():
    base_dir = os.path.dirname(__file__)
    data_path = os.path.join(base_dir, "manual_eval_set.csv")
    model_path = os.path.join(base_dir, "classifier.joblib")
    
    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found.")
        return
        
    if not os.path.exists(model_path):
        print(f"Error: {model_path} not found.")
        return

    print(f"Loading data from {data_path}...")
    
    manual_data = []
    with open(data_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if i == 0: continue # skip header
            line = line.strip()
            if not line: continue
            
            parts = line.rsplit(',', 1)
            if len(parts) == 2:
                text, label = parts[0].strip(), parts[1].strip()
                if text.startswith('"') and text.endswith('"'):
                    text = text[1:-1]
                if label.startswith('"') and label.endswith('"'):
                    label = label[1:-1]
                if text.lower() == "text" and label.lower() == "label":
                    continue # skip exact header match
                manual_data.append({"text": text, "label": label})
                
    df = pd.DataFrame(manual_data)
    
    # Filter out placeholders if the user accidentally left them in without changing text
    df = df[~df['text'].str.contains("PLACEHOLDER - REPLACE ME", na=False)]
    
    if len(df) == 0:
        print("Error: The evaluation set is empty (or only contains the placeholder template rows).")
        return

    print(f"Loaded {len(df)} examples for evaluation.\n")
    
    print(f"Loading model from {model_path}...")
    pipeline = joblib.load(model_path)
    
    import re
    # Predict using the same logic as main.py (Keyword Guard + ML Fallback)
    INTENT_GUARD_KEYWORDS = [r"\bdb\b", r"\bdatabase\b", r"\btable\b", r"\bschema\b", r"\bcolumn\b", r"\bdata\b", r"\bsql\b"]
    WRITE_VERBS = ["delete", "drop", "create", "insert", "update", "remove", "rename", "truncate", "assign", "set", "replace", "archive", "restore", "fill", "make"]
    CASUAL_PHRASES = ["explain", "suggest", "how to", "what is a ", "help me", "change the table"]
    
    y_pred = []
    y_true = df["label"]
    for text in df["text"]:
        msg_lower = text.lower()
        has_kw = any(re.search(pattern, msg_lower) for pattern in INTENT_GUARD_KEYWORDS)
        has_write = any(wv in msg_lower for wv in WRITE_VERBS)
        has_casual = any(cp in msg_lower for cp in CASUAL_PHRASES)
        
        if has_kw and not has_write and not has_casual:
            y_pred.append("read")
        else:
            y_pred.append(pipeline.predict([text])[0])
            
    y_pred = pd.Series(y_pred, index=df.index)
    
    # Metrics
    acc = accuracy_score(y_true, y_pred)
    print("="*50)
    print(f"Overall Accuracy: {acc:.4f}")
    print("="*50)
    
    print("\nClassification Report:")
    print(classification_report(y_true, y_pred))
    
    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_true, y_pred, labels=pipeline.classes_)
    print(cm)
    print(f"Labels: {pipeline.classes_}")
    
    # Find misclassified examples
    print("\n" + "="*50)
    print("Misclassified Examples:")
    print("="*50)
    
    misclassified = df[y_true != y_pred].copy()
    misclassified["predicted"] = y_pred[y_true != y_pred]
    
    if len(misclassified) == 0:
        print("None! The classifier scored 100% on the manual evaluation set.")
    else:
        for idx, row in misclassified.iterrows():
            # handle emojis/unicode for windows console
            safe_text = str(row['text']).encode('ascii', 'ignore').decode('ascii')
            print(f"Text:      \"{safe_text}\"")
            print(f"True:      {row['label']}")
            print(f"Predicted: {row['predicted']}")
            print("-" * 30)

if __name__ == "__main__":
    main()
