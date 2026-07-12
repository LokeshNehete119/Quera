import sqlglot

print("--- TRUNCATE ---")
parsed_truncate = sqlglot.parse_one("TRUNCATE TABLE logs", read="postgres")
print(type(parsed_truncate))
print(parsed_truncate)

print("\n--- DROP TABLE ---")
parsed_drop = sqlglot.parse_one("DROP TABLE users", read="postgres")
print(type(parsed_drop))
print(parsed_drop)
