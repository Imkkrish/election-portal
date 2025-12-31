"""
Seed Candidates Script
Inserts nomination data into the candidates table.

Usage: python seed_candidates.py
"""

import sqlite3

DATABASE = 'election.db'

# ============ NOMINATION DATA (EXPLICIT ASSIGNMENTS) ============

# All 16 nominees (appear in all non-VP categories)
ALL_NOMINEES = [
    "Sanskar",
    "Raj Vardhan Jha",
    "Abhishek",
    "Namrata",
    "Shashi Kumari Verma",
    "Dheeraj Kumar",
    "Samridhi Tripathi",
    "Abhi Raj Gupta",
    "Diwakar",
    "Priyanshi Chaurasia",
    "Kundan Kumar",
    "Ujit Raj Rathore",
    "Priyanshu Verma",
    "Raj Vardhan Rathore",
    "Ashish Sahu",
    "Basil Joy",
]

# Vice President nominees (VP) - separate list
VP_CANDIDATES = [
    "Priyanshu Verma",
    "Basil Joy",
    "Apurba Das",
    "Aditya Singh Chandel",
    "Krish Kumar",
]

# All other categories get all 17 nominees
GS_CANDIDATES = ALL_NOMINEES.copy()
JS1_CANDIDATES = ALL_NOMINEES.copy()
JS2_CANDIDATES = ALL_NOMINEES.copy()
EXEC_TECH_CANDIDATES = ALL_NOMINEES.copy()
EXEC_DESIGN_CANDIDATES = ALL_NOMINEES.copy()
EXEC_PR_CANDIDATES = ALL_NOMINEES.copy()


def seed_candidates():
    """Insert all candidates into the database."""
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Category to candidates mapping
    categories = {
        'VP': VP_CANDIDATES,
        'GS': GS_CANDIDATES,
        'JS1': JS1_CANDIDATES,
        'JS2': JS2_CANDIDATES,
        'EXEC_TECH': EXEC_TECH_CANDIDATES,
        'EXEC_DESIGN': EXEC_DESIGN_CANDIDATES,
        'EXEC_PR': EXEC_PR_CANDIDATES,
    }
    
    results = {}
    
    for category, candidates in categories.items():
        inserted = 0
        for name in candidates:
            try:
                # INSERT OR IGNORE prevents duplicate (name, category) entries
                cursor.execute(
                    "INSERT OR IGNORE INTO candidates (name, category) VALUES (?, ?)",
                    (name, category)
                )
                if cursor.rowcount > 0:
                    inserted += 1
            except sqlite3.Error as e:
                print(f"Error inserting {name} into {category}: {e}")
        
        results[category] = inserted
    
    conn.commit()
    conn.close()
    
    # Print summary
    print("\n" + "=" * 50)
    print("CANDIDATE SEEDING COMPLETE")
    print("=" * 50)
    print(f"VP candidates inserted:          {results['VP']}")
    print(f"GS candidates inserted:          {results['GS']}")
    print(f"JS1 candidates inserted:         {results['JS1']}")
    print(f"JS2 candidates inserted:         {results['JS2']}")
    print(f"EXEC_TECH candidates inserted:   {results['EXEC_TECH']}")
    print(f"EXEC_DESIGN candidates inserted: {results['EXEC_DESIGN']}")
    print(f"EXEC_PR candidates inserted:     {results['EXEC_PR']}")
    print("-" * 50)
    print(f"TOTAL inserted: {sum(results.values())}")
    print("=" * 50)


def verify_candidates():
    """Query and display all candidates."""
    
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n" + "=" * 50)
    print("VERIFICATION: All Candidates")
    print("=" * 50)
    
    cursor.execute("SELECT name, category FROM candidates ORDER BY category, name")
    rows = cursor.fetchall()
    
    current_category = None
    for row in rows:
        if row['category'] != current_category:
            current_category = row['category']
            print(f"\n[{current_category}]")
        print(f"  - {row['name']}")
    
    # Count by category
    print("\n" + "-" * 50)
    print("Summary by Category:")
    cursor.execute("""
        SELECT category, COUNT(*) as count 
        FROM candidates 
        GROUP BY category 
        ORDER BY category
    """)
    for row in cursor.fetchall():
        print(f"  {row['category']:12s}: {row['count']} candidates")
    
    # Total unique candidates
    cursor.execute("SELECT COUNT(DISTINCT name) as count FROM candidates")
    unique_count = cursor.fetchone()['count']
    print(f"\nUnique names across all categories: {unique_count}")
    
    conn.close()


if __name__ == "__main__":
    print("Seeding candidates into election.db...")
    seed_candidates()
    verify_candidates()
