"""
Initialize Database Script
Run this once to set up the database with all data.
This is called automatically by the build command on Render.

Usage: python init_all.py
"""

import os
from app import app
from models import init_db, auto_initialize_data, DB_TYPE

if __name__ == "__main__":
    print("=" * 50)
    print(f"ELECTION PORTAL - FULL INITIALIZATION ({DB_TYPE.upper()})")
    print("=" * 50)
    
    with app.app_context():
        try:
            init_db(app)
            auto_initialize_data(app)
            print("\n✅ INITIALIZATION COMPLETE!")
        except Exception as e:
            print(f"\n❌ INITIALIZATION FAILED: {e}")
    
    print("=" * 50)
