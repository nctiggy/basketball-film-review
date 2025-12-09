#!/usr/bin/env python3
"""Database migration runner.

This script runs SQL migrations in order and tracks which migrations have been applied.
It is idempotent and safe to run multiple times.

Usage:
    python migrate.py              # Run all pending migrations
    python migrate.py --dry-run    # Show which migrations would be run
    python migrate.py --reset      # Reset migration tracking (danger!)
"""
import asyncio
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime
import asyncpg


async def create_migrations_table(conn: asyncpg.Connection):
    """Create the schema_migrations table if it doesn't exist."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT NOW(),
            description TEXT
        );
    """)
    print("Migration tracking table ready")


async def get_applied_migrations(conn: asyncpg.Connection) -> set:
    """Get the set of already-applied migration versions."""
    rows = await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
    return {row['version'] for row in rows}


def find_migration_files(migrations_dir: Path) -> list:
    """Find all SQL migration files in order.

    Returns list of tuples: (version, filename, full_path, description)
    """
    migrations = []

    if not migrations_dir.exists():
        print(f"Warning: Migrations directory not found: {migrations_dir}")
        return migrations

    for file_path in sorted(migrations_dir.glob("*.sql")):
        # Extract version from filename (e.g., "001_add_users_teams_auth.sql" -> "001")
        filename = file_path.name
        parts = filename.split('_', 1)

        if len(parts) != 2:
            print(f"Warning: Skipping invalid migration filename: {filename}")
            continue

        version = parts[0]
        description = parts[1].replace('.sql', '').replace('_', ' ')

        migrations.append((version, filename, file_path, description))

    return migrations


async def apply_migration(conn: asyncpg.Connection, version: str, file_path: Path, description: str, dry_run: bool = False):
    """Apply a single migration file."""
    print(f"\nApplying migration {version}: {description}")

    # Read the migration SQL
    sql = file_path.read_text()

    if dry_run:
        print(f"  [DRY RUN] Would execute SQL from: {file_path}")
        print(f"  [DRY RUN] SQL preview (first 200 chars): {sql[:200]}...")
        return

    try:
        # Execute the migration in a transaction
        async with conn.transaction():
            # Run the migration SQL
            await conn.execute(sql)

            # Record that this migration has been applied
            await conn.execute(
                """
                INSERT INTO schema_migrations (version, applied_at, description)
                VALUES ($1, $2, $3)
                ON CONFLICT (version) DO NOTHING
                """,
                version,
                datetime.now(),
                description
            )

        print(f"  SUCCESS: Migration {version} applied")

    except Exception as e:
        print(f"  ERROR: Failed to apply migration {version}")
        print(f"  {type(e).__name__}: {e}")
        raise


async def reset_migrations(conn: asyncpg.Connection, dry_run: bool = False):
    """Reset migration tracking table (DANGER!)."""
    if dry_run:
        print("[DRY RUN] Would drop and recreate schema_migrations table")
        return

    print("WARNING: Resetting migration tracking...")
    await conn.execute("DROP TABLE IF EXISTS schema_migrations")
    await create_migrations_table(conn)
    print("Migration tracking has been reset")


async def run_migrations(database_url: str, migrations_dir: Path, dry_run: bool = False, reset: bool = False):
    """Main migration runner."""
    print(f"Database: {database_url.split('@')[-1]}")  # Hide credentials
    print(f"Migrations directory: {migrations_dir}")
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}")
    print("-" * 60)

    # Connect to database
    try:
        conn = await asyncpg.connect(database_url)
    except Exception as e:
        print(f"ERROR: Failed to connect to database")
        print(f"  {type(e).__name__}: {e}")
        sys.exit(1)

    try:
        # Handle reset if requested
        if reset:
            await reset_migrations(conn, dry_run)
            if not dry_run:
                return  # Exit after reset

        # Create migrations table if needed
        await create_migrations_table(conn)

        # Get already-applied migrations
        applied = await get_applied_migrations(conn)
        print(f"\nApplied migrations: {len(applied)}")
        for version in sorted(applied):
            print(f"  - {version}")

        # Find all migration files
        migrations = find_migration_files(migrations_dir)
        print(f"\nFound {len(migrations)} migration files")

        # Determine which migrations need to be applied
        pending = [(v, fn, fp, desc) for v, fn, fp, desc in migrations if v not in applied]

        if not pending:
            print("\nNo pending migrations to apply")
            return

        print(f"\nPending migrations: {len(pending)}")
        for version, filename, _, description in pending:
            print(f"  - {version}: {description}")

        # Apply each pending migration
        print("\n" + "=" * 60)
        for version, filename, file_path, description in pending:
            await apply_migration(conn, version, file_path, description, dry_run)

        print("\n" + "=" * 60)
        if dry_run:
            print("DRY RUN complete - no changes made")
        else:
            print(f"SUCCESS: Applied {len(pending)} migrations")

    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which migrations would be run without applying them"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset migration tracking table (DANGER!)"
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Database connection URL (default: DATABASE_URL env var)"
    )
    parser.add_argument(
        "--migrations-dir",
        default="migrations",
        help="Directory containing migration files (default: migrations)"
    )

    args = parser.parse_args()

    # Validate database URL
    if not args.database_url:
        print("ERROR: DATABASE_URL environment variable not set and --database-url not provided")
        sys.exit(1)

    # Get absolute path to migrations directory
    migrations_dir = Path(args.migrations_dir)
    if not migrations_dir.is_absolute():
        # Assume relative to script location
        script_dir = Path(__file__).parent
        migrations_dir = (script_dir.parent / migrations_dir).resolve()

    # Run migrations
    asyncio.run(run_migrations(
        database_url=args.database_url,
        migrations_dir=migrations_dir,
        dry_run=args.dry_run,
        reset=args.reset
    ))


if __name__ == "__main__":
    main()
