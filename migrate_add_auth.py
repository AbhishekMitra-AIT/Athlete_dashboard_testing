"""
Migration script to add authentication system tables and columns.
Run this ONCE to upgrade your existing database.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
import os

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///athlete_data.db"
db.init_app(app)

def migrate():
    with app.app_context():
        try:
            print("="*60)
            print("AUTHENTICATION SYSTEM MIGRATION")
            print("="*60)
            
            # Step 1: Create User table
            result = db.session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user'"
            ))
            table_exists = result.fetchone() is not None
            
            if not table_exists:
                print("\n1. Creating 'user' table...")
                db.session.execute(text("""
                    CREATE TABLE user (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email VARCHAR(120) UNIQUE NOT NULL,
                        username VARCHAR(80),
                        password_hash VARCHAR(200),
                        oauth_provider VARCHAR(20),
                        oauth_id VARCHAR(200),
                        email_verified BOOLEAN DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                db.session.commit()
                print("✓ Table 'user' created successfully!")
            else:
                print("\n1. ✓ Table 'user' already exists")
            
            # Step 2: Add user_id column to athlete__data table
            result = db.session.execute(text("PRAGMA table_info(athlete__data)"))
            columns = [row[1] for row in result]
            
            if 'user_id' not in columns:
                print("\n2. Adding 'user_id' column to athlete__data table...")
                db.session.execute(text("ALTER TABLE athlete__data ADD COLUMN user_id INTEGER DEFAULT 1"))
                db.session.commit()
                print("✓ Column 'user_id' added successfully!")
                print("⚠️  Note: Existing records assigned to user_id=1 (default user)")
            else:
                print("\n2. ✓ Column 'user_id' already exists in athlete__data")
            
            # Step 3: Add user_id column to strava_token table (if it exists)
            result = db.session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='strava_token'"
            ))
            strava_table_exists = result.fetchone() is not None
            
            if strava_table_exists:
                result = db.session.execute(text("PRAGMA table_info(strava_token)"))
                columns = [row[1] for row in result]
                
                if 'user_id' not in columns:
                    print("\n3. Adding 'user_id' column to strava_token table...")
                    db.session.execute(text("ALTER TABLE strava_token ADD COLUMN user_id INTEGER DEFAULT 1"))
                    db.session.commit()
                    print("✓ Column 'user_id' added successfully!")
                else:
                    print("\n3. ✓ Column 'user_id' already exists in strava_token")
            else:
                print("\n3. ℹ strava_token table doesn't exist yet (will be created on first Strava connection)")
            
            # Step 4: Create a default user for existing data
            result = db.session.execute(text("SELECT COUNT(*) FROM user"))
            user_count = result.scalar()
            
            if user_count == 0:
                print("\n4. Creating default user for existing data...")
                db.session.execute(text("""
                    INSERT INTO user (id, email, username, email_verified)
                    VALUES (1, 'default@localhost.local', 'Default User', 1)
                """))
                db.session.commit()
                print("✓ Default user created (ID: 1)")
                print("⚠️  Please register a new account and login")
            else:
                print(f"\n4. ✓ Found {user_count} existing user(s)")
            
            # Summary
            print("\n" + "="*60)
            print("MIGRATION COMPLETED SUCCESSFULLY!")
            print("="*60)
            print("\n✅ Your database is now ready for authentication")
            print("\nNext steps:")
            print("1. Set up OAuth credentials (Google/GitHub) in .env file")
            print("2. Configure email settings for verification in .env file")
            print("3. Update your app.py to the new version with auth")
            print("4. Create login.html and register.html templates")
            print("5. Restart your Flask app")
            print("6. Go to http://localhost:5000/login")
            print("\n" + "="*60)
            
        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            db.session.rollback()
            return False
    
    return True

if __name__ == "__main__":
    print("\n⚠️  IMPORTANT: Backup your database before proceeding!")
    print(f"Database location: instance/athlete_data.db")
    
    db_path = "instance/athlete_data.db"
    if not os.path.exists(db_path):
        print(f"\n✗ Database not found at {db_path}")
        print("Please run the app once to create the database first.")
    else:
        response = input("\nDo you want to proceed with the migration? (y/n): ").lower()
        
        if response == 'y':
            print("\nStarting migration...\n")
            success = migrate()
            if not success:
                print("\nMigration failed. Please check the error messages above.")
        else:
            print("\nMigration cancelled.")