import sqlite3
import os

db_paths = ["appdata.db", "..appdata.db", "../appdata.db"]

for path in db_paths:
    if os.path.exists(path):
        print(f"Migrating {path}...")
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        
        # Check existing columns in health_reports
        cursor.execute("PRAGMA table_info(health_reports)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Existing columns in {path}: {columns}")
        
        new_cols = [
            ("selected_modules_json", "TEXT"),
            ("risk_results_json", "TEXT"),
            ("visual_summary", "TEXT"),
            ("questionnaire_summary", "TEXT"),
            ("lab_findings", "TEXT"),
            ("pdf_path", "TEXT")
        ]

        for col_name, col_type in new_cols:
            if col_name not in columns:
                try:
                    cursor.execute(f"ALTER TABLE health_reports ADD COLUMN {col_name} {col_type}")
                    print(f"Added column {col_name} to {path}")
                except Exception as e:
                    print(f"Error adding {col_name} to {path}: {e}")

        conn.commit()
        conn.close()
