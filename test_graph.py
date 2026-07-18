import os
import sys
import pymysql
import psycopg2
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
import main
from main import build_schema_graph, get_neighbor_tables, get_relevant_schema, get_db_schema

load_dotenv("backend/.env")

def main_func():
    print("--- MYSQL RICH SCHEMA RETRIEVAL TEST ---")
    my_conn = pymysql.connect(
        host="quera-mysql-test",
        port=3306,
        user="quera_user",
        password="querapassword",
        database="quera_test",
        cursorclass=pymysql.cursors.DictCursor
    )
    
    # Create richer schema (5 tables, <= 8 cutoff)
    with my_conn.cursor() as cur:
        # Drop everything to ensure only the test tables exist in the schema
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
    my_conn.commit()

    my_graph_small = build_schema_graph(my_conn, "mysql")
    full_schema_str_small = get_db_schema(my_conn, "mysql")
    
    queries = [
        "show all products_rich and their price",
        "which users_rich bought the most expensive products_rich last month in their orders_rich",
        "show me everything"
    ]
    
    print("\n--- SCHEMA (5 TABLES, <= 8) ---")
    for q in queries:
        print(f"\nQUERY: '{q}'")
        _ = get_relevant_schema(q, full_schema_str_small, my_graph_small, "mysql")
        
    # Extend schema to > 8 tables (9 tables total)
    with my_conn.cursor() as cur:
        cur.execute("CREATE TABLE suppliers_rich (id INT PRIMARY KEY, name VARCHAR(100));")
        cur.execute("CREATE TABLE categories_rich (id INT PRIMARY KEY, name VARCHAR(100));")
        cur.execute("CREATE TABLE warehouses_rich (id INT PRIMARY KEY, location VARCHAR(100));")
        cur.execute("CREATE TABLE shipments_rich (id INT PRIMARY KEY, status VARCHAR(100));")
    my_conn.commit()

    my_graph_large = build_schema_graph(my_conn, "mysql")
    full_schema_str_large = get_db_schema(my_conn, "mysql")
    
    print("\n--- SCHEMA (9 TABLES, > 8) ---")
    for q in queries:
        print(f"\nQUERY: '{q}'")
        _ = get_relevant_schema(q, full_schema_str_large, my_graph_large, "mysql")
    
    my_conn.close()

if __name__ == "__main__":
    main_func()
