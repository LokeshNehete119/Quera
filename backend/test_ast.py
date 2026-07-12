import sqlglot
from sqlglot import exp

print("Testing TRUNCATE:")
try:
    parsed_truncate = sqlglot.parse_one("TRUNCATE TABLE logs", read="postgres")
    print(f"TRUNCATE Class: {type(parsed_truncate)}")
except Exception as e:
    print(f"Error parsing TRUNCATE: {e}")

print("\nTesting CTE DELETE:")
try:
    parsed_cte = sqlglot.parse_one("WITH x AS (DELETE FROM users RETURNING id) SELECT * FROM x", read="postgres")
    print(f"CTE Class: {type(parsed_cte)}")
    print(f"Is top-level Select? {isinstance(parsed_cte, exp.Select)}")
    deletes = list(parsed_cte.find_all(exp.Delete))
    print(f"Found {len(deletes)} Delete nodes inside!")
except Exception as e:
    print(f"Error parsing CTE: {e}")
