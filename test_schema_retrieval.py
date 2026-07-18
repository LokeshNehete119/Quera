import os
import sys
import pymysql
import psycopg2
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
import main
from main import build_schema_graph, get_relevant_schema, get_db_schema

load_dotenv("backend/.env")

def parse_returned_tables(schema_str: str) -> set:
    tables = set()
    for line in schema_str.split('\n'):
        if line.startswith('Table: '):
            tables.add(line[7:].strip())
    return tables

def main_func():
    print("--- SCHEMA RETRIEVAL EVALUATION ---")
    my_conn = pymysql.connect(
        host="quera-mysql-test",
        port=3306,
        user="quera_user",
        password="querapassword",
        database="quera_test",
        cursorclass=pymysql.cursors.DictCursor
    )
    
    # Create the 9-table schema
    with my_conn.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
        cur.execute("SHOW TABLES")
        for row in cur.fetchall():
            cur.execute(f"DROP TABLE IF EXISTS {row['Tables_in_quera_test']}")
        cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
            
        cur.execute("CREATE TABLE users_rich (id INT PRIMARY KEY, name VARCHAR(100), email VARCHAR(100));")
        cur.execute("CREATE TABLE products_rich (id INT PRIMARY KEY, name VARCHAR(100), price DECIMAL);")
        cur.execute("CREATE TABLE orders_rich (id INT PRIMARY KEY, user_id INT, order_date DATE, FOREIGN KEY (user_id) REFERENCES users_rich(id));")
        cur.execute("CREATE TABLE order_items_rich (order_id INT, product_id INT, quantity INT, FOREIGN KEY (order_id) REFERENCES orders_rich(id), FOREIGN KEY (product_id) REFERENCES products_rich(id));")
        cur.execute("CREATE TABLE reviews_rich (id INT PRIMARY KEY, product_id INT, rating INT, comment TEXT, FOREIGN KEY (product_id) REFERENCES products_rich(id));")
        cur.execute("CREATE TABLE suppliers_rich (id INT PRIMARY KEY, name VARCHAR(100));")
        cur.execute("CREATE TABLE categories_rich (id INT PRIMARY KEY, name VARCHAR(100));")
        cur.execute("CREATE TABLE warehouses_rich (id INT PRIMARY KEY, location VARCHAR(100));")
        cur.execute("CREATE TABLE shipments_rich (id INT PRIMARY KEY, status VARCHAR(100));")
    my_conn.commit()

    my_graph = build_schema_graph(my_conn, "mysql")
    full_schema_str = get_db_schema(my_conn, "mysql")
    all_tables = parse_returned_tables(full_schema_str)
    
    test_cases = [
        {
            "query": "What are the names of all suppliers_rich?",
            "expected": {"suppliers_rich"}
        },
        {
            "query": "Show all products_rich and their price",
            "expected": {"products_rich"}
        },
        {
            "query": "List all orders_rich placed by each users_rich",
            "expected": {"orders_rich", "users_rich"}
        },
        {
            "query": "Show me the comment and rating for products_rich",
            "expected": {"reviews_rich", "products_rich"}
        },
        {
            "query": "List quantity of order_items_rich in orders_rich for users_rich",
            "expected": {"order_items_rich", "orders_rich", "users_rich"}
        },
        {
            "query": "Which users_rich bought the most expensive products_rich last month in their orders_rich",
            "expected": {"users_rich", "orders_rich", "order_items_rich", "products_rich"}
        },
        {
            "query": "What are the locations of warehouses_rich and status of shipments_rich?",
            "expected": {"warehouses_rich", "shipments_rich"}
        },
        {
            "query": "Find the email of the person who placed this order_date",
            "expected": {"users_rich", "orders_rich"}
        },
        {
            "query": "Show me everything in the database",
            "expected": all_tables
        },
        {
            "query": "Can you summarize our business metrics?",
            "expected": all_tables
        },
        {
            "query": "who has spent the most money with us",
            "expected": {"users_rich", "orders_rich", "order_items_rich", "products_rich"}
        },
        {
            "query": "what shipments haven't arrived yet",
            "expected": {"shipments_rich"}
        },
        {
            "query": "which item never got reviewed",
            "expected": {"products_rich", "reviews_rich"}
        },
        {
            "query": "who signed up but never ordered anything",
            "expected": {"users_rich", "orders_rich"}
        },
        {
            "query": "what's low in stock at our storage sites",
            "expected": {"products_rich", "warehouses_rich"}
        },
        {
            "query": "Show me the status of the people",
            "expected": {"users_rich"}
        }
    ]
    
    print("\n" + "="*50)
    print(f"--- RUNNING FINAL CONFIG (MARGIN_30 + KEYWORD GUARD) ---")
    print("="*50)
    
    total_recall = 0.0
    total_precision = 0.0
    
    for i, tc in enumerate(test_cases, 1):
        q = tc["query"]
        expected = tc["expected"]
        
        filtered_str = get_relevant_schema(q, full_schema_str, my_graph, "mysql")
        returned = parse_returned_tables(filtered_str)
        
        # Calculate Recall and Precision
        true_positives = len(expected.intersection(returned))
        recall = true_positives / len(expected) if expected else 1.0
        precision = true_positives / len(returned) if returned else 1.0
        
        total_recall += recall
        total_precision += precision
        
        status = "PASS" if recall == 1.0 else "FAIL"
        
        print(f"\nTest Case {i}: {status}")
        print(f"  Query: '{q}'")
        print(f"  Expected: {expected}")
        print(f"  Returned: {returned}")
        print(f"  Recall: {recall:.2%} | Precision: {precision:.2%}")
        
    avg_recall = total_recall / len(test_cases)
    avg_precision = total_precision / len(test_cases)
    
    print("\n" + "-"*40)
    print(f"OVERALL METRICS - FINAL CONFIG (16 CASES)")
    print("-"*40)
    print(f"Average Recall:    {avg_recall:.2%}")
    print(f"Average Precision: {avg_precision:.2%}")
    print("-"*40)
    
    my_conn.close()

if __name__ == "__main__":
    main_func()
