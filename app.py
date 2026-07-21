import math
import re
import sqlite3
import threading
import webbrowser
from collections import defaultdict
from pathlib import Path

from flask import Flask, g, render_template, request, url_for
from flask_paginate import Pagination, get_page_parameter

THREADS_PER_FORUM_PAGE = 50
POSTS_PER_THREAD_PAGE = 10

DB_PATH = Path(__file__).resolve().parent / "data" / "dentonet.db"

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


URL = "http://127.0.0.1:5000"

if __name__ == "__main__":
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
    app.run(host="127.0.0.1", port=5000)
