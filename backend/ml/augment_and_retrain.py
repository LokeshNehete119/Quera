import os
import shutil
import pandas as pd
import subprocess

def main():
    base_dir = os.path.dirname(__file__)
    training_path = os.path.join(base_dir, "training_data.csv")
    backup_path = os.path.join(base_dir, "training_data_backup_pre_augment.csv")
    augment_path = os.path.join(base_dir, "casual_augment_examples.csv")
    train_script_path = os.path.join(base_dir, "train_classifier.py")
    
    # 1. Backup
    if os.path.exists(training_path):
        shutil.copy2(training_path, backup_path)
        print(f"Backed up {training_path} to {backup_path}")
    else:
        print(f"Error: {training_path} not found.")
        return
        
    # 2. Parse augmentation data safely
    print(f"Loading augmentation data from {augment_path}...")
    manual_data = []
    with open(augment_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if i == 0: continue # skip header
            line = line.strip()
            if not line: continue
            if "PLACEHOLDER - REPLACE ME" in line: continue
            
            parts = line.rsplit(',', 1)
            if len(parts) == 2:
                text, label = parts[0].strip(), parts[1].strip()
                if text.startswith('"') and text.endswith('"'):
                    text = text[1:-1]
                if label.startswith('"') and label.endswith('"'):
                    label = label[1:-1]
                manual_data.append({"text": text, "label": label})
                
    df_new = pd.DataFrame(manual_data)
    if len(df_new) == 0:
        print("No new valid examples found in casual_augment_examples.csv.")
        return
        
    print(f"Loaded {len(df_new)} new examples.")
    
    # 3. Append to existing training data
    df_train = pd.read_csv(training_path, on_bad_lines='skip')
    initial_len = len(df_train)
    
    df_combined = pd.concat([df_train, df_new], ignore_index=True)
    df_combined = df_combined.sample(frac=1, random_state=42).reset_index(drop=True)
    df_combined.to_csv(training_path, index=False)
    
    print(f"Augmented training data from {initial_len} to {len(df_combined)} rows.")
    
    # 4. Retrain by running train_classifier.py
    print("\nStarting retraining...")
    # Get path to current python executable in the venv
    import sys
    python_exe = sys.executable
    result = subprocess.run([python_exe, train_script_path], cwd=os.path.dirname(base_dir))
    
    if result.returncode == 0:
        print("\nRetraining completed successfully!")
    else:
        print("\nRetraining failed.")

if __name__ == "__main__":
    main()
