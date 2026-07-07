from dotenv import load_dotenv
import os
import psycopg2
load_dotenv()
conn = psycopg2.connect(os.environ.get('APP_DB_URL'))
cur = conn.cursor()
cur.execute("SELECT tablename, policyname, roles, qual, with_check FROM pg_policies WHERE tablename IN ('db_connections', 'chats', 'messages');")
policies = cur.fetchall()
print("POLICIES:")
for p in policies:
    print(p)

cur.execute("SELECT relname, relrowsecurity FROM pg_class WHERE relname IN ('db_connections', 'chats', 'messages');")
tables = cur.fetchall()
print("\nTABLE SECURITY:")
for t in tables:
    print(t)
