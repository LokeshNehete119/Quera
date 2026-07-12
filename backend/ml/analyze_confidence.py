import os
import pandas as pd
import joblib
import numpy as np

def main():
    base_dir = os.path.dirname(__file__)
    data_path = os.path.join(base_dir, "manual_eval_set.csv")
    model_path = os.path.join(base_dir, "classifier.joblib")
    
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
    # Remove placeholders
    df = df[~df['text'].str.contains("PLACEHOLDER - REPLACE ME", na=False)]
    
    print(f"Loaded {len(df)} examples.")
    
    print(f"Loading model from {model_path}...")
    pipeline = joblib.load(model_path)
    
    y_true = df["label"].values
    texts = df["text"].values
    y_pred = pipeline.predict(texts)
    
    # Get probabilities
    if hasattr(pipeline, "predict_proba"):
        probs = pipeline.predict_proba(texts)
    else:
        print("Model does not support predict_proba.")
        return
        
    # Max probability is the confidence of the predicted class
    confidences = np.max(probs, axis=1)
    
    correct_mask = (y_true == y_pred)
    incorrect_mask = (y_true != y_pred)
    
    print("\n" + "="*50)
    print("CONFIDENCE ANALYSIS: MISCLASSIFIED EXAMPLES")
    print("="*50)
    
    misclassified_indices = np.where(incorrect_mask)[0]
    for idx in misclassified_indices:
        safe_text = str(texts[idx]).encode('ascii', 'ignore').decode('ascii')
        print(f"Text:      \"{safe_text}\"")
        print(f"True:      {y_true[idx]}")
        print(f"Predicted: {y_pred[idx]}")
        print(f"Confidence: {confidences[idx]:.4f}")
        print("-" * 30)
        
    print("\n" + "="*50)
    print("CONFIDENCE DISTRIBUTION")
    print("="*50)
    
    if np.any(correct_mask):
        corr_conf = confidences[correct_mask]
        print(f"Correct Predictions (Count: {len(corr_conf)}):")
        print(f"  Mean Confidence: {np.mean(corr_conf):.4f}")
        print(f"  Min Confidence:  {np.min(corr_conf):.4f}")
        print(f"  Max Confidence:  {np.max(corr_conf):.4f}")
    
    if np.any(incorrect_mask):
        inc_conf = confidences[incorrect_mask]
        print(f"\nIncorrect Predictions (Count: {len(inc_conf)}):")
        print(f"  Mean Confidence: {np.mean(inc_conf):.4f}")
        print(f"  Min Confidence:  {np.min(inc_conf):.4f}")
        print(f"  Max Confidence:  {np.max(inc_conf):.4f}")

if __name__ == "__main__":
    main()
