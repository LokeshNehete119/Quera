import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import is_safe_select_query, is_highly_destructive

test_cases = [
    {
        "sql": "SELECT * FROM users",
        "expected_read": True,
        "expected_write": False,
        "desc": "Safe SELECT"
    },
    {
        "sql": "SELECT * FROM users WHERE id = 1",
        "expected_read": True,
        "expected_write": False,
        "desc": "SELECT with WHERE"
    },
    {
        "sql": "SELECT 1; DROP TABLE users;",
        "expected_read": False,
        "expected_write": True,
        "desc": "Stacked query (read context)"
    },
    {
        "sql": "WITH x AS (DELETE FROM users RETURNING id) SELECT * FROM x",
        "expected_read": False,
        "expected_write": False,
        "desc": "Writable CTE"
    },
    {
        "sql": "DELETE FROM users",
        "expected_read": False,
        "expected_write": True,
        "desc": "DELETE without WHERE"
    },
    {
        "sql": "DELETE FROM users WHERE id = 1",
        "expected_read": False,
        "expected_write": False,
        "desc": "DELETE with WHERE"
    },
    {
        "sql": "UPDATE users SET role = 'admin'",
        "expected_read": False,
        "expected_write": True,
        "desc": "UPDATE without WHERE"
    },
    {
        "sql": "DROP TABLE users",
        "expected_read": False,
        "expected_write": True,
        "desc": "DROP TABLE"
    },
    {
        "sql": "TRUNCATE TABLE logs",
        "expected_read": False,
        "expected_write": True,
        "desc": "TRUNCATE"
    },
    {
        "sql": "UPDATE users SET role='admin'; DROP TABLE audit_log;",
        "expected_read": False,
        "expected_write": True,
        "desc": "Stacked write query"
    },
    {
        "sql": "SELECT * FROM &&&& syntax error",
        "expected_read": False,
        "expected_write": True,
        "desc": "Unparseable string"
    }
]

mysql_specific_cases = [
    {
        "sql": "CREATE TABLE notes (id INT AUTO_INCREMENT PRIMARY KEY, title VARCHAR(255))",
        "expected_read": False,
        "expected_write": False, # CREATE is not Drop/Truncate/Delete/Update without WHERE
        "desc": "MySQL CREATE TABLE AUTO_INCREMENT"
    },
    {
        "sql": "SELECT `id` FROM `users` WHERE `name` = 'test'",
        "expected_read": True,
        "expected_write": False,
        "desc": "MySQL Backticks SELECT"
    }
]

def run_tests():
    print("=" * 60)
    print("SQL SAFETY TEST SUITE (MULTI-DIALECT)")
    print("=" * 60)
    
    passed_all = True
    
    dialects = ["postgres", "mysql"]
    
    for dialect in dialects:
        print(f"\n[{dialect.upper()} DIALECT]")
        cases = test_cases + (mysql_specific_cases if dialect == "mysql" else [])
        
        for tc in cases:
            sql = tc["sql"]
            print(f"\n  Test: {tc['desc']}")
            print(f"  SQL:  {sql}")
            
            # Test Read Path
            is_safe_read = is_safe_select_query(sql, dialect)
            read_match = (is_safe_read == tc["expected_read"])
            print(f"    Read Path (Safe Select?): {is_safe_read} {'PASS' if read_match else 'FAIL'} (Expected {tc['expected_read']})")
            
            # Test Write Path
            is_destructive_write = is_highly_destructive(sql, dialect)
            write_match = (is_destructive_write == tc["expected_write"])
            print(f"    Write Path (Destructive?): {is_destructive_write} {'PASS' if write_match else 'FAIL'} (Expected {tc['expected_write']})")
            
            if not read_match or not write_match:
                passed_all = False
                
    print("\n" + "=" * 60)
    if passed_all:
        print("PASS: ALL TESTS PASSED FOR ALL DIALECTS")
    else:
        print("FAIL: SOME TESTS FAILED")

if __name__ == "__main__":
    run_tests()
