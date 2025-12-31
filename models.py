"""
Database models and helper functions for the Election Portal.
Uses SQLite for simplicity and portability.
Passwordless authentication via email + CCPC profile URL.
"""

import sqlite3
import hashlib
import re
from flask import g

DATABASE = 'election.db'

# Valid voting categories
CATEGORIES = ['VP', 'GS', 'JS1', 'JS2', 'EXEC_TECH', 'EXEC_DESIGN', 'EXEC_PR']

CATEGORY_NAMES = {
    'VP': 'Vice President',
    'GS': 'General Secretary',
    'JS1': 'Joint Secretary 1',
    'JS2': 'Joint Secretary 2',
    'EXEC_TECH': 'Tech Executive',
    'EXEC_DESIGN': 'Design Executive',
    'EXEC_PR': 'PR Executive'
}


def get_db():
    """Get database connection, creating one if needed."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """Close database connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    """Initialize database from schema.sql."""
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.executescript(f.read())
        db.commit()
        
        # Create default admin if not exists
        cursor = db.execute("SELECT id FROM users WHERE email = ?", ('admin@club.com',))
        if cursor.fetchone() is None:
            db.execute(
                "INSERT INTO users (name, email, ccpc_profile_id, is_admin) VALUES (?, ?, ?, ?)",
                ('Admin', 'admin@club.com', 'ADMIN', True)
            )
            db.commit()


# ============ CCPC PROFILE URL PARSING ============

def extract_ccpc_profile_id(ccpc_url):
    """
    Extract profile ID from CCPC profile URL.
    Supports formats:
    - https://ccpc-cuj.web.app/profile/FE9FO4dLssN22QBPz8liIIgj04C2
    - ccpc-cuj.web.app/profile/FE9FO4dLssN22QBPz8liIIgj04C2
    - Just the ID: FE9FO4dLssN22QBPz8liIIgj04C2
    """
    if not ccpc_url:
        return None
    
    ccpc_url = ccpc_url.strip()
    
    # Try to extract from URL pattern
    match = re.search(r'/profile/([A-Za-z0-9]+)$', ccpc_url)
    if match:
        return match.group(1)
    
    # If no URL pattern, assume it's just the ID
    if re.match(r'^[A-Za-z0-9]+$', ccpc_url):
        return ccpc_url
    
    return None


# ============ USER FUNCTIONS ============

def get_user_by_email(email):
    """Fetch user by email."""
    db = get_db()
    cursor = db.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
    return cursor.fetchone()


def get_user_by_id(user_id):
    """Fetch user by ID."""
    db = get_db()
    cursor = db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone()


def authenticate_member(email, ccpc_url):
    """
    Authenticate a member using email + CCPC profile URL.
    Returns user if valid, None otherwise.
    """
    if not email or not ccpc_url:
        return None
    
    email = email.lower().strip()
    profile_id = extract_ccpc_profile_id(ccpc_url)
    
    if not profile_id:
        return None
    
    db = get_db()
    cursor = db.execute(
        "SELECT * FROM users WHERE email = ? AND ccpc_profile_id = ?",
        (email, profile_id)
    )
    return cursor.fetchone()


def create_member(name, email, ccpc_profile_id, is_admin=False):
    """Create a new member."""
    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (name, email, ccpc_profile_id, is_admin) VALUES (?, ?, ?, ?)",
            (name, email.lower().strip(), ccpc_profile_id, is_admin)
        )
        db.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Email already exists


# ============ CANDIDATE FUNCTIONS ============

def get_candidates_by_category(category):
    """Get all candidates for a specific category."""
    db = get_db()
    cursor = db.execute(
        "SELECT * FROM candidates WHERE category = ? ORDER BY name",
        (category,)
    )
    return cursor.fetchall()


def get_all_candidates():
    """Get all candidates grouped by category."""
    db = get_db()
    cursor = db.execute("SELECT * FROM candidates ORDER BY category, name")
    return cursor.fetchall()


def add_candidate(name, category):
    """Add a new candidate."""
    if category not in CATEGORIES:
        return False
    db = get_db()
    db.execute(
        "INSERT INTO candidates (name, category) VALUES (?, ?)",
        (name, category)
    )
    db.commit()
    return True


# ============ VOTING FUNCTIONS ============

def generate_voter_hash(user_id, secret_key):
    """Generate anonymous voter hash."""
    return hashlib.sha256(f"{user_id}{secret_key}".encode()).hexdigest()


def get_voted_categories(voter_hash):
    """Get list of categories user has already voted in."""
    db = get_db()
    cursor = db.execute(
        "SELECT category FROM votes WHERE voter_hash = ?",
        (voter_hash,)
    )
    return [row['category'] for row in cursor.fetchall()]


def record_vote(category, candidate_id, voter_hash):
    """
    Record a vote. Returns True on success, False if already voted.
    The UNIQUE constraint on (category, voter_hash) prevents double voting.
    """
    if category not in CATEGORIES:
        return False, "Invalid category"
    
    db = get_db()
    
    # Verify candidate exists and belongs to category
    cursor = db.execute(
        "SELECT id FROM candidates WHERE id = ? AND category = ?",
        (candidate_id, category)
    )
    if cursor.fetchone() is None:
        return False, "Invalid candidate"
    
    try:
        db.execute(
            "INSERT INTO votes (category, candidate_id, voter_hash) VALUES (?, ?, ?)",
            (category, candidate_id, voter_hash)
        )
        db.commit()
        return True, "Vote recorded successfully"
    except sqlite3.IntegrityError:
        return False, "You have already voted in this category"


def has_voted_in_category(voter_hash, category):
    """Check if user has voted in a specific category."""
    db = get_db()
    cursor = db.execute(
        "SELECT id FROM votes WHERE voter_hash = ? AND category = ?",
        (voter_hash, category)
    )
    return cursor.fetchone() is not None


# ============ ELECTION CONFIG FUNCTIONS ============

def is_election_active():
    """Check if election is currently active."""
    db = get_db()
    cursor = db.execute("SELECT is_active FROM election_config WHERE id = 1")
    row = cursor.fetchone()
    return row['is_active'] if row else False


def toggle_election():
    """Toggle election status. Returns new status."""
    db = get_db()
    cursor = db.execute("SELECT is_active FROM election_config WHERE id = 1")
    row = cursor.fetchone()
    
    if row:
        new_status = not row['is_active']
        timestamp_field = 'started_at' if new_status else 'ended_at'
        db.execute(
            f"UPDATE election_config SET is_active = ?, {timestamp_field} = CURRENT_TIMESTAMP WHERE id = 1",
            (new_status,)
        )
    else:
        new_status = True
        db.execute(
            "INSERT INTO election_config (id, is_active, started_at) VALUES (1, TRUE, CURRENT_TIMESTAMP)"
        )
    
    db.commit()
    return new_status


def get_election_status():
    """Get election configuration."""
    db = get_db()
    cursor = db.execute("SELECT * FROM election_config WHERE id = 1")
    return cursor.fetchone()


# ============ RESULTS FUNCTIONS ============

def get_results():
    """Get vote counts per candidate, grouped by category."""
    db = get_db()
    cursor = db.execute("""
        SELECT 
            c.category,
            c.name as candidate_name,
            c.id as candidate_id,
            COUNT(v.id) as vote_count
        FROM candidates c
        LEFT JOIN votes v ON c.id = v.candidate_id
        GROUP BY c.id
        ORDER BY c.category, vote_count DESC
    """)
    
    results = {}
    for row in cursor.fetchall():
        category = row['category']
        if category not in results:
            results[category] = []
        results[category].append({
            'name': row['candidate_name'],
            'id': row['candidate_id'],
            'votes': row['vote_count']
        })
    
    return results


def get_total_voters():
    """Get count of unique voters."""
    db = get_db()
    cursor = db.execute("SELECT COUNT(DISTINCT voter_hash) as count FROM votes")
    row = cursor.fetchone()
    return row['count'] if row else 0
