"""
Seed Members Script
Adds club members to the database for election authentication.

Usage: python seed_members.py
"""

import sqlite3

DATABASE = 'election.db'

# ============ MEMBER DATA ============
# Add members as: (name, email, ccpc_profile_id)
# The ccpc_profile_id is extracted from: https://ccpc-cuj.web.app/profile/{ID}

MEMBERS = [
    # Example format - add your members here:
    # ("Name", "email@cuj.ac.in", "CCPC_PROFILE_ID"),
    
    ("Krish Kumar", "krish.22190503027@cuj.ac.in", "FE9FO4dLssN22QBPz8liIIgj04C2"),
    
    # Add more members below...
    # ("Priyanshu Verma", "priyanshu.xxxxx@cuj.ac.in", "PROFILE_ID_HERE"),
]


def seed_members():
    """Insert all members into the database."""
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    for name, email, ccpc_id in MEMBERS:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO users (name, email, ccpc_profile_id, is_admin) VALUES (?, ?, ?, ?)",
                (name, email.lower().strip(), ccpc_id, False)
            )
            if cursor.rowcount > 0:
                inserted += 1
                print(f"✓ Added: {name} ({email})")
            else:
                skipped += 1
                print(f"⊘ Skipped (already exists): {name} ({email})")
        except sqlite3.Error as e:
            print(f"✗ Error adding {name}: {e}")
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print(f"MEMBERS SEEDED: {inserted} added, {skipped} skipped")
    print("=" * 50)


def list_members():
    """List all registered members."""
    
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, email, is_admin FROM users ORDER BY name")
    rows = cursor.fetchall()
    
    print("\n" + "=" * 50)
    print("REGISTERED MEMBERS")
    print("=" * 50)
    
    for row in rows:
        admin_tag = " [ADMIN]" if row['is_admin'] else ""
        print(f"  {row['id']:3d}. {row['name']}{admin_tag}")
        print(f"       {row['email']}")
    
    print(f"\nTotal: {len(rows)} members")
    conn.close()


if __name__ == "__main__":
    print("Seeding members into election.db...")
    seed_members()
    list_members()
