import html as html_mod
import json
import math
import os
import re
import sqlite3
import threading
import webbrowser
from collections import defaultdict
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request, url_for
from flask_paginate import Pagination, get_page_parameter

THREADS_PER_FORUM_PAGE = 50
POSTS_PER_THREAD_PAGE = 10

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "dentonet.db"
VEC_DB_PATH = BASE_DIR / "data" / "embeddings.db"
CHATS_DB_PATH = BASE_DIR / "data" / "chats.db"

# Load .env (never committed to git)
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in open(_env_file):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.strip().split("=", 1)
            os.environ.setdefault(_k, _v)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "gemini-3-flash-preview")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "gemini-embedding-001")
EMBED_DIMS = 768
TOP_K = 8  # posts retrieved per question

app = Flask(__name__)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def row_to_thread(row):
    """Shape a threads-table row like the old MongoDB document (for templates)."""
    return {
        "_id": row["id"],
        "title": row["title"],
        "author": {"username": row["author"]},
        "date": row["date"],
        "latest_post_datetime": row["latest_post_datetime"],
        "num_replies": row["num_replies"],
    }


@app.route("/")
def main():
    db = get_db()
    rows = db.execute(
        "SELECT collection, section, COUNT(*) AS n FROM threads "
        "GROUP BY collection ORDER BY section, collection"
    ).fetchall()
    sections = defaultdict(list)
    for row in rows:
        sections[row["section"]].append(
            {"collection_name": row["collection"], "num_threads": row["n"]}
        )
    return render_template("main.html", sections=sections)


@app.route("/forum/<collection_name>")
def forum(collection_name):
    db = get_db()

    announcements = [
        row_to_thread(r)
        for r in db.execute(
            "SELECT * FROM threads WHERE collection = ? AND announcement = 1",
            (collection_name,),
        )
    ]

    len_topics = db.execute(
        "SELECT COUNT(*) FROM threads WHERE collection = ? AND announcement = 0",
        (collection_name,),
    ).fetchone()[0]

    page = request.args.get(get_page_parameter(), type=int, default=1)
    topics_pagination = Pagination(
        page=page,
        per_page=THREADS_PER_FORUM_PAGE,
        total=len_topics,
        css_framework="bootstrap4",
    )

    total_pages = math.ceil(len_topics / THREADS_PER_FORUM_PAGE)
    next_page = min(page + 1, total_pages)
    prev_page = max(page - 1, 1)

    topics_page = [
        row_to_thread(r)
        for r in db.execute(
            "SELECT * FROM threads WHERE collection = ? AND announcement = 0 "
            "ORDER BY latest_post_datetime DESC LIMIT ? OFFSET ?",
            (collection_name, THREADS_PER_FORUM_PAGE, (page - 1) * THREADS_PER_FORUM_PAGE),
        )
    ]

    return render_template(
        "forum.html",
        collection_name=collection_name,
        announcements=announcements,
        topics=topics_page,
        topics_pagination=topics_pagination,
        num_pages=total_pages,
        next_page=next_page,
        prev_page=prev_page,
    )


def parse_html(html):
    html = html.replace("&lt;", "<")
    html = html.replace("&gt;", ">")
    return html


def parse_and_mark_html(x, mark):
    x = parse_html(x)
    if mark and mark in x:
        mark_not_in_href = True
        for href in re.findall(r'href="([^"]*)"', x):
            if mark in href:
                mark_not_in_href = False
                break
        if mark_not_in_href:
            x = x.replace(mark, f"<mark>{mark}</mark>")
    return x


@app.route("/thread/<collection_name>/<thread_id>")
@app.route("/thread/<collection_name>/<thread_id>/<int:page>")
@app.route("/thread/<collection_name>/<thread_id>/<int:page>/<mark>")
def thread(collection_name, thread_id, page=1, mark=""):
    db = get_db()
    row = db.execute(
        "SELECT * FROM threads WHERE collection = ? AND id = ?",
        (collection_name, thread_id),
    ).fetchone()
    if row is None:
        return "Thread not found", 404

    thread = row_to_thread(row)

    all_posts = db.execute(
        "SELECT * FROM posts WHERE thread_id = ? ORDER BY idx", (thread_id,)
    ).fetchall()

    num_pages = int(math.ceil(len(all_posts) / POSTS_PER_THREAD_PAGE))

    start_idx = (page - 1) * POSTS_PER_THREAD_PAGE
    end_idx = start_idx + POSTS_PER_THREAD_PAGE
    paginated_posts = [
        {
            "idx": p["idx"],
            "author": {"username": p["author"]},
            "datetime": p["datetime"],
            "content": p["content"],
            "html": p["html"],
        }
        for p in all_posts[start_idx:end_idx]
    ]

    prev_page = page - 1 if page > 1 else None
    next_page = page + 1 if page < num_pages else None
    pages = []
    for i in range(1, num_pages + 1):
        if i == page:
            pages.append({"num": i, "url": None})
        else:
            pages.append(
                {
                    "num": i,
                    "url": url_for(
                        "thread",
                        collection_name=collection_name,
                        thread_id=thread_id,
                        page=i,
                    ),
                }
            )

    return render_template(
        "thread.html",
        collection_name=collection_name,
        thread=thread,
        posts=paginated_posts,
        prev_page=prev_page,
        next_page=next_page,
        pages=pages,
        num_pages=num_pages,
        current_page=page,
        parse_html=parse_and_mark_html,
        mark=mark,
    )


def like_escape(query):
    """Escape LIKE wildcards so the query is treated as a literal substring."""
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@app.route("/search", methods=["GET", "POST"])
def search():
    search_query = str(request.args.get("search_query"))
    db = get_db()

    all_results = defaultdict(list)

    rows = db.execute(
        "SELECT p.thread_id, p.idx, p.content, p.html, t.collection, t.title "
        "FROM posts p JOIN threads t ON t.id = p.thread_id "
        "WHERE p.content LIKE ? ESCAPE '\\'",
        (f"%{like_escape(search_query)}%",),
    )

    for row in rows:
        if search_query not in row["content"]:
            continue

        html = parse_and_mark_html(row["html"], search_query)
        thread_page_index = math.ceil((row["idx"] + 1) / POSTS_PER_THREAD_PAGE)
        thread_page_link = url_for(
            "thread",
            collection_name=row["collection"],
            thread_id=row["thread_id"],
            page=thread_page_index,
            mark=search_query,
        )
        search_result = {
            "thread_id": row["thread_id"],
            "thread_title": row["title"],
            "html": html,
            "thread_link": thread_page_link,
        }
        all_results[row["collection"]].append(search_result)

    total_results = sum(len(results) for results in all_results.values())
    return render_template(
        "search.html",
        search_query=search_query,
        all_results=all_results,
        total_results=total_results,
    )


# ---------------------------------------------------------------------------
# Chat (RAG over the forum archive)
# ---------------------------------------------------------------------------

_genai_client = None


def get_genai():
    global _genai_client
    if _genai_client is None:
        from google import genai

        _genai_client = genai.Client(api_key=GEMINI_API_KEY)
    return _genai_client


def get_vecdb():
    if "vecdb" not in g:
        import sqlite_vec

        g.vecdb = sqlite3.connect(VEC_DB_PATH)
        g.vecdb.enable_load_extension(True)
        sqlite_vec.load(g.vecdb)
    return g.vecdb


def get_chatsdb():
    if "chatsdb" not in g:
        g.chatsdb = sqlite3.connect(CHATS_DB_PATH)
        g.chatsdb.row_factory = sqlite3.Row
        g.chatsdb.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                favorite INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources_json TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            """
        )
        # migrate old dbs that are missing the favorite column
        cols = [c[1] for c in g.chatsdb.execute("PRAGMA table_info(conversations)")]
        if "favorite" not in cols:
            g.chatsdb.execute("ALTER TABLE conversations ADD COLUMN favorite INTEGER DEFAULT 0")
    return g.chatsdb


@app.teardown_appcontext
def close_extra_dbs(exception):
    for key in ("vecdb", "chatsdb"):
        db = g.pop(key, None)
        if db is not None:
            db.close()


def chat_available():
    return bool(GEMINI_API_KEY) and VEC_DB_PATH.exists()


def gemini_with_retry(fn, attempts=4):
    """Retry Gemini calls on 429 (the embedding build can saturate the quota)."""
    import time

    delay = 20
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:
            msg = str(e)
            if ("429" in msg or "RESOURCE_EXHAUSTED" in msg) and attempt < attempts - 1:
                time.sleep(delay)
                delay = min(delay * 2, 90)
            else:
                raise


def embed_query(text):
    from google.genai import types

    r = gemini_with_retry(
        lambda: get_genai().models.embed_content(
            model=EMBED_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBED_DIMS, task_type="RETRIEVAL_QUERY"
            ),
        )
    )
    return r.embeddings[0].values


def retrieve_posts(query, k=TOP_K):
    """KNN search over post embeddings; returns source dicts with URLs."""
    import sqlite_vec

    vec = embed_query(query)
    rows = get_vecdb().execute(
        "SELECT rowid, distance FROM vec_posts WHERE embedding MATCH ? AND k = ?",
        (sqlite_vec.serialize_float32(vec), k),
    ).fetchall()

    db = get_db()
    sources = []
    for i, (post_rowid, distance) in enumerate(rows, start=1):
        p = db.execute(
            "SELECT p.thread_id, p.idx, p.author, p.datetime, p.content, "
            "t.collection, t.title FROM posts p "
            "JOIN threads t ON t.id = p.thread_id WHERE p.rowid = ?",
            (post_rowid,),
        ).fetchone()
        if p is None:
            continue
        page = math.ceil((p["idx"] + 1) / POSTS_PER_THREAD_PAGE)
        url_kwargs = dict(
            collection_name=p["collection"], thread_id=p["thread_id"], page=page
        )
        if query and query in p["content"]:
            url_kwargs["mark"] = query
        # scroll to exact post and highlight it
        url = url_for("thread", **url_kwargs) + f"#post-{p['idx']}"
        sources.append(
            {
                "n": i,
                "title": p["title"],
                "author": p["author"],
                "date": p["datetime"],
                "content": p["content"][:2000],
                "url": url,
            }
        )
    return sources


SYSTEM_PROMPT = """Jesteś asystentem archiwum polskiego forum dentystycznego DENTOnet.
Odpowiadasz po polsku, WYŁĄCZNIE na podstawie dostarczonych postów z forum.

Zasady:
- Po każdym twierdzeniu zaczerpniętym z postu podaj numer źródła w nawiasie kwadratowym, np. [1] albo [2][3].
- Jeśli posty nie zawierają odpowiedzi na pytanie, powiedz to wprost.
- Nie wymieniaj źródeł na końcu — linki dodaje system.
- Pisz zwięźle i konkretnie. Możesz używać **pogrubień**.
- Zaznacz, że odpowiedzi pochodzą z archiwum forum (opinie użytkowników), a nie stanowią porady medycznej."""


def build_chat_contents(history, question, sources):
    posts_block = "\n\n".join(
        f"[{s['n']}] (wątek: „{s['title']}”, autor: {s['author']}, {s['date']})\n{s['content']}"
        for s in sources
    )
    contents = [
        {"role": m["role"], "parts": [{"text": m["content"]}]} for m in history
    ]
    contents.append(
        {
            "role": "user",
            "parts": [
                {"text": f"Pytanie: {question}\n\nPosty z forum:\n{posts_block}"}
            ],
        }
    )
    return contents


def render_answer_html(text, sources):
    """Escape the model output, then turn [n] markers into source links."""
    by_n = {s["n"]: s for s in sources}
    escaped = html_mod.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)

    def replace_marker(match):
        nums = [int(x) for x in re.findall(r"\d+", match.group(0))]
        valid = [n for n in nums if n in by_n]
        if not valid:
            return ""
        return "".join(
            f'<a href="{by_n[n]["url"]}" target="_blank" '
            f'title="{html_mod.escape(by_n[n]["title"])}">[{n}]</a>'
            for n in valid
        )

    escaped = re.sub(r"\[[\d,\s]+\]", replace_marker, escaped)
    return escaped.replace("\n", "<br>")


@app.route("/chat")
def chat():
    return render_template("chat.html", chat_available=chat_available())


@app.route("/api/embeddings/status")
def embeddings_status():
    """Progress of tools/build_embeddings.py (read from its meta table)."""
    total = get_db().execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    if not VEC_DB_PATH.exists():
        return jsonify({"done": 0, "total": total, "percent": 0, "running": False})
    vec = get_vecdb()
    meta = dict(vec.execute("SELECT key, value FROM meta").fetchall())
    done = int(meta.get("last_rowid", 0))
    rate = float(meta.get("rate_per_min", 0) or 0)
    updated_at = int(meta.get("updated_at", 0) or 0)
    import time as _time

    running = (_time.time() - updated_at) < 90 and done < total
    percent = min(100, round(done * 100 / total, 1))
    eta_min = round((total - done) / rate) if rate > 0 else None
    return jsonify(
        {
            "done": done,
            "total": total,
            "percent": percent,
            "rate_per_min": round(rate),
            "eta_min": eta_min,
            "running": running,
        }
    )


@app.route("/api/conversations")
def list_conversations():
    rows = get_chatsdb().execute(
        "SELECT id, title, favorite, created_at FROM conversations "
        "ORDER BY favorite DESC, id DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/conversations/<int:conv_id>")
def get_conversation(conv_id):
    rows = get_chatsdb().execute(
        "SELECT role, content, sources_json, created_at FROM messages "
        "WHERE conversation_id = ? ORDER BY id",
        (conv_id,),
    ).fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "role": r["role"],
                "content": r["content"],
                "sources": json.loads(r["sources_json"] or "[]"),
                "created_at": r["created_at"],
            }
        )
    return jsonify(out)


@app.route("/api/conversations/<int:conv_id>/favorite", methods=["POST"])
def favorite_conversation(conv_id):
    fav = request.get_json(force=True).get("favorite", False)
    chats = get_chatsdb()
    with chats:
        chats.execute(
            "UPDATE conversations SET favorite = ? WHERE id = ?", (1 if fav else 0, conv_id)
        )
    chats.commit()
    return jsonify({"ok": True, "favorite": bool(fav)})


@app.route("/api/conversations/<int:conv_id>/title", methods=["POST"])
def rename_conversation(conv_id):
    title = (request.get_json(force=True).get("title") or "").strip()
    if not title:
        return jsonify({"error": "Pusty tytuł."}), 400
    chats = get_chatsdb()
    with chats:
        chats.execute(
            "UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id)
        )
    chats.commit()
    return jsonify({"ok": True, "title": title})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    if not chat_available():
        return (
            jsonify(
                {
                    "error": "Chat nie jest jeszcze gotowy (brak klucza API lub bazy embeddings)."
                }
            ),
            503,
        )

    data = request.get_json(force=True)
    question = (data.get("message") or "").strip()
    conv_id = data.get("conversation_id")
    if not question:
        return jsonify({"error": "Puste pytanie."}), 400

    chats = get_chatsdb()

    if conv_id:
        history = chats.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? "
            "ORDER BY id DESC LIMIT 8",
            (conv_id,),
        ).fetchall()
        history = list(reversed(history))
    else:
        history = []
        cur = chats.execute(
            "INSERT INTO conversations (title) VALUES (?)", (question[:80],)
        )
        conv_id = cur.lastrowid

    try:
        sources = retrieve_posts(question)
        contents = build_chat_contents(history, question, sources)

        from google.genai import types

        response = gemini_with_retry(
            lambda: get_genai().models.generate_content(
                model=CHAT_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            )
        )
        answer_text = response.text
    except Exception as e:
        return (
            jsonify(
                {
                    "error": "Usługa Gemini jest chwilowo przeciążona "
                    "(trwa indeksowanie archiwum). Spróbuj ponownie za minutę."
                }
            ),
            503,
        )
    answer_html = render_answer_html(answer_text, sources)

    with chats:
        chats.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
            (conv_id, question),
        )
        chats.execute(
            "INSERT INTO messages (conversation_id, role, content, sources_json) "
            "VALUES (?, 'model', ?, ?)",
            (conv_id, answer_html, json.dumps(sources, ensure_ascii=False)),
        )
    chats.commit()

    return jsonify(
        {"conversation_id": conv_id, "answer_html": answer_html, "sources": sources}
    )


URL = "http://127.0.0.1:5000"
PORT = 5000


def instance_already_running():
    """Only one instance may run: if the port is taken, one is already up."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


if __name__ == "__main__":
    if instance_already_running():
        print("\n  Forum Dentonet juz dziala!")
        print(f"  Otwieram przegladarke: {URL}\n")
        webbrowser.open(URL)
        raise SystemExit(0)

    if not DB_PATH.exists():
        print(f"\nERROR: database not found at {DB_PATH}")
        print("The folder 'data' with 'dentonet.db' must be next to app.py.\n")
        raise SystemExit(1)

    print("\n" + "=" * 56)
    print("  FORUM DENTONET jest uruchomione!")
    print(f"  Adres strony:  {URL}")
    print("  (Strona otworzy sie automatycznie w przegladarce.)")
    print("  Aby zamknac forum, zamknij to okno.")
    print("=" * 56 + "\n")

    threading.Timer(1.0, lambda: webbrowser.open(URL)).start()
    app.run(host="127.0.0.1", port=PORT)
