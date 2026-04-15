-- Migration: 002_add_jsonb_for_onboarding.sql
-- Created: JSONB support for flexible onboarding data
-- FIX 2.23: Replace TEXT JSON with proper PostgreSQL JSONB column

-- Up:
CREATE TABLE IF NOT EXISTS onboarding_data (
  id SERIAL PRIMARY KEY,
  user_id INTEGER UNIQUE NOT NULL,
  learning_goals JSONB DEFAULT '[]'::jsonb,
  preferred_topics JSONB DEFAULT '[]'::jsonb,
  skill_level TEXT DEFAULT 'beginner',
  preferred_language TEXT DEFAULT 'en',
  onboarded_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_onboarding_user ON onboarding_data(user_id);

-- Down:
-- DROP TABLE IF EXISTS onboarding_data;
