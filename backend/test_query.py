import os
import json
import pymysql
import psycopg2
from psycopg2.extras import RealDictCursor
from google import genai
from google.genai import types
from main import get_db_schema, SqlResponse
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def test_db_chat(db_type: str, message: str):
    print(f"\n{'='*50}\nTESTING {db_type.upper()}: '{message}'\n{'='*50}")
    
    if db_type == "postgres":
        conn = psycopg2.connect("postgresql://postgres.yupxousqgvyrqndgcqys:123asd78IJFPE@aws-1-ap-south-1.pooler.supabase.com:5432/postgres", cursor_factory=RealDictCursor)
        schema_str = get_db_schema(conn, "postgres")
        sql_instruct = f"""You are an expert SQL generator for a PostgreSQL database.
Here is the database schema:
{schema_str}

Generate a single valid SELECT query that answers the user's question. 
You may query the tables listed in the schema, or standard PostgreSQL system catalogs (like information_schema) if the user asks metadata questions about the database itself.
If the question is completely unrelated to databases or the schema, generate exactly: SELECT 'IMPOSSIBLE' AS STATUS;"""
    else:
        conn = pymysql.connect(
            host="quera-mysql-test",
            user="quera_user",
            password="querapassword",
            database="quera_test",
            port=3306,
            cursorclass=pymysql.cursors.DictCursor
        )
        schema_str = get_db_schema(conn, "mysql")
        sql_instruct = f"""You are an expert SQL generator for a MySQL database.
Here is the database schema:
{schema_str}

Generate a single valid SELECT query that answers the user's question. 
You may query the tables listed in the schema, or standard MySQL system catalogs (like information_schema) if the user asks metadata questions about the database itself.
CRITICAL MYSQL RULES:
- Quote string literals with single quotes ('). Do not use double quotes.
- Quote identifiers (tables/columns) with backticks (`), NOT double quotes.
- Do not use PostgreSQL-specific syntax or functions.
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
        
    print(f"EXTRACTED SQL:\n{sql}\n")
    
    if sql and sql != "SELECT 'IMPOSSIBLE' AS STATUS;":
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                res = cur.fetchall()
            print(f"EXECUTION RESULT: {res}")
        except Exception as e:
            print(f"EXECUTION ERROR: {e}")
            
    conn.close()

if __name__ == "__main__":
    test_db_chat("mysql", "count number of tables with more than 2 columns")
    test_db_chat("postgres", "count number of tables with more than 2 columns")
