import os
import sys
import pymysql
import tiktoken
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__)))
from main import build_schema_graph, get_relevant_schema, get_db_schema

load_dotenv(".env")

def parse_returned_tables(schema_str: str) -> set:
    tables = set()
    for line in schema_str.split('\n'):
        if line.startswith('Table: '):
            tables.add(line[7:].strip())
    return tables

def main_func():
    enc = tiktoken.get_encoding("cl100k_base")
    print("--- TOKEN REDUCTION EVALUATION (tiktoken cl100k_base) ---")
    
    my_conn = pymysql.connect(
        host="quera-mysql-test",
        port=3306,
        user="quera_user",
        password="querapassword",
        database="quera_test",
        cursorclass=pymysql.cursors.DictCursor
    )
    
    my_graph = build_schema_graph(my_conn, "mysql")
    full_schema_str = get_db_schema(my_conn, "mysql")
    all_tables = parse_returned_tables(full_schema_str)
    full_tokens = len(enc.encode(full_schema_str))
    
    test_cases = [
        "What are the names of all suppliers_rich?",
        "Show all products_rich and their price",
        "List all orders_rich placed by each users_rich",
        "Show me the comment and rating for products_rich",
        "List quantity of order_items_rich in orders_rich for users_rich",
        "Which users_rich bought the most expensive products_rich last month in their orders_rich",
        "What are the locations of warehouses_rich and status of shipments_rich?",
        "Find the email of the person who placed this order_date",
        "Show me everything in the database",
        "Can you summarize our business metrics?",
        "who has spent the most money with us",
        "what shipments haven't arrived yet",
        "which item never got reviewed",
        "who signed up but never ordered anything",
        "what's low in stock at our storage sites",
        "Show me the status of the people",
        "tell me about my db",
        "tell me about my database",
        "what's in my db"
    ]
    
    all_reductions = []
    narrowed_reductions = []
    
    print(f"Full Schema Tokens: {full_tokens}")
    print("="*60)
    
    for i, q in enumerate(test_cases, 1):
        filtered_str = get_relevant_schema(q, full_schema_str, my_graph, "mysql")
        returned_tables = parse_returned_tables(filtered_str)
        
        filtered_tokens = len(enc.encode(filtered_str))
        reduction = (full_tokens - filtered_tokens) / full_tokens
        
        is_narrowed = len(returned_tables) < len(all_tables)
        
        all_reductions.append(reduction)
        if is_narrowed:
            narrowed_reductions.append(reduction)
            
        print(f"Test Case {i}: '{q}'")
        print(f"  Narrowed? {'Yes' if is_narrowed else 'No'} ({len(returned_tables)}/{len(all_tables)} tables)")
        print(f"  Tokens: {filtered_tokens} / {full_tokens}")
        print(f"  Reduction: {reduction:.2%}")
        print("-" * 40)
        
    avg_all = sum(all_reductions) / len(all_reductions) if all_reductions else 0
    avg_narrowed = sum(narrowed_reductions) / len(narrowed_reductions) if narrowed_reductions else 0
    
    print("\n" + "="*60)
    print("OVERALL TOKEN REDUCTION SUMMARY")
    print("="*60)
    print(f"Average reduction (ALL 16 cases): {avg_all:.2%}")
    print(f"Average reduction (ONLY genuine narrowed cases): {avg_narrowed:.2%} ({len(narrowed_reductions)} cases)")

    my_conn.close()

if __name__ == "__main__":
    main_func()
