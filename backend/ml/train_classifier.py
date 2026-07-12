import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
from sklearn.pipeline import Pipeline
import joblib

def main():
    base_dir = os.path.dirname(__file__)
    data_path = os.path.join(base_dir, "training_data.csv")
    
    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found. Run generate_training_data.py first.")
        return

    print("Loading data...")
    df = pd.read_csv(data_path)
    print(f"Total samples: {len(df)}")
    # Randomize entire dataset
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    # Stratified split
    X_train, X_test, y_train, y_test = train_test_split(
        df["text"], df["label"], test_size=0.2, random_state=42, stratify=df["label"]
    )
    
    print(f"Training set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples\n")
    
    # Model 1: Logistic Regression
    pipeline_lr = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1, 2), max_features=5000)),
        ('clf', LogisticRegression(random_state=42, max_iter=1000))
    ])
    
    # Model 2: Calibrated LinearSVC
    pipeline_svc = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1, 2), max_features=5000)),
        ('clf', CalibratedClassifierCV(LinearSVC(random_state=42, dual='auto'), method='sigmoid', cv=5))
    ])
    
    models = {
        "Logistic Regression": pipeline_lr,
        "LinearSVC (Calibrated)": pipeline_svc
    }
    
    results = {}
    reports = []
    
    for name, pipeline in models.items():
        print(f"Training {name}...")
        pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)
        
        acc = accuracy_score(y_test, y_pred)
        report_dict = classification_report(y_test, y_pred, output_dict=True)
        report_str = classification_report(y_test, y_pred)
        cm = confusion_matrix(y_test, y_pred, labels=pipeline.classes_)
        
        weighted_f1 = report_dict['weighted avg']['f1-score']
        results[name] = {
            "pipeline": pipeline,
            "weighted_f1": weighted_f1,
            "accuracy": acc
        }
        
        reports.append(f"=== {name} ===\nAccuracy: {acc:.4f}\nWeighted F1: {weighted_f1:.4f}\n\nClassification Report:\n{report_str}\nConfusion Matrix:\n{cm}\nLabels: {pipeline.classes_}\n")

    # Select winner
    winner_name = max(results.keys(), key=lambda k: results[k]["weighted_f1"])
    winner_pipeline = results[winner_name]["pipeline"]
    
    summary = f"\n*** WINNER: {winner_name} ***\n"
    summary += f"Selected {winner_name} because it achieved the highest weighted F1 score ({results[winner_name]['weighted_f1']:.4f}).\n"
    print(summary)
    
    # Save the winner
    model_path = os.path.join(base_dir, "classifier.joblib")
    joblib.dump(winner_pipeline, model_path)
    print(f"Saved winning model to {model_path}")
    
    # Save evaluation report
    report_path = os.path.join(base_dir, "evaluation_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("ML Classifier Evaluation Report\n")
        f.write("===============================\n\n")
        f.write(summary + "\n")
        f.write("-" * 50 + "\n\n")
        for r in reports:
            f.write(r + "\n")
            
    print(f"Saved full evaluation report to {report_path}")

if __name__ == "__main__":
    main()
