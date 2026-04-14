#!/usr/bin/env python3
"""
FIX 2.16: Database migration runner with version tracking and rollback support
Usage:
  python migrations/migrate.py           # Run all pending migrations
  python migrations/migrate.py --status  # Show migration status
  python migrations/migrate.py --rollback # Rollback last migration
"""
import os
import sys
import sqlite3
import glob
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db

MIGRATIONS_DIR = os.path.dirname(__file__)


def init_version_table():
    """Create schema_version table if it doesn't exist"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT UNIQUE NOT NULL,
            applied_at TEXT DEFAULT (datetime('now')),
            description TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_applied_migrations():
    """Get list of already-applied migrations"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM schema_version ORDER BY version")
    versions = [row[0] for row in cursor.fetchall()]
    conn.close()
    return versions


def get_all_migrations():
    """Get all migration files in order"""
    migrations = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
    return [os.path.basename(m).replace(".sql", "") for m in migrations]


def parse_migration_file(filepath):
    """Parse migration file into up and down sections"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    parts = {'comment': '', 'up': '', 'down': ''}
    
    # Extract comment (header)
    lines = content.split('\n')
    for line in lines[:5]:
        if line.startswith('--'):
            parts['comment'] += line + '\n'
    
    # Split up/down
    if '-- Up:' in content:
        up_start = content.find('-- Up:') + len('-- Up:')
        down_start = content.find('-- Down:')
        parts['up'] = content[up_start:down_start].strip() if down_start > 0 else content[up_start:].strip()
        if down_start > 0:
            parts['down'] = content[down_start + len('-- Down:'):].strip()
    
    return parts


def apply_migration(version):
    """Apply a single migration"""
    filepath = os.path.join(MIGRATIONS_DIR, version + ".sql")
    if not os.path.exists(filepath):
        print(f"❌ Migration file not found: {filepath}")
        return False
    
    parts = parse_migration_file(filepath)
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Execute up migration
        statements = [s.strip() for s in parts['up'].split(';') if s.strip() and not s.strip().startswith('--')]
        for stmt in statements:
            cursor.execute(stmt)
        
        # Record migration
        cursor.execute("INSERT INTO schema_version (version, description) VALUES (?, ?)", 
                      (version, parts['comment'].strip()))
        conn.commit()
        print(f"✅ Applied migration: {version}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ Error applying migration {version}: {e}")
        return False
    finally:
        conn.close()


def rollback_migration(version):
    """Rollback a single migration"""
    filepath = os.path.join(MIGRATIONS_DIR, version + ".sql")
    if not os.path.exists(filepath):
        print(f"❌  Migration file not found: {filepath}")
        return False
    
    parts = parse_migration_file(filepath)
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Execute down migration
        statements = [s.strip() for s in parts['down'].split(';') if s.strip() and not s.strip().startswith('--')]
        for stmt in statements:
            cursor.execute(stmt)
        
        # Remove migration record
        cursor.execute("DELETE FROM schema_version WHERE version = ?", (version,))
        conn.commit()
        print(f"✅ Rolled back migration: {version}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ Error rolling back migration {version}: {e}")
        return False
    finally:
        conn.close()


def show_status():
    """Show which migrations have been applied"""
    init_version_table()
    applied = get_applied_migrations()
    all_migrations = get_all_migrations()
    
    print("\n📊 Migration Status")
    print("=" * 50)
    for mig in all_migrations:
        status = "✅ Applied  " if mig in applied else "⏳ Pending"
        print(f"{status}  {mig}")
    print("=" * 50)
    print(f"Applied: {len(applied)}/{len(all_migrations)}\n")


def main():
    """Main migration runner"""
    init_version_table()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--status':
            show_status()
            return
        elif sys.argv[1] == '--rollback':
            applied = get_applied_migrations()
            if applied:
                last = applied[-1]
                if rollback_migration(last):
                    print("Successfully rolled back last migration")
            else:
                print("❌ No migrations to rollback")
            return
    
    # Apply all pending migrations
    applied = get_applied_migrations()
    all_migrations = get_all_migrations()
    pending = [m for m in all_migrations if m not in applied]
    
    if not pending:
        print("✅ All migrations applied")
        return
    
    print(f"📦 Applying {len(pending)} pending migration(s)...\n")
    for mig in pending:
        if not apply_migration(mig):
            print(f"❌ Migration failed at {mig}, stopping")
            sys.exit(1)
    
    print(f"\n✅ All{len(pending)} migrations applied successfully")
    show_status()


if __name__ == '__main__':
    main()
