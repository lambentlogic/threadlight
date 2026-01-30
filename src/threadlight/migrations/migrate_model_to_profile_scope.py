"""
Migration script: model_scope to profile_scope

This script migrates existing model_scope values to profile_scope in the Threadlight database.
Run this after upgrading to the profile-based architecture.

The migration:
1. Copies model_scope values to profile_scope for capsules
2. Copies model_scope values to profile_scope for conversations
3. Sets profile_scope to NULL for shared memories (where model_scope was NULL or "shared")

Usage:
    python -m threadlight.migrations.migrate_model_to_profile_scope [--db-path ./threadlight.db]
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Optional


def migrate_database(db_path: str, dry_run: bool = False) -> dict[str, int]:
    """
    Migrate model_scope to profile_scope in the database.

    Args:
        db_path: Path to the SQLite database
        dry_run: If True, don't commit changes, just report what would be done

    Returns:
        Dictionary with migration statistics
    """
    stats = {
        "capsules_migrated": 0,
        "conversations_migrated": 0,
        "messages_profile_column_added": False,
        "messages_model_used_column_added": False,
    }

    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    try:
        # Check current schema
        cursor = conn.execute("PRAGMA table_info(capsules)")
        capsule_columns = [row[1] for row in cursor.fetchall()]

        cursor = conn.execute("PRAGMA table_info(conversations)")
        conv_columns = [row[1] for row in cursor.fetchall()]

        cursor = conn.execute("PRAGMA table_info(messages)")
        msg_columns = [row[1] for row in cursor.fetchall()]

        # Add profile_scope column to capsules if needed
        if "profile_scope" not in capsule_columns:
            print("Adding profile_scope column to capsules table...")
            if not dry_run:
                conn.execute("ALTER TABLE capsules ADD COLUMN profile_scope TEXT")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_capsules_profile_scope ON capsules(profile_scope)")

        # Migrate capsule model_scope to profile_scope
        cursor = conn.execute("""
            SELECT COUNT(*) FROM capsules
            WHERE model_scope IS NOT NULL
            AND model_scope != 'shared'
            AND (profile_scope IS NULL OR profile_scope = '')
        """)
        capsules_to_migrate = cursor.fetchone()[0]

        if capsules_to_migrate > 0:
            print(f"Migrating {capsules_to_migrate} capsules from model_scope to profile_scope...")
            if not dry_run:
                conn.execute("""
                    UPDATE capsules
                    SET profile_scope = model_scope
                    WHERE model_scope IS NOT NULL
                    AND model_scope != 'shared'
                    AND (profile_scope IS NULL OR profile_scope = '')
                """)
            stats["capsules_migrated"] = capsules_to_migrate

        # Add profile_scope column to conversations if needed
        if "profile_scope" not in conv_columns:
            print("Adding profile_scope column to conversations table...")
            if not dry_run:
                conn.execute("ALTER TABLE conversations ADD COLUMN profile_scope TEXT")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_profile_scope ON conversations(profile_scope)")

        # Migrate conversation model_scope to profile_scope
        cursor = conn.execute("""
            SELECT COUNT(*) FROM conversations
            WHERE model_scope IS NOT NULL
            AND model_scope != 'shared'
            AND (profile_scope IS NULL OR profile_scope = '')
        """)
        convs_to_migrate = cursor.fetchone()[0]

        if convs_to_migrate > 0:
            print(f"Migrating {convs_to_migrate} conversations from model_scope to profile_scope...")
            if not dry_run:
                conn.execute("""
                    UPDATE conversations
                    SET profile_scope = model_scope
                    WHERE model_scope IS NOT NULL
                    AND model_scope != 'shared'
                    AND (profile_scope IS NULL OR profile_scope = '')
                """)
            stats["conversations_migrated"] = convs_to_migrate

        # Add profile_id column to messages if needed
        if "profile_id" not in msg_columns:
            print("Adding profile_id column to messages table...")
            if not dry_run:
                conn.execute("ALTER TABLE messages ADD COLUMN profile_id TEXT")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_profile_id ON messages(profile_id)")
            stats["messages_profile_column_added"] = True

        # Add model_used column to messages if needed
        if "model_used" not in msg_columns:
            print("Adding model_used column to messages table...")
            if not dry_run:
                conn.execute("ALTER TABLE messages ADD COLUMN model_used TEXT")
            stats["messages_model_used_column_added"] = True

        if not dry_run:
            conn.commit()
            print("Migration completed successfully!")
        else:
            print("Dry run completed. No changes were made.")

    finally:
        conn.close()

    return stats


def verify_migration(db_path: str) -> dict[str, any]:
    """
    Verify that the migration was successful.

    Args:
        db_path: Path to the SQLite database

    Returns:
        Dictionary with verification results
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    results = {}

    try:
        # Check capsules table
        cursor = conn.execute("PRAGMA table_info(capsules)")
        capsule_columns = [row[1] for row in cursor.fetchall()]
        results["capsules_has_profile_scope"] = "profile_scope" in capsule_columns

        # Count capsules by scope
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN profile_scope IS NOT NULL THEN 1 ELSE 0 END) as with_profile,
                SUM(CASE WHEN profile_scope IS NULL THEN 1 ELSE 0 END) as shared
            FROM capsules
        """)
        row = cursor.fetchone()
        results["capsules_total"] = row["total"]
        results["capsules_with_profile_scope"] = row["with_profile"]
        results["capsules_shared"] = row["shared"]

        # Check conversations table
        cursor = conn.execute("PRAGMA table_info(conversations)")
        conv_columns = [row[1] for row in cursor.fetchall()]
        results["conversations_has_profile_scope"] = "profile_scope" in conv_columns

        # Check messages table
        cursor = conn.execute("PRAGMA table_info(messages)")
        msg_columns = [row[1] for row in cursor.fetchall()]
        results["messages_has_profile_id"] = "profile_id" in msg_columns
        results["messages_has_model_used"] = "model_used" in msg_columns

    finally:
        conn.close()

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Migrate model_scope to profile_scope in Threadlight database"
    )
    parser.add_argument(
        "--db-path",
        default="./threadlight.db",
        help="Path to the SQLite database (default: ./threadlight.db)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify the migration was successful"
    )

    args = parser.parse_args()

    if args.verify:
        print(f"Verifying migration in: {args.db_path}")
        results = verify_migration(args.db_path)
        print("\nVerification results:")
        for key, value in results.items():
            print(f"  {key}: {value}")
        return

    print(f"Migrating database: {args.db_path}")
    if args.dry_run:
        print("(DRY RUN - no changes will be made)")

    stats = migrate_database(args.db_path, dry_run=args.dry_run)

    print("\nMigration statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
