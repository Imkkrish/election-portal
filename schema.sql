-- Election Portal Database Schema
-- SQLite-based schema for club member elections

-- Users table (passwordless - uses email + CCPC profile for auth)
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  ccpc_profile_id TEXT NOT NULL,
  is_admin BOOLEAN DEFAULT FALSE
);

-- Candidates table with category constraint
CREATE TABLE IF NOT EXISTS candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('VP','GS','JS1','JS2','EXEC_TECH','EXEC_DESIGN','EXEC_PR'))
);

-- Votes table - UNIQUE constraint prevents double voting
CREATE TABLE IF NOT EXISTS votes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category TEXT NOT NULL CHECK (category IN ('VP','GS','JS1','JS2','EXEC_TECH','EXEC_DESIGN','EXEC_PR')),
  candidate_id INTEGER NOT NULL,
  voter_hash TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(category, voter_hash),
  FOREIGN KEY (candidate_id) REFERENCES candidates(id)
);

-- Election configuration (singleton table - legacy, kept for compatibility)
CREATE TABLE IF NOT EXISTS election_config (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  is_active BOOLEAN DEFAULT FALSE,
  started_at TIMESTAMP,
  ended_at TIMESTAMP
);

-- Initialize election config
INSERT OR IGNORE INTO election_config (id, is_active) VALUES (1, FALSE);

-- ============ PREFERENCE-BASED RECOMPUTATION TABLES ============

-- Per-position election configuration (admin toggles each position ON/OFF)
CREATE TABLE IF NOT EXISTS election_positions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  position_code TEXT NOT NULL UNIQUE,
  position_name TEXT NOT NULL,
  rank_order INTEGER NOT NULL,  -- 1=VP (highest), 2=GS, 3=JS1, etc.
  is_active BOOLEAN DEFAULT FALSE,
  opens_at TIMESTAMP,
  closes_at TIMESTAMP
);

-- Initialize default positions
INSERT OR IGNORE INTO election_positions (position_code, position_name, rank_order) VALUES 
  ('VP', 'Vice President', 1),
  ('GS', 'General Secretary', 2),
  ('JS1', 'Joint Secretary 1', 3),
  ('JS2', 'Joint Secretary 2', 4),
  ('EXEC_TECH', 'Tech Executive', 5),
  ('EXEC_DESIGN', 'Design Executive', 6),
  ('EXEC_PR', 'PR Executive', 7);

-- Ranked preference votes (new voting system)
CREATE TABLE IF NOT EXISTS ranked_votes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  voter_hash TEXT NOT NULL,
  position_code TEXT NOT NULL,
  candidate_id INTEGER NOT NULL,
  preference_rank INTEGER NOT NULL,  -- 1 = first choice, 2 = second, etc.
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(voter_hash, position_code, preference_rank),
  UNIQUE(voter_hash, position_code, candidate_id),
  FOREIGN KEY (candidate_id) REFERENCES candidates(id)
);

-- Track which candidates have been elected (for recomputation)
CREATE TABLE IF NOT EXISTS election_winners (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  position_code TEXT NOT NULL UNIQUE,
  candidate_id INTEGER NOT NULL,
  candidate_name TEXT NOT NULL,
  elected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  vote_count INTEGER,
  FOREIGN KEY (candidate_id) REFERENCES candidates(id)
);
