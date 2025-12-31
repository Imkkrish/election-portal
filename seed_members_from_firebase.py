"""
Seed Members from Firebase Export
Parses the CCPC Firebase Realtime Database export and seeds members into election.db

Usage: python seed_members_from_firebase.py
"""

import sqlite3
import json

DATABASE = 'election.db'
FIREBASE_EXPORT = 'soc-ccpc-cuj-default-rtdb-export.json'


def parse_firebase_members():
    """Parse Firebase export and extract member data."""
    
    with open(FIREBASE_EXPORT, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    users = data.get('users', {})
    members = []
    
    for profile_id, user_data in users.items():
        # Skip incomplete profiles
        if not user_data.get('completeProfile', False):
            continue
        
        # Skip non-members or alumni
        if not user_data.get('isMember', False):
            continue
        
        # Get required fields
        name = user_data.get('name', '').strip()
        email = user_data.get('email', '').strip().lower()
        
        # Skip if no name or email
        if not name:
            continue
        
        if not email:
            print(f"⚠️ Skipping {name}: No email provided")
            continue
        
        # profile_id is the Firebase UID which is the CCPC profile ID
        members.append({
            'name': name,
            'email': email,
            'ccpc_profile_id': profile_id,
            'designation': user_data.get('designation', 'Member')
        })
    
    return members


def seed_members():
    """Insert parsed members into the database."""
    
    members = parse_firebase_members()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    for member in members:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO users (name, email, ccpc_profile_id, is_admin) VALUES (?, ?, ?, ?)",
                (member['name'], member['email'], member['ccpc_profile_id'], False)
            )
            if cursor.rowcount > 0:
                inserted += 1
                print(f"✓ Added: {member['name']} ({member['email']})")
            else:
                skipped += 1
                print(f"⊘ Skipped (already exists): {member['name']}")
        except sqlite3.Error as e:
            print(f"✗ Error adding {member['name']}: {e}")
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 60)
    print(f"MEMBERS SEEDED FROM FIREBASE: {inserted} added, {skipped} skipped")
    print("=" * 60)


def list_members():
    """List all registered members."""
    
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, email, is_admin FROM users ORDER BY name")
    rows = cursor.fetchall()
    
    print("\n" + "=" * 60)
    print("ALL REGISTERED MEMBERS")
    print("=" * 60)
    
    for row in rows:
        admin_tag = " [ADMIN]" if row['is_admin'] else ""
        print(f"  {row['id']:3d}. {row['name']}{admin_tag}")
        print(f"       {row['email']}")
    
    print(f"\nTotal: {len(rows)} members")
    conn.close()


if __name__ == "__main__":
    print(f"Parsing members from {FIREBASE_EXPORT}...")
    seed_members()
    list_members()
