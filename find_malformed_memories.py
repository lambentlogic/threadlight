#!/usr/bin/env python3
"""
Find memories with potentially malformed text fields.

Helps identify memories that may need manual editing or re-import to restore proper narrative text.
"""

import sqlite3
import json
from pathlib import Path

def find_malformed_memories():
    """Find capsules where text field might be malformed."""
    db_path = Path.home() / "Documents" / "Projects" / "threadlight" / "threadlight.db"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    print("🔍 Searching for memories with potentially malformed text...\n")

    # Category 1: Text starts with dict syntax
    cursor = conn.execute("""
        SELECT id, type, text
        FROM capsules
        WHERE text IS NOT NULL
          AND (text LIKE '{%' OR text LIKE '[%')
        ORDER BY type, id
    """)

    dict_like = cursor.fetchall()

    # Category 2: Text is very short (might be truncated)
    cursor = conn.execute("""
        SELECT id, type, text
        FROM capsules
        WHERE text IS NOT NULL
          AND length(text) < 50
          AND type IN ('relational', 'witness', 'myth_seed')
        ORDER BY type, id
    """)

    short_text = cursor.fetchall()

    # Category 3: Text contains escaped quotes (might be stringified JSON)
    cursor = conn.execute("""
        SELECT id, type, text
        FROM capsules
        WHERE text IS NOT NULL
          AND text LIKE '%\\"%'
        ORDER BY type, id
    """)

    escaped_quotes = cursor.fetchall()

    # Print results
    if dict_like:
        print(f"📋 **Memories with dict-like text** ({len(dict_like)} found)")
        print("   These likely have stringified dicts that couldn't be fully recovered:\n")
        for row in dict_like:
            entity = ""
            try:
                content = json.loads(row["text"].replace("'", '"'))
                if isinstance(content, dict):
                    entity = content.get("entity", content.get("moment", ""))
            except:
                pass

            print(f"   {row['id'][:8]} ({row['type']}) {entity}")
            print(f"      Preview: {row['text'][:80]}...")
            print()

    if short_text:
        print(f"\n⚠️  **Memories with suspiciously short text** ({len(short_text)} found)")
        print("   These might be truncated or missing narrative:\n")
        for row in short_text:
            print(f"   {row['id'][:8]} ({row['type']})")
            print(f"      Text: {row['text']}")
            print()

    if escaped_quotes:
        print(f"\n🔗 **Memories with escaped quotes** ({len(escaped_quotes)} found)")
        print("   These might have stringified JSON:\n")
        for row in escaped_quotes:
            print(f"   {row['id'][:8]} ({row['type']})")
            print(f"      Preview: {row['text'][:80]}...")
            print()

    # Summary
    total_issues = len(dict_like) + len(short_text) + len(escaped_quotes)
    if total_issues == 0:
        print("✅ No obviously malformed memories found!")
    else:
        print(f"\n📊 Summary: {total_issues} memories may need attention")
        print(f"   - Dict-like: {len(dict_like)}")
        print(f"   - Short text: {len(short_text)}")
        print(f"   - Escaped quotes: {len(escaped_quotes)}")

    conn.close()

if __name__ == "__main__":
    find_malformed_memories()
