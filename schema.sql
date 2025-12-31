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

-- Election configuration (singleton table)
CREATE TABLE IF NOT EXISTS election_config (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  is_active BOOLEAN DEFAULT FALSE,
  started_at TIMESTAMP,
  ended_at TIMESTAMP
);

-- Initialize election config
INSERT OR IGNORE INTO election_config (id, is_active) VALUES (1, FALSE);
