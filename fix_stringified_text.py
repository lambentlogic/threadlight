#!/usr/bin/env python3
"""
Fix capsules with stringified dicts in the text field.

Some capsules have their text field set to a stringified dict instead of
the actual narrative text. This script extracts the _original_text from
those stringified dicts and sets it as the proper text field.
"""

import ast
import json
import sqlite3
import sys
from pathlib import Path
import os

def fix_stringified_text_fields():
    """Fix capsules where text field contains stringified dicts."""
    # Try project database first, then config
    db_candidates = [
        Path.home() / "Documents" / "Projects" / "threadlight" / "threadlight.db",
        Path.home() / ".config" / "threadlight" / "threadlight.db",
    ]

    db_path = None
    for candidate in db_candidates:
        if candidate.exists():
            db_path = candidate
            break

    if not db_path:
        print(f"Database not found. Tried: {db_candidates}")
        return 0

    print(f"Using database: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Find capsules where text looks like a stringified dict
    cursor = conn.execute("""
        SELECT id, type, text, content
        FROM capsules
        WHERE text IS NOT NULL
          AND text LIKE '{%'
    """)

    rows = cursor.fetchall()
    print(f"Found {len(rows)} capsules with stringified text fields")

    fixed_count = 0
    for row in rows:
        capsule_id = row["id"]
        text_field = row["text"]
        content_field = row["content"]

        try:
            # Parse the stringified dict
            parsed = ast.literal_eval(text_field)

            # Extract _original_text if present
            original_text = parsed.get("_original_text")

            if original_text:
                print(f"\nFixing capsule {capsule_id[:8]}...")
                print(f"  Type: {row['type']}")
                print(f"  Old text (first 100 chars): {text_field[:100]}...")
                print(f"  New text (first 100 chars): {original_text[:100]}...")

                # Update the text field
                conn.execute("""
                    UPDATE capsules
                    SET text = ?
                    WHERE id = ?
                """, (original_text, capsule_id))

                fixed_count += 1
            else:
                # No _original_text, try to extract 'text' from the parsed dict
                fallback_text = parsed.get("text")
                if fallback_text:
                    print(f"\nFixing capsule {capsule_id[:8]} (no _original_text, using 'text')...")
                    conn.execute("""
                        UPDATE capsules
                        SET text = ?
                        WHERE id = ?
                    """, (fallback_text, capsule_id))
                    fixed_count += 1
                else:
                    print(f"\nWarning: Capsule {capsule_id[:8]} has stringified dict but no _original_text or text field")

        except (ValueError, SyntaxError) as e:
            print(f"\nError parsing text for capsule {capsule_id[:8]}: {e}")
            continue

    conn.commit()
    conn.close()

    print(f"\n✅ Fixed {fixed_count} capsules")
    return fixed_count

if __name__ == "__main__":
    fix_stringified_text_fields()
