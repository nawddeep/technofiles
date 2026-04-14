# Database Migrations

FIX 2.16: Version-controlled database schema changes using migration scripts.

## Format

Migrations are numbered: `001_initial_schema.sql`, `002_add_feature.sql`, etc.

Each migration file contains:
- Up migration: Changes to apply
- Down migration: How to revert

## Tracking

The `schema_version` table tracks applied migrations.

## Running Migrations

```bash
# Apply all new migrations
python -m migrations

# Specific migration
python manage.py migrate 001_initial_schema

# Rollback last migration
python manage.py migrate --rollback
```

## Creating New Migrations

```sql
-- Migration: 003_feature_name.sql
-- Up:
ALTER TABLE users ADD COLUMN deleted_at TEXT;

-- Down:
ALTER TABLE users DROP COLUMN deleted_at;
```
