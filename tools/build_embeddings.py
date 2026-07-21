"""Embed all forum posts into data/embeddings.db (sqlite-vec) using Gemini.

One-time job. Safe to re-run: it resumes from the last checkpoint.
Rate limits: batches of 100 texts/request, backs off on 429. If the daily
free-tier quota is exhausted, it saves progress and exits — just run it
again the next day.

Usage:
    uv run python tools/build_embeddings.py
"""

import os
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FORUM_DB = ROOT / "data" / "dentonet.db"
VEC_DB = ROOT / "data" / "embeddings.db"

for line in open(ROOT / ".env"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v)

from google import genai
from google.genai import types
import sqlite_vec

MODEL = "gemini-embedding-001"
DIMS = 768
BATCH_SIZE = 100
MAX_CHARS = 6000  # safety truncation (limit is 2048 tokens/request text)

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

forum = sqlite3.connect(FORUM_DB)
vec_conn = sqlite3.connect(VEC_DB)
vec_conn.enable_load_extension(True)
sqlite_vec.load(vec_conn)
vec_conn.execute("PRAGMA journal_mode = WAL")
vec_conn.executescript(
    f"""
    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
    CREATE VIRTUAL TABLE IF NOT EXISTS vec_posts USING vec0(embedding float[{DIMS}]);
    """
)
last_rowid = int(
    (vec_conn.execute("SELECT value FROM meta WHERE key='last_rowid'").fetchone() or ["0"])[0]
)

total = forum.execute("SELECT COUNT(*) FROM posts WHERE rowid > ?", (last_rowid,)).fetchone()[0]
if total == 0:
    print("Nothing to do — all posts embedded.")
    sys.exit(0)

print(f"Resuming from rowid {last_rowid}. {total:,} posts to embed.")
done = 0
start = time.time()


def fetch_batch(after_rowid):
    return forum.execute(
        "SELECT p.rowid, p.thread_id, t.title, p.content FROM posts p "
        "JOIN threads t ON t.id = p.thread_id "
        "WHERE p.rowid > ? ORDER BY p.rowid LIMIT ?",
        (after_rowid, BATCH_SIZE),
    ).fetchall()


def embed_with_retry(texts):
    """Returns embeddings list, or raises DailyQuotaExceeded."""
    delay = 30
    for attempt in range(6):
        try:
            r = client.models.embed_content(
                model=MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=DIMS, task_type="RETRIEVAL_DOCUMENT"
                ),
            )
            return [e.values for e in r.embeddings]
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                if "per_day" in msg or "daily" in msg.lower() or "PerDay" in msg:
                    raise DailyQuotaExceeded(msg)
                print(f"\n  rate limited, waiting {delay}s (attempt {attempt+1}/6)")
                time.sleep(delay)
                delay = min(delay * 2, 300)
            else:
                raise
    raise RuntimeError("Too many rate-limit retries")


class DailyQuotaExceeded(Exception):
    pass


try:
    while True:
        rows = fetch_batch(last_rowid)
        if not rows:
            break
        texts = [
            ((title or "") + "\n" + (content or "")).strip()[:MAX_CHARS] or "(pusty post)"
            for (_, _, title, content) in rows
        ]
        try:
            vecs = embed_with_retry(texts)
        except DailyQuotaExceeded as e:
            print("\n\nDAILY QUOTA REACHED. Progress saved.")
            print("Run this script again tomorrow to continue.")
            break

        with vec_conn:
            vec_conn.executemany(
                "INSERT INTO vec_posts(rowid, embedding) VALUES (?, ?)",
                [(r[0], sqlite_vec.serialize_float32(v)) for r, v in zip(rows, vecs)],
            )
            last_rowid = rows[-1][0]
            vec_conn.execute(
                "INSERT OR REPLACE INTO meta VALUES ('last_rowid', ?)", (str(last_rowid),)
            )
        done += len(rows)
        elapsed = time.time() - start
        rate = done / elapsed if elapsed else 0
        remaining = (total - done) / rate / 60 if rate else 0
        print(
            f"  {done:,}/{total:,} posts ({done*100//total}%) "
            f"| {rate:,.0f} posts/min | ETA {remaining:,.0f} min",
            flush=True,
        )
        time.sleep(0.5)  # be gentle with the free tier
finally:
    vec_conn.commit()
    n = vec_conn.execute("SELECT COUNT(*) FROM vec_posts").fetchone()[0]
    size_mb = VEC_DB.stat().st_size / 1024 / 1024 if VEC_DB.exists() else 0
    print(f"\nEmbeddings in DB: {n:,} ({VEC_DB}, {size_mb:,.0f} MB)")
