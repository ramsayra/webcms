from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "cms.db"



def resolve_db_path() -> Path:
    raw = os.getenv("CMS_DB_PATH", str(DEFAULT_DB_PATH))
    return Path(raw).expanduser().resolve()


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["DB_PATH"] = resolve_db_path()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_: Any) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db_path = Path(app.config["DB_PATH"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            is_published INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.commit()
    db.close()


def normalize_slug(raw: str) -> str:
    cleaned = "-".join(raw.lower().strip().split())
    return "".join(ch for ch in cleaned if ch.isalnum() or ch == "-")


@app.route("/")
def public_index() -> str:
    db = get_db()
    pages = db.execute(
        "SELECT title, slug, updated_at FROM pages WHERE is_published = 1 ORDER BY updated_at DESC"
    ).fetchall()
    return render_template("public_index.html", pages=pages)


@app.route("/p/<slug>")
def view_page(slug: str) -> str:
    db = get_db()
    page = db.execute(
        "SELECT title, content, updated_at FROM pages WHERE slug = ? AND is_published = 1",
        (slug,),
    ).fetchone()
    if page is None:
        abort(404)
    return render_template("public_page.html", page=page)


@app.route("/admin")
def admin_index() -> str:
    db = get_db()
    pages = db.execute(
        "SELECT id, title, slug, is_published, updated_at FROM pages ORDER BY updated_at DESC"
    ).fetchall()
    return render_template("admin_index.html", pages=pages)


@app.route("/admin/new", methods=["GET", "POST"])
def create_page() -> str:
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        slug = normalize_slug(request.form.get("slug", "") or title)
        is_published = 1 if request.form.get("is_published") else 0

        if not title or not content or not slug:
            flash("Title, content, and slug are required.")
            return render_template("page_form.html", page=request.form, is_edit=False)

        db = get_db()
        try:
            db.execute(
                "INSERT INTO pages (title, slug, content, is_published) VALUES (?, ?, ?, ?)",
                (title, slug, content, is_published),
            )
            db.commit()
            flash("Page created successfully.")
            return redirect(url_for("admin_index"))
        except sqlite3.IntegrityError:
            flash("Slug already exists. Please choose another slug.")

    return render_template("page_form.html", page={}, is_edit=False)


@app.route("/admin/edit/<int:page_id>", methods=["GET", "POST"])
def edit_page(page_id: int) -> str:
    db = get_db()
    page = db.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
    if page is None:
        abort(404)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        slug = normalize_slug(request.form.get("slug", "") or title)
        is_published = 1 if request.form.get("is_published") else 0

        if not title or not content or not slug:
            flash("Title, content, and slug are required.")
            return render_template("page_form.html", page=request.form, is_edit=True)

        try:
            db.execute(
                """
                UPDATE pages
                SET title = ?, slug = ?, content = ?, is_published = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title, slug, content, is_published, page_id),
            )
            db.commit()
            flash("Page updated.")
            return redirect(url_for("admin_index"))
        except sqlite3.IntegrityError:
            flash("Slug already exists. Please choose another slug.")

    return render_template("page_form.html", page=page, is_edit=True)


@app.route("/admin/delete/<int:page_id>", methods=["POST"])
def delete_page(page_id: int) -> str:
    db = get_db()
    db.execute("DELETE FROM pages WHERE id = ?", (page_id,))
    db.commit()
    flash("Page deleted.")
    return redirect(url_for("admin_index"))


@app.route("/admin/export")
def export_pages() -> str:
    db = get_db()
    rows = db.execute(
        "SELECT title, slug, content, is_published, created_at, updated_at FROM pages"
    ).fetchall()
    payload = [dict(row) for row in rows]
    return app.response_class(
        response=json.dumps(payload, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=pages.json"},
    )


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
