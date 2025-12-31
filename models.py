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


# ============ POSITION MANAGEMENT FUNCTIONS ============

def get_all_positions():
    """Get all election positions with their status."""
    db = get_db()
    cursor = db.execute("""
        SELECT * FROM election_positions 
        ORDER BY rank_order
    """)
    return cursor.fetchall()


def get_position(position_code):
    """Get a specific position by code."""
    db = get_db()
    cursor = db.execute(
        "SELECT * FROM election_positions WHERE position_code = ?",
        (position_code,)
    )
    return cursor.fetchone()


def toggle_position(position_code):
    """Toggle a position's active status. Returns new status."""
    db = get_db()
    cursor = db.execute(
        "SELECT is_active FROM election_positions WHERE position_code = ?",
        (position_code,)
    )
    row = cursor.fetchone()
    
    if row:
        new_status = not row['is_active']
        db.execute(
            "UPDATE election_positions SET is_active = ? WHERE position_code = ?",
            (new_status, position_code)
        )
        db.commit()
        return new_status
    return False


def set_position_timeline(position_code, opens_at, closes_at):
    """Set opens_at and closes_at for a position."""
    db = get_db()
    db.execute(
        """UPDATE election_positions 
           SET opens_at = ?, closes_at = ? 
           WHERE position_code = ?""",
        (opens_at, closes_at, position_code)
    )
    db.commit()
    return True


def is_position_active(position_code):
    """Check if a specific position's voting is currently active."""
    from datetime import datetime
    db = get_db()
    cursor = db.execute(
        "SELECT is_active, opens_at, closes_at FROM election_positions WHERE position_code = ?",
        (position_code,)
    )
    row = cursor.fetchone()
    
    if not row or not row['is_active']:
        return False
    
    # If no timeline set, just use is_active flag
    if not row['opens_at'] and not row['closes_at']:
        return True
    
    now = datetime.now()
    
    # Check timeline bounds
    if row['opens_at']:
        opens = datetime.fromisoformat(row['opens_at']) if isinstance(row['opens_at'], str) else row['opens_at']
        if now < opens:
            return False
    
    if row['closes_at']:
        closes = datetime.fromisoformat(row['closes_at']) if isinstance(row['closes_at'], str) else row['closes_at']
        if now > closes:
            return False
    
    return True


def get_active_positions():
    """Get list of currently active position codes."""
    positions = get_all_positions()
    return [p['position_code'] for p in positions if is_position_active(p['position_code'])]


# ============ RANKED VOTING FUNCTIONS ============

def record_ranked_votes(voter_hash, position_code, ranked_candidate_ids):
    """
    Record ranked preference votes for a position.
    ranked_candidate_ids: list of candidate IDs in preference order (first = most preferred)
    Returns (success, message)
    """
    if position_code not in CATEGORIES:
        return False, "Invalid position"
    
    db = get_db()
    
    # Check if already voted for this position
    cursor = db.execute(
        "SELECT id FROM ranked_votes WHERE voter_hash = ? AND position_code = ?",
        (voter_hash, position_code)
    )
    if cursor.fetchone():
        return False, "You have already voted for this position"
    
    # Validate all candidate IDs belong to this position
    for cand_id in ranked_candidate_ids:
        cursor = db.execute(
            "SELECT id FROM candidates WHERE id = ? AND category = ?",
            (cand_id, position_code)
        )
        if not cursor.fetchone():
            return False, f"Invalid candidate ID: {cand_id}"
    
    # Insert ranked votes
    try:
        for rank, cand_id in enumerate(ranked_candidate_ids, start=1):
            db.execute(
                """INSERT INTO ranked_votes 
                   (voter_hash, position_code, candidate_id, preference_rank) 
                   VALUES (?, ?, ?, ?)""",
                (voter_hash, position_code, cand_id, rank)
            )
        db.commit()
        return True, "Votes recorded successfully"
    except sqlite3.IntegrityError as e:
        return False, f"Error recording votes: {e}"


def has_voted_for_position(voter_hash, position_code):
    """Check if voter has submitted ranked votes for a position."""
    db = get_db()
    cursor = db.execute(
        "SELECT id FROM ranked_votes WHERE voter_hash = ? AND position_code = ? LIMIT 1",
        (voter_hash, position_code)
    )
    return cursor.fetchone() is not None


def get_voter_preferences(voter_hash, position_code):
    """Get a voter's ranked preferences for a position."""
    db = get_db()
    cursor = db.execute(
        """SELECT c.id, c.name, rv.preference_rank
           FROM ranked_votes rv
           JOIN candidates c ON rv.candidate_id = c.id
           WHERE rv.voter_hash = ? AND rv.position_code = ?
           ORDER BY rv.preference_rank""",
        (voter_hash, position_code)
    )
    return cursor.fetchall()


def get_ranked_voted_positions(voter_hash):
    """Get list of positions voter has submitted ranked votes for."""
    db = get_db()
    cursor = db.execute(
        "SELECT DISTINCT position_code FROM ranked_votes WHERE voter_hash = ?",
        (voter_hash,)
    )
    return [row['position_code'] for row in cursor.fetchall()]


# ============ RECOMPUTATION ALGORITHM ============

def compute_position_winner(position_code, excluded_candidate_ids=None):
    """
    Compute the winner for a position using preference recomputation.
    
    Algorithm:
    1. Get all ranked votes for this position
    2. For each voter, find their highest-ranked candidate NOT in excluded list
    3. Count these "effective first-preference" votes
    4. Return candidate with most votes
    
    Args:
        position_code: The position to compute winner for
        excluded_candidate_ids: Set of candidate IDs already elected to higher posts
    
    Returns:
        dict with 'winner' (candidate info) and 'results' (all candidates with counts)
    """
    if excluded_candidate_ids is None:
        excluded_candidate_ids = set()
    
    db = get_db()
    
    # Get all unique voters for this position
    cursor = db.execute(
        "SELECT DISTINCT voter_hash FROM ranked_votes WHERE position_code = ?",
        (position_code,)
    )
    voters = [row['voter_hash'] for row in cursor.fetchall()]
    
    # Count effective first-preference votes
    vote_counts = {}  # candidate_id -> count
    
    for voter_hash in voters:
        # Get this voter's preferences in order
        cursor = db.execute(
            """SELECT candidate_id FROM ranked_votes 
               WHERE voter_hash = ? AND position_code = ?
               ORDER BY preference_rank""",
            (voter_hash, position_code)
        )
        preferences = [row['candidate_id'] for row in cursor.fetchall()]
        
        # Find first non-excluded candidate
        for cand_id in preferences:
            if cand_id not in excluded_candidate_ids:
                vote_counts[cand_id] = vote_counts.get(cand_id, 0) + 1
                break
        # If all preferences are excluded, this voter's vote is exhausted
    
    # Get candidate details and build results
    results = []
    for cand_id, count in vote_counts.items():
        cursor = db.execute("SELECT id, name FROM candidates WHERE id = ?", (cand_id,))
        cand = cursor.fetchone()
        if cand:
            results.append({
                'id': cand['id'],
                'name': cand['name'],
                'votes': count
            })
    
    # Add candidates with zero votes (not in any voter's top choice after exclusions)
    cursor = db.execute(
        "SELECT id, name FROM candidates WHERE category = ?",
        (position_code,)
    )
    all_candidates = cursor.fetchall()
    existing_ids = {r['id'] for r in results}
    for cand in all_candidates:
        if cand['id'] not in existing_ids and cand['id'] not in excluded_candidate_ids:
            results.append({
                'id': cand['id'],
                'name': cand['name'],
                'votes': 0
            })
    
    # Sort by votes descending
    results.sort(key=lambda x: x['votes'], reverse=True)
    
    winner = results[0] if results else None
    
    return {
        'position_code': position_code,
        'winner': winner,
        'results': results,
        'total_voters': len(voters),
        'exhausted_votes': len(voters) - sum(vote_counts.values())
    }


def compute_all_results():
    """
    Compute winners for all positions using hierarchical recomputation.
    
    Process:
    1. Get positions in rank order (VP first, then GS, etc.)
    2. For each position, compute winner excluding all previously elected candidates
    3. Add winner to exclusion list
    4. Continue to next position
    
    Returns:
        List of position results with winners
    """
    db = get_db()
    
    # Get positions in hierarchical order
    cursor = db.execute(
        "SELECT position_code, position_name FROM election_positions ORDER BY rank_order"
    )
    positions = cursor.fetchall()
    
    excluded_candidates = set()
    all_results = []
    
    for pos in positions:
        position_code = pos['position_code']
        
        result = compute_position_winner(position_code, excluded_candidates)
        result['position_name'] = pos['position_name']
        
        # Add winner to exclusion set for subsequent positions
        if result['winner']:
            excluded_candidates.add(result['winner']['id'])
        
        all_results.append(result)
    
    return all_results


def save_election_winners(results):
    """
    Save computed winners to election_winners table.
    Clears existing winners and saves new ones.
    """
    db = get_db()
    
    # Clear existing winners
    db.execute("DELETE FROM election_winners")
    
    # Save new winners
    for result in results:
        if result['winner']:
            db.execute(
                """INSERT INTO election_winners 
                   (position_code, candidate_id, candidate_name, vote_count)
                   VALUES (?, ?, ?, ?)""",
                (result['position_code'], result['winner']['id'], 
                 result['winner']['name'], result['winner']['votes'])
            )
    
    db.commit()


def get_election_winners():
    """Get saved election winners."""
    db = get_db()
    cursor = db.execute("""
        SELECT ew.*, ep.position_name, ep.rank_order
        FROM election_winners ew
        JOIN election_positions ep ON ew.position_code = ep.position_code
        ORDER BY ep.rank_order
    """)
    return cursor.fetchall()


def get_ranked_vote_count():
    """Get count of unique voters who have submitted ranked votes."""
    db = get_db()
    cursor = db.execute("SELECT COUNT(DISTINCT voter_hash) as count FROM ranked_votes")
    row = cursor.fetchone()
    return row['count'] if row else 0
