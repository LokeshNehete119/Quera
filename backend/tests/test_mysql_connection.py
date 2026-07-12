import sys
import os

# Add parent directory to path so we can import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import get_db_connection

def run_test():
    print("=" * 60)
    print("MYSQL CONNECTION TEST")
    print("=" * 60)
    
    conn_string = "mysql+pymysql://quera_user:querapassword@localhost:3307/quera_test"
    db_type = "mysql"
    
    print(f"Testing connection string: {conn_string}")
    try:
        conn = get_db_connection(conn_string, db_type)
        print("PASS: Connection established.")
        
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM products")
            results = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []
            
        print("\nPASS: Query executed.")
        print(f"Columns: {columns}")
        print("Rows:")
        for row in results:
            print(f"  {row}")
            
        conn.close()
    except Exception as e:
        print(f"FAIL: {e}")

if __name__ == "__main__":
    run_test()
