# 🗳️ Club Election Portal

A secure, web-based election system for club member voting with strict vote integrity rules.

## Features

- **7 Voting Categories**: VP, GS, JS1, JS2, EXEC1, EXEC2, EXEC3
- **One Vote Per Category**: Database-enforced unique constraint
- **Anonymous Voting**: Voter ID hashed with SHA256
- **Time-Locked Voting**: Only when election is active
- **Admin Panel**: Start/Stop election, view results, export CSV
- **CSRF Protection**: All forms protected

## Tech Stack

- **Backend**: Python Flask
- **Database**: SQLite
- **Templates**: Jinja2
- **Auth**: Session-based
- **Security**: werkzeug password hashing, CSRF tokens

## Setup

### 1. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Mac/Linux
# or: venv\Scripts\activate  # Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Initialize Database

```bash
flask init-db
```

Or simply run the app (auto-initializes on first run).

### 4. Run the Application

```bash
python app.py
```

Visit: http://127.0.0.1:5001

## Default Admin Account

- **Email**: admin@club.com
- **Password**: admin123

⚠️ Change this in production!

## CLI Commands

```bash
# Initialize database
flask init-db

# Add a user
flask add-user

# Add a candidate
flask add-candidate
```

## Election Rules

1. Each member votes in all 7 categories: VP, GS, JS1, JS2, EXEC1, EXEC2, EXEC3
2. **One vote per category** - enforced by database constraint
3. Votes are **final** - no edit, no delete
4. Votes are **anonymous** - stored as SHA256 hash
5. Voting only allowed when admin **activates** the election

## API Routes

| Route              | Method   | Description         |
| ------------------ | -------- | ------------------- |
| `/login`           | GET/POST | User login          |
| `/logout`          | GET      | User logout         |
| `/dashboard`       | GET      | Voting dashboard    |
| `/vote/<category>` | GET/POST | Vote in category    |
| `/confirmation`    | GET      | Vote confirmation   |
| `/admin`           | GET      | Admin panel         |
| `/admin/toggle`    | POST     | Start/Stop election |
| `/admin/export`    | GET      | Export results CSV  |

## Schema

```sql
-- Users
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  name TEXT, email TEXT UNIQUE,
  password_hash TEXT, is_admin BOOLEAN
);

-- Candidates
CREATE TABLE candidates (
  id INTEGER PRIMARY KEY,
  name TEXT, category TEXT
);

-- Votes (UNIQUE constraint prevents double voting)
CREATE TABLE votes (
  id INTEGER PRIMARY KEY,
  category TEXT, candidate_id INTEGER,
  voter_hash TEXT,
  UNIQUE(category, voter_hash)
);
```

## Security Notes

- Set `SECRET_KEY` environment variable in production
- Change default admin password
- Run behind HTTPS in production
- Database file (`election.db`) should be secured

## License

Academic use only.
