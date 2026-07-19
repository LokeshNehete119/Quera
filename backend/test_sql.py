import sqlglot
from sqlglot import exp

def is_safe_select_query(query: str, db_type: str = "postgres") -> bool:
    try:
        parsed = sqlglot.parse(query, read=db_type)
    except Exception:
        return False
        
    if len(parsed) != 1 or parsed[0] is None:
        return False
        
    stmt = parsed[0]
    if not isinstance(stmt, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        return False
        
    # Writable CTE / Nested Statement Check
    destructive_nodes = list(stmt.find_all(
        exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command, exp.TruncateTable
    ))
    if destructive_nodes:
        return False
        
    return True

print("Test 1 (UNION ALL):", is_safe_select_query("SELECT 'orders' UNION ALL SELECT 'products'"))
print("Test 2 (Stacked):", is_safe_select_query("SELECT 1; DROP TABLE users;"))
print("Test 3 (CTE):", is_safe_select_query("WITH a AS (DELETE FROM users RETURNING id) SELECT * FROM a"))
