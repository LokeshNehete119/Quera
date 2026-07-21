import os
import json
import pymysql
from google import genai
from google.genai import types
from main import get_db_schema, SqlResponse
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def test_mysql_chat(message: str):
    # Connect to local docker MySQL test db
    conn = pymysql.connect(
        host="quera-mysql-test",
        user="quera_user",
        password="querapassword",
        database="quera_test",
        port=3306,
        cursorclass=pymysql.cursors.DictCursor
    )
    msg_lower = message.lower()
    
    INTENT_GUARD_KEYWORDS = ["db", "database", "table", "schema", "column", "data", "sql"]
    WRITE_VERBS = ["delete", "drop", "create", "insert", "update", "remove", "rename", "truncate", "assign", "set", "replace", "archive", "restore", "fill", "make"]
    CASUAL_PHRASES = ["explain", "suggest", "how to", "what is a ", "help me", "change the table"]
    SCHEMA_BROAD_INTENT_KEYWORDS = ["everything", "all data", "my db", "my database", "what's in", "tell me about", "entire database", "summarize", "overview"]
    
    has_kw = any(kw in msg_lower for kw in INTENT_GUARD_KEYWORDS)
    has_write = any(wv in msg_lower for wv in WRITE_VERBS)
    has_casual = any(cp in msg_lower for cp in CASUAL_PHRASES)
    
    if has_kw and not has_write and not has_casual:
        category = "read"
        print(f"[INTENT CLASSIFIER] Message: '{message}' -> Forced Category: {category} (Source: Keyword Guard)")
    else:
        category = "casual" # Simulate misclassification for this specific query
    
    if any(kw in msg_lower for kw in SCHEMA_BROAD_INTENT_KEYWORDS):
        print(f"[SCHEMA RETRIEVAL] Fallback: Broad intent keyword detected in query. Returning full schema.")
        schema_str = get_db_schema(conn, "mysql")
    else:
        schema_str = "PARTIAL_SCHEMA_MOCK"
    
    if category == "casual":
        print("Final Response: I don't have direct access to your personal systems.")
        return
        
    sql_instruct = f"""You are an expert SQL generator for a MySQL database.
Here is the database schema:
{schema_str}

Generate a single valid SELECT query that answers the user's question. 
You may query the tables listed in the schema, or standard MySQL system catalogs (like information_schema) if the user asks metadata questions about the database itself.
CRITICAL MYSQL RULES:
- Quote string literals with single quotes ('). Do not use double quotes.
- Quote identifiers (tables/columns) with backticks (`), NOT double quotes.
- Do not use PostgreSQL-specific syntax or functions.
- If querying information_schema, you MUST filter by table_schema = DATABASE() to avoid returning internal system tables.
If the question is completely unrelated to databases or the schema, generate exactly: SELECT 'IMPOSSIBLE' AS STATUS;"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=message,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SqlResponse,
            system_instruction=sql_instruct,
            temperature=0.0
        ),
    )
    
    raw_output = response.text
    try:
        sql = json.loads(raw_output).get("sql", "")
    except:
        sql = "Parse error"
        
    print(f"\nQUERY: {message}")
    print(f"RAW OUTPUT: {raw_output.strip()}")
    print(f"EXTRACTED SQL: {sql}")
    
    # Run the SQL against the DB if it's not impossible
    if sql and sql != "SELECT 'IMPOSSIBLE' AS STATUS;":
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                res = cur.fetchall()
            print(f"EXECUTION RESULT: {res[:2]} {'(truncated)' if len(res)>2 else ''}")
        except Exception as e:
            print(f"EXECUTION ERROR: {e}")
            
    conn.close()

if __name__ == "__main__":
    test_mysql_chat("tell me about my db")
