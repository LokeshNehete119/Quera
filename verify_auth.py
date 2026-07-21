import os
import psycopg2
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv("backend/.env")
load_dotenv("frontend/.env.local")

db_url = os.environ.get("APP_DB_URL")
supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
supabase_key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")

def check_identities():
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT u.email, i.provider, i.identity_data FROM auth.users u JOIN auth.identities i ON u.id = i.user_id WHERE u.email = 'lokesh.hnehete@gmail.com'")
        rows = cur.fetchall()
        print("\n=== Current auth.identities for lokesh.hnehete@gmail.com ===")
        if not rows:
            print("No identities found or user doesn't exist.")
        for row in rows:
            print(f"Email: {row[0]}, Provider: {row[1]}")
        cur.close()
        conn.close()
    except Exception as e:
        print("Error checking DB:", e)

def test_login(email, password):
    supabase: Client = create_client(supabase_url, supabase_key)
    print(f"\n=== Testing Sign-in for {email} ===")
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.user:
            print("SUCCESS! User signed in.")
            print("User ID:", response.user.id)
            print("Email:", response.user.email)
            print("Providers:", response.user.app_metadata.get("providers", []))
        else:
            print("FAILED! No user returned.")
    except Exception as e:
        print("FAILED! Sign-in error:", str(e))

if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    
    if action == "check":
        check_identities()
    elif action == "test":
        password = sys.argv[2] if len(sys.argv) > 2 else ""
        test_login("lokesh.hnehete@gmail.com", password)
