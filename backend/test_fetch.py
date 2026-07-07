from dotenv import load_dotenv
import os
import psycopg2
load_dotenv()
conn = psycopg2.connect(os.environ.get('APP_DB_URL'))
cur = conn.cursor()
user_id = '60a9761a-f96f-4fe1-b1f9-8fb5aa82e23e' # Main account user_id from previous session
cur.execute("SELECT id, name, created_at FROM db_connections WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
print("Main account connections:", cur.fetchall())
