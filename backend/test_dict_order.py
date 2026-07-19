import pymysql
from pymysql.cursors import DictCursor

conn = pymysql.connect(
    host="localhost",
    user="quera_user",
    password="querapassword",
    database="quera_test",
    port=3307,
    cursorclass=DictCursor
)
schema_query = """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
    ORDER BY table_name, ordinal_position;
"""
with conn.cursor() as cur:
    cur.execute(schema_query)
    rows = cur.fetchall()

print("First row dict:", rows[0])
print("First row values:", list(rows[0].values()))
