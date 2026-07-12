import nbformat as nbf
import os

def create_notebook():
    nb = nbf.v4.new_notebook()

    code_cell_1 = """import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
from sklearn.pipeline import Pipeline
import joblib"""

    code_cell_2 = """# Load and randomize data
df = pd.read_csv("training_data.csv")
print(f"Total samples: {len(df)}")
df = df.sample(frac=1, random_state=42).reset_index(drop=True)
df.head()"""

    code_cell_3 = """# Stratified 80-20 train-test split
X_train, X_test, y_train, y_test = train_test_split(
    df["text"], df["label"], test_size=0.2, random_state=42, stratify=df["label"]
)
print(f"Training set: {len(X_train)} samples")
print(f"Test set: {len(X_test)} samples")"""

    code_cell_4 = """# Define models
pipeline_lr = Pipeline([
    ('tfidf', TfidfVectorizer(ngram_range=(1, 2), max_features=5000)),
    ('clf', LogisticRegression(random_state=42, max_iter=1000))
])

pipeline_svc = Pipeline([
    ('tfidf', TfidfVectorizer(ngram_range=(1, 2), max_features=5000)),
    ('clf', CalibratedClassifierCV(LinearSVC(random_state=42, dual='auto'), method='sigmoid', cv=5))
])"""

    code_cell_5 = """# Train and Evaluate Logistic Regression
pipeline_lr.fit(X_train, y_train)
y_pred_lr = pipeline_lr.predict(X_test)
print("=== Logistic Regression ===")
print("Accuracy:", accuracy_score(y_test, y_pred_lr))
print(classification_report(y_test, y_pred_lr))"""

    code_cell_6 = """# Train and Evaluate LinearSVC
pipeline_svc.fit(X_train, y_train)
y_pred_svc = pipeline_svc.predict(X_test)
print("=== LinearSVC (Calibrated) ===")
print("Accuracy:", accuracy_score(y_test, y_pred_svc))
print(classification_report(y_test, y_pred_svc))"""

    code_cell_7 = """# Save best model
# Assuming LinearSVC was better based on your runs
joblib.dump(pipeline_svc, "classifier.joblib")
print("Saved winning model to classifier.joblib")"""

    nb['cells'] = [
        nbf.v4.new_markdown_cell("# Quera - Intent Classifier Training"),
        nbf.v4.new_code_cell(code_cell_1),
        nbf.v4.new_markdown_cell("## 1. Load and Randomize Data"),
        nbf.v4.new_code_cell(code_cell_2),
        nbf.v4.new_markdown_cell("## 2. Train-Test Split (80/20)"),
        nbf.v4.new_code_cell(code_cell_3),
        nbf.v4.new_markdown_cell("## 3. Define and Train Models"),
        nbf.v4.new_code_cell(code_cell_4),
        nbf.v4.new_code_cell(code_cell_5),
        nbf.v4.new_code_cell(code_cell_6),
        nbf.v4.new_markdown_cell("## 4. Save Model"),
        nbf.v4.new_code_cell(code_cell_7),
    ]

    base_dir = os.path.dirname(__file__)
    nb_path = os.path.join(base_dir, "train_classifier.ipynb")
    with open(nb_path, 'w', encoding='utf-8') as f:
        nbf.write(nb, f)
    print(f"Created notebook at {nb_path}")

if __name__ == "__main__":
    create_notebook()
