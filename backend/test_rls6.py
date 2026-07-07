from dotenv import load_dotenv
import os
import psycopg2
load_dotenv()
conn = psycopg2.connect(os.environ.get('APP_DB_URL'))
cur = conn.cursor()
cur.execute("SELECT id, user_id, name FROM db_connections;")
for row in cur.fetchall():
    print(row)
