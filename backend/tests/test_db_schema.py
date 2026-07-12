import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import get_db_connection, get_db_schema
from dotenv import load_dotenv

load_dotenv()

def run_test():
    print("=" * 60)
    print("DB SCHEMA DETECTION TEST")
    print("=" * 60)

    # Test MySQL
    try:
        mysql_conn_str = "mysql+pymysql://quera_user:querapassword@localhost:3307/quera_test"
        mysql_conn = get_db_connection(mysql_conn_str, "mysql")
        mysql_schema = get_db_schema(mysql_conn, "mysql")
        mysql_conn.close()
        
        print("\n--- MySQL Schema Output ---")
        if not mysql_schema:
            print("FAIL: MySQL schema is empty!")
        else:
            print(mysql_schema)
    except Exception as e:
        print(f"MySQL Test Failed: {e}")

    # Test Postgres
    try:
        pg_conn_str = os.environ.get("APP_DB_URL")
        pg_conn = get_db_connection(pg_conn_str, "postgres")
        pg_schema = get_db_schema(pg_conn, "postgres")
        pg_conn.close()
        
        print("\n--- Postgres Schema Output ---")
        if not pg_schema:
            print("FAIL: Postgres schema is empty!")
        else:
            print(pg_schema[:500] + "...\n[TRUNCATED FOR BREVITY]")
    except Exception as e:
        print(f"Postgres Test Failed: {e}")

if __name__ == "__main__":
    run_test()
