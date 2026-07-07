from dotenv import load_dotenv
import os
import psycopg2
import json
load_dotenv()
conn = psycopg2.connect(os.environ.get('APP_DB_URL'))
with conn.cursor() as cur:
    cur.execute("SET LOCAL ROLE authenticated;")
    claim_json = json.dumps({"sub": '11111111-1111-1111-1111-111111111111', "role": "authenticated"})
    cur.execute("SET LOCAL request.jwt.claims = %s;", (claim_json,))

with conn.cursor() as cur:
    cur.execute("SELECT current_user, current_setting('request.jwt.claims', true);")
    print("Same transaction:", cur.fetchone())
    
conn.commit()

with conn.cursor() as cur:
    cur.execute("SELECT current_user, current_setting('request.jwt.claims', true);")
    print("After commit:", cur.fetchone())

