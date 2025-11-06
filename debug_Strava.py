"""
Quick debug script to check Strava configuration
Run this to verify your setup
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String
import os
from dotenv import load_dotenv

load_dotenv()

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///athlete_data.db"
db.init_app(app)

class StravaToken(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_token: Mapped[str] = mapped_column(String(500), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(500), nullable=False)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)
    athlete_id: Mapped[int] = mapped_column(Integer, nullable=False)

print("="*60)
print("STRAVA INTEGRATION DEBUG")
print("="*60)

# Check environment variables
print("\n1. Environment Variables:")
strava_client_id = os.environ.get("STRAVA_CLIENT_ID")
strava_client_secret = os.environ.get("STRAVA_CLIENT_SECRET")
strava_redirect_uri = os.environ.get("STRAVA_REDIRECT_URI")

if strava_client_id:
    print(f"   ✓ STRAVA_CLIENT_ID: {strava_client_id[:10]}... (found)")
else:
    print("   ✗ STRAVA_CLIENT_ID: NOT SET")

if strava_client_secret:
    print(f"   ✓ STRAVA_CLIENT_SECRET: {strava_client_secret[:10]}... (found)")
else:
    print("   ✗ STRAVA_CLIENT_SECRET: NOT SET")

if strava_redirect_uri:
    print(f"   ✓ STRAVA_REDIRECT_URI: {strava_redirect_uri}")
else:
    print("   ✗ STRAVA_REDIRECT_URI: NOT SET (will use default)")

# Check database
print("\n2. Database Check:")
with app.app_context():
    try:
        token_count = db.session.query(StravaToken).count()
        if token_count > 0:
            print(f"   ✓ Strava tokens found: {token_count}")
            token = db.session.query(StravaToken).first()
            print(f"   ✓ Connected Athlete ID: {token.athlete_id}")
        else:
            print("   ℹ No Strava tokens found (not connected yet)")
    except Exception as e:
        print(f"   ✗ Database error: {e}")

# Check .env file
print("\n3. .env File Check:")
if os.path.exists(".env"):
    print("   ✓ .env file exists")
    with open(".env", "r") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        print(f"   ✓ Contains {len(lines)} configuration line(s)")
else:
    print("   ✗ .env file NOT FOUND")
    print("   → Create a .env file with your Strava credentials")

print("\n" + "="*60)
print("RECOMMENDATIONS:")
print("="*60)

if not strava_client_id or not strava_client_secret:
    print("\n⚠️  Strava credentials not configured!")
    print("\nTo fix:")
    print("1. Go to: https://www.strava.com/settings/api")
    print("2. Create an API application")
    print("3. Create a .env file with:")
    print("   STRAVA_CLIENT_ID=your_client_id")
    print("   STRAVA_CLIENT_SECRET=your_client_secret")
    print("   STRAVA_REDIRECT_URI=http://localhost:5000/strava/callback")
else:
    print("\n✅ Configuration looks good!")
    print("\nIf you still don't see the button:")
    print("1. Restart your Flask app")
    print("2. Clear browser cache (Ctrl+Shift+R)")
    print("3. Check browser console for errors (F12)")

print("\n" + "="*60)