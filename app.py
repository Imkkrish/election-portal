"""
Election Portal - Main Flask Application
A secure web-based election system for club member voting.
Passwordless authentication via email + CCPC profile URL.
"""

import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from flask_wtf.csrf import CSRFProtect

import models
from models import (
    get_db, close_db, init_db,
    get_user_by_email, get_user_by_id, authenticate_member,
    get_candidates_by_category, generate_voter_hash,
    get_voted_categories, record_vote, has_voted_in_category,
    is_election_active, toggle_election, get_election_status,
    get_results, get_total_voters,
    CATEGORIES, CATEGORY_NAMES,
    # New imports for preference-based system
    get_all_positions, get_position, toggle_position, 
    set_position_timeline, is_position_active, get_active_positions,
    record_ranked_votes, has_voted_for_position, get_ranked_voted_positions,
    compute_all_results, save_election_winners, get_election_winners,
    get_ranked_vote_count
)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['WTF_CSRF_ENABLED'] = True

# Enable CSRF protection
csrf = CSRFProtect(app)

# ============ AUTO-INITIALIZE DATABASE ============
def auto_initialize():
    """Auto-initialize database on first request if tables don't exist."""
    import sqlite3
    import json
    
    DATABASE = 'election.db'
    
    # Check if database needs initialization
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        conn.close()
        if count > 0:
            return  # Already initialized
    except sqlite3.OperationalError:
        pass  # Table doesn't exist, need to initialize
    
    print("=" * 50)
    print("AUTO-INITIALIZING DATABASE...")
    print("=" * 50)
    
    # Initialize schema
    with open('schema.sql', 'r') as f:
        schema = f.read()
    
    conn = sqlite3.connect(DATABASE)
    conn.executescript(schema)
    conn.commit()
    print("✓ Schema created")
    
    # Create admin user
    conn.execute(
        "INSERT OR IGNORE INTO users (name, email, ccpc_profile_id, is_admin) VALUES (?, ?, ?, ?)",
        ('Admin', 'admin@club.com', 'ADMIN', True)
    )
    conn.commit()
    print("✓ Admin user created")
    
    # Seed candidates
    from seed_candidates import VP_CANDIDATES, ALL_NOMINEES
    categories = {
        'VP': VP_CANDIDATES,
        'GS': ALL_NOMINEES,
        'JS1': ALL_NOMINEES,
        'JS2': ALL_NOMINEES,
        'EXEC_TECH': ALL_NOMINEES,
        'EXEC_DESIGN': ALL_NOMINEES,
        'EXEC_PR': ALL_NOMINEES,
    }
    
    for category, candidates in categories.items():
        for name in candidates:
            conn.execute(
                "INSERT OR IGNORE INTO candidates (name, category) VALUES (?, ?)",
                (name, category)
            )
    conn.commit()
    print("✓ Candidates seeded")
    
    # Seed members from Firebase
    FIREBASE_EXPORT = 'soc-ccpc-cuj-default-rtdb-export.json'
    if os.path.exists(FIREBASE_EXPORT):
        with open(FIREBASE_EXPORT, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        users = data.get('users', {})
        for profile_id, user_data in users.items():
            if not user_data.get('completeProfile', False):
                continue
            if not user_data.get('isMember', False):
                continue
            
            name = user_data.get('name', '').strip()
            email = user_data.get('email', '').strip().lower()
            
            if not name or not email:
                continue
            
            conn.execute(
                "INSERT OR IGNORE INTO users (name, email, ccpc_profile_id, is_admin) VALUES (?, ?, ?, ?)",
                (name, email, profile_id, False)
            )
        
        # Add members with manually specified emails
        conn.execute(
            "INSERT OR IGNORE INTO users (name, email, ccpc_profile_id, is_admin) VALUES (?, ?, ?, ?)",
            ('Basil Joy', 'basil.23190503023@cuj.ac.in', 'ZnStO6ic3fM6MQLiI5iUBZnyyC63', False)
        )
        conn.execute(
            "INSERT OR IGNORE INTO users (name, email, ccpc_profile_id, is_admin) VALUES (?, ?, ?, ?)",
            ('Shashi Kumari Verma', 'shashi.24190503050@cuj.ac.in', 's8ZKdaxsWPWl1hQoTDhon47uy9O2', False)
        )
        conn.commit()
        print("✓ Members seeded from Firebase")
    
    # Count totals
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM candidates")
    cand_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"✓ Total users: {user_count}")
    print(f"✓ Total candidates: {cand_count}")
    print("=" * 50)
    print("DATABASE INITIALIZATION COMPLETE!")
    print("=" * 50)

# Run auto-initialization when module loads
with app.app_context():
    auto_initialize()

# Register database cleanup
app.teardown_appcontext(close_db)


# ============ DECORATORS ============

def login_required(f):
    """Decorator to require login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        user = get_user_by_id(session['user_id'])
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('ranked_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def election_active_required(f):
    """Decorator to require active election for voting."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_election_active():
            flash('Voting is currently closed.', 'warning')
            return redirect(url_for('ranked_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ============ CONTEXT PROCESSORS ============

@app.context_processor
def inject_globals():
    """Inject global variables into all templates."""
    user = None
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
    return {
        'current_user': user,
        'election_active': is_election_active(),
        'CATEGORY_NAMES': CATEGORY_NAMES
    }


# ============ AUTH ROUTES ============

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page - authenticate with email + CCPC profile URL."""
    if 'user_id' in session:
        return redirect(url_for('ranked_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        ccpc_url = request.form.get('ccpc_url', '').strip()
        
        # Authenticate using email + CCPC profile
        user = authenticate_member(email, ccpc_url)
        
        if user:
            session['user_id'] = user['id']
            flash(f'Welcome, {user["name"]}!', 'success')
            
            if user['is_admin']:
                return redirect(url_for('admin'))
            return redirect(url_for('ranked_dashboard'))
        else:
            flash('Invalid credentials. Please check your email and CCPC profile link.', 'danger')
    
    return render_template('login.html')


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page - password-based authentication."""
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        if user and user['is_admin']:
            return redirect(url_for('admin'))
        return redirect(url_for('ranked_dashboard'))
    
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        
        # Admin password check - MUST be set via env var in production
        ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
        FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
        
        # Security: Require ADMIN_PASSWORD env var in production
        if not ADMIN_PASSWORD:
            if FLASK_ENV == 'production':
                flash('Admin password not configured. Contact system administrator.', 'danger')
                return render_template('admin_login.html')
            else:
                # Only allow default in development
                ADMIN_PASSWORD = 'admin123'
        
        if password == ADMIN_PASSWORD:
            # Get or create admin user
            admin = get_user_by_email('admin@club.com')
            if admin:
                session['user_id'] = admin['id']
                flash('Welcome, Admin!', 'success')
                return redirect(url_for('admin'))
            else:
                flash('Admin account not found.', 'danger')
        else:
            flash('Invalid admin password.', 'danger')
    
    return render_template('admin_login.html')


@app.route('/logout')
def logout():
    """Logout and clear session."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ============ VOTING ROUTES ============

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    """Redirect to ranked dashboard."""
    return redirect(url_for('ranked_dashboard'))

@app.route('/legacy-dashboard')
@login_required
def legacy_dashboard():
    """Voting dashboard showing all categories with per-position status."""
    user = get_user_by_id(session['user_id'])
    voter_hash = generate_voter_hash(user['id'], app.secret_key)
    voted_categories = get_voted_categories(voter_hash)
    voted_positions = get_ranked_voted_positions(voter_hash)
    
    # Combine legacy votes and ranked votes
    all_voted = set(voted_categories) | set(voted_positions)
    
    categories_status = []
    any_active = False
    for cat in CATEGORIES:
        is_active = is_position_active(cat)
        if is_active:
            any_active = True
        categories_status.append({
            'code': cat,
            'name': CATEGORY_NAMES[cat],
            'voted': cat in all_voted,
            'is_active': is_active  # Per-position status
        })
    
    all_voted_complete = len(all_voted) == len(CATEGORIES)
    
    return render_template(
        'dashboard.html',
        categories=categories_status,
        all_voted=all_voted_complete,
        election_active=any_active  # True if ANY position is active
    )


@app.route('/vote/<category>', methods=['GET', 'POST'])
@login_required
@election_active_required
def vote(category):
    """Vote in a specific category."""
    if category not in CATEGORIES:
        flash('Invalid category.', 'danger')
        return redirect(url_for('dashboard'))
    
    user = get_user_by_id(session['user_id'])
    voter_hash = generate_voter_hash(user['id'], app.secret_key)
    
    # Check if already voted
    if has_voted_in_category(voter_hash, category):
        flash('You have already voted in this category.', 'warning')
        return redirect(url_for('dashboard'))
    
    candidates = get_candidates_by_category(category)
    
    if not candidates:
        flash('No candidates available for this category.', 'warning')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        candidate_id = request.form.get('candidate_id')
        
        if not candidate_id:
            flash('Please select a candidate.', 'danger')
            return render_template(
                'vote.html',
                category=category,
                category_name=CATEGORY_NAMES[category],
                candidates=candidates
            )
        
        try:
            candidate_id = int(candidate_id)
        except ValueError:
            flash('Invalid candidate selection.', 'danger')
            return redirect(url_for('vote', category=category))
        
        # Record the vote
        success, message = record_vote(category, candidate_id, voter_hash)
        
        if success:
            return redirect(url_for('confirmation'))
        else:
            flash(message, 'danger')
            return redirect(url_for('dashboard'))
    
    return render_template(
        'vote.html',
        category=category,
        category_name=CATEGORY_NAMES[category],
        candidates=candidates
    )


@app.route('/confirmation')
@login_required
def confirmation():
    """Vote confirmation page."""
    return render_template('confirmation.html')


# ============ ADMIN ROUTES ============

@app.route('/admin')
@admin_required
def admin():
    """Admin dashboard."""
    results = get_results()
    election_status = get_election_status()
    total_voters = get_total_voters()
    ranked_voter_count = get_ranked_vote_count()
    winners = get_election_winners()
    
    # Get positions with active status
    positions = get_all_positions()
    position_data = []
    for pos in positions:
        position_data.append({
            'code': pos['position_code'],
            'name': pos['position_name'],
            'is_active': pos['is_active'],
            'is_currently_active': is_position_active(pos['position_code'])
        })
    
    return render_template(
        'admin.html',
        results=results,
        election_status=election_status,
        total_voters=total_voters,
        ranked_voter_count=ranked_voter_count,
        winners=winners,
        positions=position_data,
        categories=CATEGORIES,
        category_names=CATEGORY_NAMES
    )


@app.route('/admin/toggle', methods=['POST'])
@admin_required
def admin_toggle():
    """Toggle election status."""
    new_status = toggle_election()
    status_text = 'started' if new_status else 'stopped'
    flash(f'Election has been {status_text}.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/export')
@admin_required
def admin_export():
    """Export results as CSV."""
    from flask import Response
    import csv
    import io
    
    results = get_results()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Category', 'Candidate', 'Votes'])
    
    for category in CATEGORIES:
        if category in results:
            for candidate in results[category]:
                writer.writerow([
                    CATEGORY_NAMES[category],
                    candidate['name'],
                    candidate['votes']
                ])
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=election_results.csv'}
    )


# ============ POSITION MANAGEMENT ROUTES ============

@app.route('/admin/positions')
@admin_required
def admin_positions():
    """Admin page for managing election positions."""
    positions = get_all_positions()
    winners = get_election_winners()
    ranked_voter_count = get_ranked_vote_count()
    
    # Build position status with active check
    position_data = []
    for pos in positions:
        position_data.append({
            'code': pos['position_code'],
            'name': pos['position_name'],
            'rank_order': pos['rank_order'],
            'is_active': pos['is_active'],
            'is_currently_active': is_position_active(pos['position_code']),
            'opens_at': pos['opens_at'],
            'closes_at': pos['closes_at']
        })
    
    return render_template(
        'admin_positions.html',
        positions=position_data,
        winners=winners,
        ranked_voter_count=ranked_voter_count
    )


@app.route('/admin/positions/<position_code>/toggle', methods=['POST'])
@admin_required
def admin_toggle_position(position_code):
    """Toggle a specific position's voting status."""
    new_status = toggle_position(position_code)
    status_text = 'opened' if new_status else 'closed'
    flash(f'{CATEGORY_NAMES.get(position_code, position_code)} voting has been {status_text}.', 'success')
    return redirect(url_for('admin_positions'))


@app.route('/admin/positions/<position_code>/timeline', methods=['POST'])
@admin_required
def admin_set_timeline(position_code):
    """Set timeline for a specific position."""
    opens_at = request.form.get('opens_at', '').strip() or None
    closes_at = request.form.get('closes_at', '').strip() or None
    
    set_position_timeline(position_code, opens_at, closes_at)
    flash(f'Timeline updated for {CATEGORY_NAMES.get(position_code, position_code)}.', 'success')
    return redirect(url_for('admin_positions'))


@app.route('/admin/compute-results', methods=['POST'])
@admin_required
def admin_compute_results():
    """Compute and save election results using preference recomputation."""
    results = compute_all_results()
    save_election_winners(results)
    flash('Election results computed and saved!', 'success')
    return redirect(url_for('admin_positions'))


@app.route('/admin/results')
@admin_required
def admin_view_results():
    """View detailed recomputed results."""
    results = compute_all_results()
    winners = get_election_winners()
    ranked_voter_count = get_ranked_vote_count()
    
    return render_template(
        'admin_results.html',
        results=results,
        winners=winners,
        ranked_voter_count=ranked_voter_count
    )


# ============ RANKED VOTING ROUTES ============

@app.route('/ranked-vote/<position>')
@login_required
def ranked_vote_page(position):
    """Show ranked voting page for a position."""
    if position not in CATEGORIES:
        flash('Invalid position.', 'danger')
        return redirect(url_for('ranked_dashboard'))
    
    if not is_position_active(position):
        flash(f'Voting for {CATEGORY_NAMES[position]} is currently closed.', 'warning')
        return redirect(url_for('ranked_dashboard'))
    
    user = get_user_by_id(session['user_id'])
    voter_hash = generate_voter_hash(user['id'], app.secret_key)
    
    if has_voted_for_position(voter_hash, position):
        flash('You have already voted for this position.', 'warning')
        return redirect(url_for('ranked_dashboard'))
    
    candidates = get_candidates_by_category(position)
    
    if not candidates:
        flash('No candidates available for this position.', 'warning')
        return redirect(url_for('ranked_dashboard'))
    
    return render_template(
        'ranked_vote.html',
        position=position,
        position_name=CATEGORY_NAMES[position],
        candidates=candidates
    )


@app.route('/ranked-vote/<position>/submit', methods=['POST'])
@login_required
def submit_ranked_vote(position):
    """Submit ranked preference votes."""
    if position not in CATEGORIES:
        flash('Invalid position.', 'danger')
        return redirect(url_for('ranked_dashboard'))
    
    if not is_position_active(position):
        flash(f'Voting for {CATEGORY_NAMES[position]} is currently closed.', 'warning')
        return redirect(url_for('ranked_dashboard'))
    
    user = get_user_by_id(session['user_id'])
    voter_hash = generate_voter_hash(user['id'], app.secret_key)
    
    if has_voted_for_position(voter_hash, position):
        flash('You have already voted for this position.', 'warning')
        return redirect(url_for('ranked_dashboard'))
    
    # Parse ranked candidates from form
    ranked_ids_str = request.form.get('ranked_candidates', '')
    
    if not ranked_ids_str:
        flash('Please rank at least one candidate.', 'danger')
        return redirect(url_for('ranked_vote_page', position=position))
    
    try:
        ranked_ids = [int(x) for x in ranked_ids_str.split(',') if x.strip()]
    except ValueError:
        flash('Invalid candidate selection.', 'danger')
        return redirect(url_for('ranked_vote_page', position=position))
    
    if not ranked_ids:
        flash('Please rank at least one candidate.', 'danger')
        return redirect(url_for('ranked_vote_page', position=position))
    
    # Record the ranked votes
    success, message = record_ranked_votes(voter_hash, position, ranked_ids)
    
    if success:
        flash(f'Your ranked vote for {CATEGORY_NAMES[position]} has been recorded!', 'success')
        return redirect(url_for('confirmation'))
    else:
        flash(message, 'danger')
        return redirect(url_for('ranked_vote_page', position=position))


@app.route('/ranked-dashboard')
@login_required
def ranked_dashboard():
    """Dashboard for ranked preference voting."""
    user = get_user_by_id(session['user_id'])
    voter_hash = generate_voter_hash(user['id'], app.secret_key)
    voted_positions = get_ranked_voted_positions(voter_hash)
    
    positions = get_all_positions()
    position_status = []
    
    for pos in positions:
        position_status.append({
            'code': pos['position_code'],
            'name': pos['position_name'],
            'is_active': is_position_active(pos['position_code']),
            'voted': pos['position_code'] in voted_positions,
            'opens_at': pos['opens_at'],
            'closes_at': pos['closes_at']
        })
    
    all_voted = len(voted_positions) == len(CATEGORIES)
    
    return render_template(
        'ranked_dashboard.html',
        positions=position_status,
        all_voted=all_voted
    )


# ============ ERROR HANDLERS ============

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error='Page not found'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error='Internal server error'), 500


# ============ CLI COMMANDS ============

@app.cli.command('init-db')
def init_db_command():
    """Initialize the database."""
    init_db(app)
    print('Database initialized.')


@app.cli.command('add-member')
def add_member_command():
    """Add a member."""
    from models import create_member
    name = input('Name: ')
    email = input('Email: ')
    ccpc_id = input('CCPC Profile ID: ')
    if create_member(name, email, ccpc_id):
        print(f'Member {email} created.')
    else:
        print('Error: Email already exists.')


@app.cli.command('add-candidate')
def add_candidate_command():
    """Add a candidate."""
    from models import add_candidate
    name = input('Candidate Name: ')
    print(f'Categories: {", ".join(CATEGORIES)}')
    category = input('Category: ').upper()
    if add_candidate(name, category):
        print(f'Candidate {name} added to {category}.')
    else:
        print('Error: Invalid category.')


# ============ MAIN ============

if __name__ == '__main__':
    # Initialize database on first run
    if not os.path.exists('election.db'):
        init_db(app)
        print('Database initialized with default admin user.')
    
    app.run(debug=True, port=5002)
