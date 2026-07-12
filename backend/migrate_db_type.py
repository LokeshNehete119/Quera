import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

APP_DB_URL = os.environ.get("APP_DB_URL")
if not APP_DB_URL:
    print("Error: APP_DB_URL not found in environment.")
    sys.exit(1)

try:
    conn = psycopg2.connect(APP_DB_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        print("Running migration...")
        cur.execute("ALTER TABLE db_connections ADD COLUMN IF NOT EXISTS db_type VARCHAR(20) NOT NULL DEFAULT 'postgres';")
        print("Migration successful: db_type column added.")
        
        # Verify
        cur.execute("SELECT id, name, db_type FROM db_connections LIMIT 5;")
        rows = cur.fetchall()
        print("\nVerification (First 5 rows):")
        for row in rows:
            print(f"ID: {row[0]}, Name: {row[1]}, DB_TYPE: {row[2]}")
            
    conn.close()
except Exception as e:
    print(f"Migration failed: {e}")
    sys.exit(1)
