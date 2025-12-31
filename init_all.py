"""
Initialize Database Script
Run this once to set up the database with all data.
This is called automatically by the build command on Render.

Usage: python init_all.py
"""

import os
import sqlite3

DATABASE = 'election.db'

def init_database():
    """Initialize the database from schema.sql"""
    print("Initializing database...")
    
    # Read and execute schema
    with open('schema.sql', 'r') as f:
        schema = f.read()
    
    conn = sqlite3.connect(DATABASE)
    conn.executescript(schema)
    conn.commit()
    
    # Create default admin if not exists
    cursor = conn.execute("SELECT id FROM users WHERE email = ?", ('admin@club.com',))
    if cursor.fetchone() is None:
        conn.execute(
            "INSERT INTO users (name, email, ccpc_profile_id, is_admin) VALUES (?, ?, ?, ?)",
            ('Admin', 'admin@club.com', 'ADMIN', True)
        )
        conn.commit()
        print("✓ Admin user created")
    
    conn.close()
    print("✓ Database schema initialized")


def seed_candidates():
    """Seed all candidates."""
    from seed_candidates import seed_candidates as do_seed
    print("\nSeeding candidates...")
    do_seed()


def seed_members():
    """Seed all members from Firebase export."""
    import json
    
    print("\nSeeding members from Firebase export...")
    
    FIREBASE_EXPORT = 'soc-ccpc-cuj-default-rtdb-export.json'
    
    if not os.path.exists(FIREBASE_EXPORT):
        print(f"⚠️ {FIREBASE_EXPORT} not found, skipping member seeding")
        return
    
    with open(FIREBASE_EXPORT, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    users = data.get('users', {})
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    inserted = 0
    
    for profile_id, user_data in users.items():
        if not user_data.get('completeProfile', False):
            continue
        if not user_data.get('isMember', False):
            continue
        
        name = user_data.get('name', '').strip()
        email = user_data.get('email', '').strip().lower()
        
        if not name or not email:
            continue
        
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO users (name, email, ccpc_profile_id, is_admin) VALUES (?, ?, ?, ?)",
                (name, email, profile_id, False)
            )
            if cursor.rowcount > 0:
                inserted += 1
        except sqlite3.Error:
            pass
    
    # Add manually specified members (those without email in Firebase)
    manual_members = [
        ('Basil Joy', 'basil.23190503023@cuj.ac.in', 'ZnStO6ic3fM6MQLiI5iUBZnyyC63'),
        ('Shashi Kumari Verma', 'shashi.24190503050@cuj.ac.in', 's8ZKdaxsWPWl1hQoTDhon47uy9O2'),
    ]
    
    for name, email, profile_id in manual_members:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO users (name, email, ccpc_profile_id, is_admin) VALUES (?, ?, ?, ?)",
                (name, email, profile_id, False)
            )
            if cursor.rowcount > 0:
                inserted += 1
        except sqlite3.Error:
            pass
    
    conn.commit()
    conn.close()
    
    # Count total
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    conn.close()
    
    print(f"✓ {inserted} new members added")
    print(f"✓ Total members in database: {total}")


if __name__ == "__main__":
    print("=" * 50)
    print("ELECTION PORTAL - FULL INITIALIZATION")
    print("=" * 50)
    
    init_database()
    seed_candidates()
    seed_members()
    
    print("\n" + "=" * 50)
    print("✅ INITIALIZATION COMPLETE!")
    print("=" * 50)
