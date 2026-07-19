import pymysql
import psycopg2
from psycopg2.extras import RealDictCursor
from pymysql.cursors import DictCursor
import os

def get_pg_schema():
    conn = psycopg2.connect("postgresql://postgres.yupxousqgvyrqndgcqys:123asd78IJFPE@aws-1-ap-south-1.pooler.supabase.com:5432/postgres", cursor_factory=RealDictCursor)
    schema_query = """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """
    with conn.cursor() as cur:
        cur.execute(schema_query)
        rows = cur.fetchall()
    conn.close()
    
    tables = {}
    for row in rows:
        t_name, c_name, d_type = list(row.values())
        if t_name not in tables:
            tables[t_name] = []
        tables[t_name].append(f"{c_name} ({d_type})")
        
    schema_str = ""
    for table, columns in tables.items():
        schema_str += f"Table: {table}\nColumns: {', '.join(columns)}\n\n"
    return schema_str

def get_mysql_schema():
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
    conn.close()
    
    tables = {}
    for row in rows:
        t_name, c_name, d_type = list(row.values())
        if t_name not in tables:
            tables[t_name] = []
        tables[t_name].append(f"{c_name} ({d_type})")
        
    schema_str = ""
    for table, columns in tables.items():
        schema_str += f"Table: {table}\nColumns: {', '.join(columns)}\n\n"
    return schema_str

if __name__ == "__main__":
    print("=== POSTGRES SCHEMA ===")
    print(get_pg_schema())
    print("=== MYSQL SCHEMA ===")
    print(get_mysql_schema())
