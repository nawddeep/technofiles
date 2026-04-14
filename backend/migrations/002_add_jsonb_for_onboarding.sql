-- Migration: 002_add_jsonb_for_onboarding.sql
-- Created: JSONB support for flexible onboarding data
-- FIX 2.23: Replace TEXT JSON with proper PostgreSQL JSONB column

-- Up:
-- For SQLite (no native JSONB), keep TEXT but add JSON_EXTRACT support via triggers
-- For production PostgreSQL, add JSONB column

-- New table schema (when migrating to PostgreSQL):
-- ALTER TABLE users ADD COLUMN onboarding_data JSONB DEFAULT '{}'::jsonb;
-- UPDATE users SET onboarding_data = 
--   CASE 
--     WHEN onboarding_data = '' THEN '{}'::jsonb
--     WHEN onboarding_data IS NOT NULL THEN onboarding_data::jsonb
--     ELSE '{}'::jsonb
--   END;
-- ALTER TABLE users DROP COLUMN onboarding_data_text;

-- For SQLite migration:
CREATE TABLE IF NOT EXISTS onboarding_data (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER UNIQUE NOT NULL,
  learning_goals TEXT DEFAULT '[]',  -- JSON array of goals
  preferred_topics TEXT DEFAULT '[]', -- JSON array of topics
  skill_level TEXT DEFAULT 'beginner', -- beginner, intermediate, advanced
  preferred_language TEXT DEFAULT 'en',
  onboarded_at TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_onboarding_user ON onboarding_data(user_id);

-- Down:
-- DROP TABLE IF EXISTS onboarding_data;
