"""Embed all forum posts into data/embeddings.db (sqlite-vec) using Gemini.

One-time job. Safe to re-run: it resumes from the last checkpoint.
Parallelized for paid tiers (concurrent batch requests). If a daily quota
is exhausted, progress is saved — run it again the next day.

Progress is written to the meta table so the website can display it
(/api/embeddings/status).

Usage:
    uv run python tools/build_embeddings.py
"""

import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
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
BATCH_SIZE = 100      # texts per API request
WORKERS = 12          # concurrent API requests (Tier 1)
MAX_CHARS = 6000      # safety truncation (limit is 2048 tokens/request text)

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


class DailyQuotaExceeded(Exception):
    pass


def embed_with_retry(texts):
    delay = 20
    for attempt in range(8):
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
                time.sleep(delay)
                delay = min(delay * 2, 300)
            else:
                raise
    raise RuntimeError("Too many rate-limit retries")


def main():
    forum = sqlite3.connect(FORUM_DB, check_same_thread=False)
    vec_conn = sqlite3.connect(VEC_DB, check_same_thread=False)
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

    print("Loading posts...", flush=True)
    rows = forum.execute(
        "SELECT p.rowid, t.title, p.content FROM posts p "
        "JOIN threads t ON t.id = p.thread_id WHERE p.rowid > ? ORDER BY p.rowid",
        (last_rowid,),
    ).fetchall()

    total = len(rows)
    if total == 0:
        print("Nothing to do — all posts embedded.")
        return

    batches = []
    for i in range(0, total, BATCH_SIZE):
        chunk = rows[i : i + BATCH_SIZE]
        texts = [
            ((title or "") + "\n" + (content or "")).strip()[:MAX_CHARS] or "(pusty post)"
            for (_, title, content) in chunk
        ]
        batches.append((chunk, texts))

    print(f"Resuming from rowid {last_rowid}. {total:,} posts in {len(batches):,} batches.", flush=True)

    done = 0
    start = time.time()

    def set_meta(**kv):
        vec_conn.executemany(
            "INSERT OR REPLACE INTO meta VALUES (?, ?)", [(k, str(v)) for k, v in kv.items()]
        )

    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            # map() preserves order -> checkpoints stay contiguous
            for chunk, vecs in zip(
                (b[0] for b in batches),
                pool.map(lambda b: embed_with_retry(b[1]), batches, chunksize=1),
            ):
                with vec_conn:
                    vec_conn.executemany(
                        "INSERT INTO vec_posts(rowid, embedding) VALUES (?, ?)",
                        [(r[0], sqlite_vec.serialize_float32(v)) for r, v in zip(chunk, vecs)],
                    )
                    last_rowid = chunk[-1][0]
                    done += len(chunk)
                    elapsed = time.time() - start
                    rate = done / elapsed * 60 if elapsed else 0
                    set_meta(
                        last_rowid=last_rowid,
                        done=done,
                        total=total,
                        rate_per_min=f"{rate:.0f}",
                        updated_at=int(time.time()),
                    )
                remaining = (total - done) / (rate / 60) / 60 if rate else 0
                print(
                    f"  {done:,}/{total:,} ({done*100//total}%) | "
                    f"{rate:,.0f} posts/min | ETA {remaining:,.0f} min",
                    flush=True,
                )
    except DailyQuotaExceeded:
        print("\nDAILY QUOTA REACHED. Progress saved — run again tomorrow.")
    finally:
        vec_conn.commit()
        n = vec_conn.execute("SELECT COUNT(*) FROM vec_posts").fetchone()[0]
        size_mb = VEC_DB.stat().st_size / 1024 / 1024 if VEC_DB.exists() else 0
        print(f"\nEmbeddings in DB: {n:,} ({VEC_DB}, {size_mb:,.0f} MB)")


if __name__ == "__main__":
    main()
