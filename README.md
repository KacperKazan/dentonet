# DENTOnet forum archive

Offline, read-only archive of the Polish dental forum **DENTOnet**
(dentonet.pl), scraped before the site shut down. Flask + SQLite.

## For the end user (non-technical)

See **INSTRUKCJA.txt** (Polish). In short: copy the whole folder from the
external drive, then double-click:

- Windows: `Start Dentonet (Windows).bat`
- macOS: `Start Dentonet (Mac).command`

The script installs [uv](https://docs.astral.sh/uv/) if needed, sets up
Python + dependencies automatically, starts the site and opens it in the
browser at http://127.0.0.1:5000

## Repository layout

| Path | Description |
|---|---|
| `app.py` | Flask app (SQLite backend) |
| `templates/`, `static/css`, `static/js` | Frontend |
| `data/dentonet.db` | SQLite database (not in git — lives on the backup drive) |
| `static/download/` | 17 946 forum attachments/images (not in git) |
| `tools/build_db.py` | Rebuilds `data/dentonet.db` from the MongoDB JSON export |
| `downloader.py`, `classes.py` | Original scraper (kept for reference) |
| `Start Dentonet (*)` | One-click launchers for Windows/macOS |

## Rebuilding the database

The site originally ran on MongoDB. It was migrated to SQLite (single
file, no server) to make the one-click setup possible. To rebuild
`data/dentonet.db` from the mongoexport JSON dump:

```bash
uv run python tools/build_db.py <path/to/database_export>
```

## Development

```bash
uv sync
uv run python app.py
```
