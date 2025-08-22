#!/usr/bin/env python3
"""
Database initialization script for Maths Generator App
Run this script to create the database and tables
"""

import os
import sys
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import User, UserSession, Performance, QuestionHistory

def init_database():
    """Initialize the database and create all tables"""
    with app.app_context():
        print("Creating database tables...")
        
        # Create all tables
        db.create_all()
        
        print("✅ Database tables created successfully!")
        print(f"📊 Created tables:")
        print(f"   - {User.__tablename__}")
        print(f"   - {UserSession.__tablename__}")
        print(f"   - {Performance.__tablename__}")
        print(f"   - {QuestionHistory.__tablename__}")
        
        # Check if we can connect to the database
        try:
            # Test database connection
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            print("✅ Database connection successful!")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
        
        return True

def create_sample_data():
    """Create sample data for testing (optional)"""
    with app.app_context():
        print("\nCreating sample data...")
        
        # Check if sample data already exists
        if User.query.first():
            print("Sample data already exists, skipping...")
            return
        
        # Create a sample user
        sample_user = User(
            email="sample@school.cdgfss.edu.hk",
            first_name="Sample",
            last_name="User",
            role="student"
        )
        
        try:
            db.session.add(sample_user)
            db.session.commit()
            print("✅ Sample user created successfully!")
        except Exception as e:
            print(f"❌ Failed to create sample user: {e}")
            db.session.rollback()

if __name__ == "__main__":
    print("🚀 Initializing Maths Generator Database...")
    print("=" * 50)
    
    if init_database():
        create_sample_data()
        print("\n🎉 Database initialization completed successfully!")
        print("\nYou can now run your Flask app with:")
        print("   python3 app.py")
    else:
        print("\n❌ Database initialization failed!")
        sys.exit(1)
