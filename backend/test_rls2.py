from dotenv import load_dotenv
import os
import psycopg2
load_dotenv()
conn = psycopg2.connect(os.environ.get('APP_DB_URL'))
cur = conn.cursor()
cur.execute("SET LOCAL ROLE authenticated;")
cur.execute("SELECT current_user, current_setting('is_superuser');")
print(cur.fetchone())

cur.execute("SELECT * FROM db_connections;")
print(cur.fetchall())
