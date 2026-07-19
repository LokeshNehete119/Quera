import os
import google.generativeai as genai
from google.generativeai import types
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

pg_schema = """Table: categories_rich
Columns: id (int), name (varchar)

Table: products_rich
Columns: id (int), name (varchar), price (decimal)

Table: suppliers_rich
Columns: id (int), name (varchar)
"""

mysql_schema = pg_schema # Use same schema text to isolate the prompt difference

class SqlResponse(types.Type):
    sql: str

def test_gemini(db_type, schema_str):
    if db_type == "postgres":
        sql_instruct = f"""You are an expert SQL generator for a PostgreSQL database.
Here is the database schema:
{schema_str}

Generate a single valid SELECT query that answers the user's question. 
You may query the tables listed in the schema, or standard PostgreSQL system catalogs (like information_schema) if the user asks metadata questions about the database itself.
If the question is completely unrelated to databases or the schema, generate exactly: SELECT 'IMPOSSIBLE' AS STATUS;"""
    elif db_type == "mysql":
        sql_instruct = f"""You are an expert SQL generator for a MySQL database.
Here is the database schema:
{schema_str}

Generate a single valid SELECT query that answers the user's question. 
CRITICAL MYSQL RULES:
- Quote string literals with single quotes ('). Do not use double quotes.
- Quote identifiers (tables/columns) with backticks (`), NOT double quotes.
- Do not use PostgreSQL-specific syntax or functions.
If the question is completely unrelated to databases or the schema, generate exactly: SELECT 'IMPOSSIBLE' AS STATUS;"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents="count rows of table which has min columns with name",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            system_instruction=sql_instruct,
            temperature=0.0
        ),
    )
    return response.text

print("--- POSTGRES RESPONSE ---")
print(test_gemini("postgres", pg_schema))
print("\n--- MYSQL RESPONSE ---")
print(test_gemini("mysql", mysql_schema))
