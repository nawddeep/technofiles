-- Migration: 003_soft_deletes.sql
-- Created: Add soft delete support for audit compliance
-- FIX 2.25: Allow recovery of deleted data via deleted_at timestamp

-- Up:
ALTER TABLE users ADD COLUMN deleted_at TEXT DEFAULT NULL;
ALTER TABLE chat_messages ADD COLUMN deleted_at TEXT DEFAULT NULL;
ALTER TABLE refresh_tokens ADD COLUMN deleted_at TEXT DEFAULT NULL;
ALTER TABLE sessions ADD COLUMN deleted_at TEXT DEFAULT NULL;

-- Indexes for soft delete queries
CREATE INDEX IF NOT EXISTS idx_users_deleted ON users(deleted_at);
CREATE INDEX IF NOT EXISTS idx_messages_deleted ON chat_messages(deleted_at);
CREATE INDEX IF NOT EXISTS idx_tokens_deleted ON refresh_tokens(deleted_at);
CREATE INDEX IF NOT EXISTS idx_sessions_deleted ON sessions(deleted_at);

-- Create audit table for tracking all deletions
CREATE TABLE IF NOT EXISTS deletion_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  table_name TEXT NOT NULL,
  record_id INTEGER NOT NULL,
  user_id INTEGER,
  deleted_by_user_id INTEGER,
  reason TEXT,
  data_backup TEXT,  -- JSON backup of deleted record
  deleted_at TEXT DEFAULT (datetime('now')),
  recoverable BOOLEAN DEFAULT 1,  -- Whether record can be restored
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (deleted_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_deletion_audit_table ON deletion_audit(table_name);
CREATE INDEX IF NOT EXISTS idx_deletion_audit_user ON deletion_audit(user_id);
CREATE INDEX IF NOT EXISTS idx_deletion_audit_deleted_at ON deletion_audit(deleted_at);

-- Down:
-- ALTER TABLE users DROP COLUMN deleted_at;
-- ALTER TABLE chat_messages DROP COLUMN deleted_at;
-- ALTER TABLE refresh_tokens DROP COLUMN deleted_at;
-- ALTER TABLE sessions DROP COLUMN deleted_at;
-- DROP TABLE IF EXISTS deletion_audit;
