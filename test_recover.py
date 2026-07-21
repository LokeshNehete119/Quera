import requests
import json

url = "https://yupxousqgvyrqndgcqys.supabase.co/auth/v1/recover"
anon_key = "sb_publishable_C-CTdBX1IoTjmQFZ2-rxEA_G6D8sQPe"

headers = {
    "apikey": anon_key,
    "Authorization": f"Bearer {anon_key}",
    "Content-Type": "application/json"
}

data = {
    "email": "testweak@gmail.com"
}

response = requests.post(url, headers=headers, json=data)

print(f"HTTP Status: {response.status_code}")
print("Response Headers:")
for k, v in response.headers.items():
    print(f"  {k}: {v}")
print("\nResponse Body:")
print(response.text)
