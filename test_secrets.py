import os
from dotenv import load_dotenv

load_dotenv()

secrets_to_check = [
    'SECRET_KEY',
    'EMAIL_ADDRESS',
    'EMAIL_PASSWORD',
    'GOOGLE_CLIENT_ID',
    'GOOGLE_CLIENT_SECRET',
    'GHCLIENT_ID',
    'GHCLIENT_SECRET',
    'STRAVA_CLIENT_ID',
    'STRAVA_CLIENT_SECRET',
]

print("Checking Codespaces Secrets...\n")
print("="*50)

for secret in secrets_to_check:
    value = os.environ.get(secret)
    if value:
        # Show first 10 chars for verification
        display = value[:10] + "..." if len(value) > 10 else value
        print(f"✅ {secret}: {display}")
    else:
        print(f"❌ {secret}: NOT SET")

print("="*50)