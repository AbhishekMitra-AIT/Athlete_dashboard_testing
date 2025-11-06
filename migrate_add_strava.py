"""
Migration script to add strava_id column to existing database
and create the StravaToken table.

Run this ONCE before using the Strava-integrated app.py
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Integer, String, Float, text
import os

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create a temporary app for migration
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///athlete_data.db"
db.init_app(app)

def migrate():
    with app.app_context():
        try:
            print("="*60)
            print("STRAVA INTEGRATION MIGRATION")
            print("="*60)
            
            # Step 1: Check if strava_id column exists in athlete__data table
            result = db.session.execute(text("PRAGMA table_info(athlete__data)"))
            columns = [row[1] for row in result]
            
            if 'strava_id' in columns:
                print("✓ Column 'strava_id' already exists in athlete__data table")
            else:
                print("\n1. Adding 'strava_id' column to athlete__data table...")
                db.session.execute(text("ALTER TABLE athlete__data ADD COLUMN strava_id INTEGER"))
                db.session.commit()
                print("✓ Column 'strava_id' added successfully!")
            
            # Step 2: Check if StravaToken table exists
            result = db.session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='strava_token'"
            ))
            table_exists = result.fetchone() is not None
            
            if table_exists:
                print("✓ Table 'strava_token' already exists")
            else:
                print("\n2. Creating 'strava_token' table...")
                db.session.execute(text("""
                    CREATE TABLE strava_token (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        access_token VARCHAR(500) NOT NULL,
                        refresh_token VARCHAR(500) NOT NULL,
                        expires_at INTEGER NOT NULL,
                        athlete_id INTEGER NOT NULL
                    )
                """))
                db.session.commit()
                print("✓ Table 'strava_token' created successfully!")
            
            # Summary
            print("\n" + "="*60)
            print("MIGRATION COMPLETED SUCCESSFULLY!")
            print("="*60)
            print("\n✅ Your database is now ready for Strava integration")
            print("\nNext steps:")
            print("1. Get Strava API credentials from: https://www.strava.com/settings/api")
            print("2. Add credentials to .env file:")
            print("   STRAVA_CLIENT_ID=your_client_id")
            print("   STRAVA_CLIENT_SECRET=your_client_secret")
            print("   STRAVA_REDIRECT_URI=http://localhost:5000/strava/callback")
            print("3. Run your app: python app.py")
            print("4. Click 'Connect Strava' button in the dashboard")
            print("\n" + "="*60)
            
        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            db.session.rollback()
            return False
    
    return True

if __name__ == "__main__":
    print("\n⚠️  IMPORTANT: Backup your database before proceeding!")
    print(f"Database location: instance/athlete_data.db")
    
    # Check if database exists
    db_path = "instance/athlete_data.db"
    if not os.path.exists(db_path):
        print(f"\n✗ Database not found at {db_path}")
        print("Please make sure the database file exists in the correct location.")
        print("If this is a fresh install, just run app.py first to create the database.")
    else:
        response = input("\nDo you want to proceed with the migration? (y/n): ").lower()
        
        if response == 'y':
            print("\nStarting migration...\n")
            success = migrate()
            if not success:
                print("\nMigration failed. Please check the error messages above.")
        else:
            print("\nMigration cancelled.")