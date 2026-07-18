import os
import json
from google import genai
from google.genai import types
import pymysql

# Import from main.py
import sys
sys.path.append("/app")
from main import (
    get_db_schema, 
    build_schema_graph, 
    get_relevant_schema, 
    schema_graphs_cache,
    SqlResponse,
    is_safe_select_query
)

def test_live_chat(message: str, conn_string: str, conn_id: str):
    print(f"\n{'='*50}\nTESTING LIVE MESSAGE: '{message}'\n{'='*50}")
    
    # Simulate DB connection
    user_conn = pymysql.connect(
        host="quera-mysql-test",
        port=3306,
        user="quera_user",
        password="querapassword",
        database="quera_test",
        cursorclass=pymysql.cursors.DictCursor
    )
    db_type = "mysql"
    
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    # 1. Get full schema
    full_schema_str = get_db_schema(user_conn, db_type)
    
    # 2. Build or retrieve graph
    if conn_id not in schema_graphs_cache:
        schema_graphs_cache[conn_id] = build_schema_graph(user_conn, db_type)
        print(f"[SCHEMA CACHE] Built and cached schema graph for connection {conn_id}")
        
    schema_graph = schema_graphs_cache[conn_id]
    
    # 3. Filter schema
    schema_str = get_relevant_schema(message, full_schema_str, schema_graph, db_type)
    
    # 4. Generate SQL
    sql_instruct = f"""You are an expert SQL generator for a MySQL database.
Here is the database schema:
{schema_str}

Generate a single valid SELECT query that answers the user's question. 
CRITICAL MYSQL RULES:
- Quote string literals with single quotes ('). Do not use double quotes.
- Quote identifiers (tables/columns) with backticks (`), NOT double quotes.
- Do not use PostgreSQL-specific syntax or functions.
If the question is completely unrelated to databases or the schema, generate exactly: SELECT 'IMPOSSIBLE' AS STATUS;"""

    sql_response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=message,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SqlResponse,
            system_instruction=sql_instruct,
            temperature=0.0
        ),
    )
    
    sql_data = json.loads(sql_response.text)
    raw_sql = sql_data.get("sql", "")
    
    print(f"\nGenerated SQL:\n{raw_sql}\n")
    
    if raw_sql.strip().upper() == "SELECT 'IMPOSSIBLE' AS STATUS;":
        print("Result: IMPOSSIBLE")
        user_conn.close()
        return
        
    if not is_safe_select_query(raw_sql, db_type):
        print("Result: Security Error")
        user_conn.close()
        return
        
    with user_conn.cursor() as cur:
        try:
            cur.execute(raw_sql)
            results = cur.fetchall()
            print(f"Execution Success! Retrieved {len(results)} rows.")
            if len(results) > 0:
                print(f"Returned rows: {results}")
        except Exception as e:
            print(f"Execution Failed: {e}")
            
    user_conn.close()

if __name__ == "__main__":
    conn_string = "mysql://quera_user:querapassword@quera-mysql-test:3306/quera_test"
    conn_id = "test-conn-123"
    
    test_live_chat("Show all products_rich and their price", conn_string, conn_id)
    test_live_chat("Which users_rich bought the most expensive products_rich last month in their orders_rich", conn_string, conn_id)
    test_live_chat("Show me everything in the database", conn_string, conn_id)
