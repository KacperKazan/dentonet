"""Build the SQLite database (data/dentonet.db) from the MongoDB JSON export.

Usage:
    uv run python tools/build_db.py <path_to_database_export_folder>

The export folder should contain one <collection>.json file per forum,
in mongoexport format (one JSON document per line, extended JSON types
like {"$oid": ...} and {"$date": ...}).
"""

import json
import sqlite3
import sys
from pathlib import Path

# Avoid console encoding crashes on Windows when printing Polish names
sys.stdout.reconfigure(errors="replace")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "dentonet.db"

# Fallback section mapping (normally the section is read from the data itself)
COLLECTION_TO_SECTION = {
    "Dla wszystkich": "DLA WSZYSTKICH",
    "Pomoc techniczna": "DLA WSZYSTKICH",
    "Forum ogólnostomatologiczne": "DLA DENTYSTÓW",
    "Sprzęt i materiały": "DLA DENTYSTÓW",
    "Z praktyki wzięte  przypadki": "DLA DENTYSTÓW",
    "NFZ": "DLA DENTYSTÓW",
    "Ankiety": "DLA DENTYSTÓW",
    "Forum specjalistyczne": "DLA DENTYSTÓW",
    "Po godzinach": "DLA DENTYSTÓW",
    "Dla asystentek i higienistek": "DLA ASYSTENTEK",
    "Dla studentów": "DLA STUDENTÓW",
    "Sprawy forum": "DLA MODERATORÓW",
}


def parse_value(value):
    """Convert mongoexport extended-JSON values to plain Python values."""
    if isinstance(value, dict):
        if "$oid" in value:
            return value["$oid"]
        if "$date" in value:
            # "2010-01-08T14:40:00Z" -> "2010-01-08 14:40:00"
            return value["$date"].replace("T", " ").rstrip("Z")
        return {k: parse_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [parse_value(v) for v in value]
    return value


def main(export_dir):
    export_dir = Path(export_dir)
    json_files = sorted(export_dir.glob("*.json"))
    if not json_files:
        sys.exit(f"No .json files found in {export_dir}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    conn.executescript(
        """
        CREATE TABLE threads (
            id TEXT PRIMARY KEY,
            collection TEXT NOT NULL,
            section TEXT NOT NULL,
            title TEXT,
            link TEXT,
            author TEXT,
            date TEXT,
            num_replies INTEGER,
            latest_post_datetime TEXT,
            announcement INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE posts (
            thread_id TEXT NOT NULL,
            idx INTEGER NOT NULL,
            author TEXT,
            datetime TEXT,
            content TEXT,
            html TEXT
        );
        """
    )

    total_threads = 0
    total_posts = 0
    for json_file in json_files:
        collection = json_file.stem
        section_fallback = COLLECTION_TO_SECTION.get(collection, "")
        threads_in_file = 0

        with open(json_file, encoding="utf-8") as f, conn:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                doc = parse_value(json.loads(line))
                posts = doc.get("posts") or []
                section = (doc.get("forum") or {}).get("section") or section_fallback
                latest = doc.get("latest_post_datetime") or doc.get("date") or ""

                conn.execute(
                    "INSERT OR IGNORE INTO threads VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        doc["_id"],
                        collection,
                        section,
                        doc.get("title", ""),
                        doc.get("link", ""),
                        (doc.get("author") or {}).get("username", ""),
                        doc.get("date", ""),
                        doc.get("num_replies", 0),
                        latest,
                        1 if doc.get("announcement") else 0,
                    ),
                )
                conn.executemany(
                    "INSERT INTO posts VALUES (?,?,?,?,?,?)",
                    (
                        (
                            doc["_id"],
                            i,
                            (p.get("author") or {}).get("username", ""),
                            p.get("datetime", ""),
                            p.get("content", ""),
                            p.get("html", ""),
                        )
                        for i, p in enumerate(posts)
                    ),
                )
                threads_in_file += 1
                total_posts += len(posts)

        total_threads += threads_in_file
        print(f"{collection}: {threads_in_file} threads")

    with conn:
        conn.execute(
            "CREATE INDEX idx_threads_collection ON threads "
            "(collection, announcement, latest_post_datetime DESC)"
        )
        conn.execute("CREATE INDEX idx_posts_thread ON posts (thread_id, idx)")

    conn.close()
    size_mb = DB_PATH.stat().st_size / 1024 / 1024
    print(f"\nDone: {total_threads} threads, {total_posts} posts")
    print(f"Database written to {DB_PATH} ({size_mb:.0f} MB)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
