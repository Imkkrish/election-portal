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
    CATEGORIES, CATEGORY_NAMES
)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['WTF_CSRF_ENABLED'] = True

# Enable CSRF protection
csrf = CSRFProtect(app)

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
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def election_active_required(f):
    """Decorator to require active election for voting."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_election_active():
            flash('Voting is currently closed.', 'warning')
            return redirect(url_for('dashboard'))
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
        return redirect(url_for('dashboard'))
    
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
            return redirect(url_for('dashboard'))
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
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        
        # Simple admin password check
        ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
        
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
    """Voting dashboard showing all categories."""
    user = get_user_by_id(session['user_id'])
    voter_hash = generate_voter_hash(user['id'], app.secret_key)
    voted_categories = get_voted_categories(voter_hash)
    
    categories_status = []
    for cat in CATEGORIES:
        categories_status.append({
            'code': cat,
            'name': CATEGORY_NAMES[cat],
            'voted': cat in voted_categories
        })
    
    all_voted = len(voted_categories) == len(CATEGORIES)
    
    return render_template(
        'dashboard.html',
        categories=categories_status,
        all_voted=all_voted,
        election_active=is_election_active()
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
    
    return render_template(
        'admin.html',
        results=results,
        election_status=election_status,
        total_voters=total_voters,
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
