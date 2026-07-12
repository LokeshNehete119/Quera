import sys
import os

# Add parent directory to path so we can import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import detect_db_type

test_cases = [
    ("postgresql://user:pass@host/db", "postgres"),
    ("postgres://user:pass@host/db", "postgres"),
    ("mysql://user:pass@host/db", "mysql"),
    ("mysql+pymysql://user:pass@host/db", "mysql")
]

def run_tests():
    print("=" * 60)
    print("DB TYPE DETECTION TEST SUITE")
    print("=" * 60)
    
    passed_all = True
    
    # Test valid connection strings
    for conn_str, expected in test_cases:
        print(f"\nTest Connection String: {conn_str}")
        try:
            detected = detect_db_type(conn_str)
            match = (detected == expected)
            print(f"  Detected DB Type: {detected} {'PASS' if match else 'FAIL'} (Expected: {expected})")
            if not match:
                passed_all = False
        except Exception as e:
            print(f"  FAIL: Raised unexpected exception: {e}")
            passed_all = False

    # Test invalid connection string
    invalid_str = "not-a-real-connection-string"
    print(f"\nTest Connection String: {invalid_str}")
    try:
        detect_db_type(invalid_str)
        print(f"  FAIL: Expected ValueError, but no exception was raised.")
        passed_all = False
    except ValueError as e:
        print(f"  PASS: Raised expected ValueError: {e}")
    except Exception as e:
        print(f"  FAIL: Raised wrong exception type: {type(e).__name__}: {e}")
        passed_all = False
        
    print("\n" + "=" * 60)
    if passed_all:
        print("PASS: ALL TESTS PASSED")
    else:
        print("FAIL: SOME TESTS FAILED")

if __name__ == "__main__":
    run_tests()
