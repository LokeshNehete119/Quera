import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import get_db_connection
from dotenv import load_dotenv

load_dotenv()

def run_test():
    conn_string = os.environ.get("APP_DB_URL")
    db_type = "postgres"
    
    print("Testing Postgres connection via get_db_connection...")
    conn = get_db_connection(conn_string, db_type)
    
    with conn.cursor() as cur:
        cur.execute("SELECT 1 as test_col;")
        results = cur.fetchall()
        print(f"Results: {results}")
        
    conn.close()
    print("Postgres test passed.")

if __name__ == "__main__":
    run_test()
