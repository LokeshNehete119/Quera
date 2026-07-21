import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv("backend/.env")
load_dotenv("frontend/.env.local")

supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
supabase_key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")

def test_signup(email, password):
    supabase: Client = create_client(supabase_url, supabase_key)
    print(f"\n=== Testing Sign-up for {email} ===")
    print(f"Password being tested: {password}")
    try:
        response = supabase.auth.sign_up({"email": email, "password": password})
        if response.user:
            print("SUCCESS! User signed up.")
            print("User ID:", response.user.id)
            print("Email:", response.user.email)
        else:
            print("FAILED! No user returned. Check configuration or limits.")
    except Exception as e:
        print("FAILED! Supabase Error:")
        print(str(e))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_signup.py <email> <password>")
        sys.exit(1)
    
    email_to_test = sys.argv[1]
    password_to_test = sys.argv[2]
    
    test_signup(email_to_test, password_to_test)
