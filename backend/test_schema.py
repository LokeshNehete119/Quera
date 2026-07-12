import psycopg2
conn_str = 'postgresql://postgres.gevurhhgbmxkgbqynfks:LOK123esh456@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres'
conn = psycopg2.connect(conn_str)
cur = conn.cursor()
cur.execute("SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'public' ORDER BY table_name, ordinal_position;")
rows = cur.fetchall()
print(f'Rows: {len(rows)}')
for r in rows[:5]:
    print(r)
