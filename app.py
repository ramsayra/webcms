from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "cms.db"
UPLOADS_DIR = BASE_DIR / "uploads"

ALLOWED_UPLOAD_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "svg",
    "pdf",
    "mp4",
    "webm",
    "mov",
    "avi",
    "css",
    "js",
    "txt",
    "zip",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
}
import sqlite3
from pathlib import Path
from typing import Any

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "cms.db"



def resolve_db_path() -> Path:
    raw = os.getenv("CMS_DB_PATH", str(DEFAULT_DB_PATH))
    return Path(raw).expanduser().resolve()


def get_admin_username() -> str:
    return os.getenv("ADMIN_USERNAME", "admin")


def get_admin_password_hash() -> str:
    return os.getenv(
        "ADMIN_PASSWORD_HASH",
        "pbkdf2:sha256:600000$jzUxuM4scl0Y57P8$8b89dd22a05e2b6272e02b38a1db4e470f9fca8d32ad5f7bf6e35130fd0920f0",
    )


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config["DB_PATH"] = resolve_db_path()
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024
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
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(db_path)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            custom_css TEXT NOT NULL DEFAULT '',
            custom_js TEXT NOT NULL DEFAULT '',
            template_key TEXT NOT NULL DEFAULT 'default',
            is_published INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS themes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            custom_css TEXT NOT NULL DEFAULT '',
            header_html TEXT NOT NULL DEFAULT '',
            footer_html TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            url TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    existing_columns = {row[1] for row in db.execute("PRAGMA table_info(pages)").fetchall()}
    if "custom_css" not in existing_columns:
        db.execute("ALTER TABLE pages ADD COLUMN custom_css TEXT NOT NULL DEFAULT ''")
    if "custom_js" not in existing_columns:
        db.execute("ALTER TABLE pages ADD COLUMN custom_js TEXT NOT NULL DEFAULT ''")
    if "template_key" not in existing_columns:
        db.execute("ALTER TABLE pages ADD COLUMN template_key TEXT NOT NULL DEFAULT 'default'")

    has_theme = db.execute("SELECT id FROM themes LIMIT 1").fetchone()
    if has_theme is None:
        db.execute(
            "INSERT INTO themes (name, custom_css, header_html, footer_html, is_active) VALUES (?, '', '', '', 1)",
            ("Default Theme",),
        )

    db.commit()
    db.close()


def normalize_slug(raw: str) -> str:
    cleaned = "-".join(raw.lower().strip().split())
    return "".join(ch for ch in cleaned if ch.isalnum() or ch == "-")


def is_logged_in() -> bool:
    return bool(session.get("is_admin"))


def require_login():
    if not is_logged_in():
        next_url = request.path
        return redirect(url_for("admin_login", next=next_url))
    return None


def validate_admin_password(password: str) -> bool:
    return check_password_hash(get_admin_password_hash(), password)


def allowed_upload(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_UPLOAD_EXTENSIONS


def unique_upload_name(filename: str) -> str:
    safe = secure_filename(filename)
    if not safe:
        safe = f"file-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    path = UPLOADS_DIR / safe
    if not path.exists():
        return safe

    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = f"{stem}-{counter}{suffix}"
        if not (UPLOADS_DIR / candidate).exists():
            return candidate
        counter += 1


def make_embed_hint(filename: str) -> str:
    encoded = quote(filename)
    lower = filename.lower()
    url = f"/uploads/{encoded}"
    if re.search(r"\.(png|jpe?g|gif|webp|svg)$", lower):
        return f'<img src="{url}" alt="{filename}">'
    if re.search(r"\.(mp4|webm|mov|avi)$", lower):
        return f'<video controls src="{url}"></video>'
    if lower.endswith(".pdf"):
        return f'<a href="{url}" target="_blank">{filename}</a>'
    if lower.endswith(".css"):
        return f'<link rel="stylesheet" href="{url}">'
    if lower.endswith(".js"):
        return f'<script src="{url}"></script>'
    return f'<a href="{url}">{filename}</a>'


def get_active_theme() -> sqlite3.Row | None:
    db = get_db()
    return db.execute(
        "SELECT id, name, custom_css, header_html, footer_html FROM themes WHERE is_active = 1 ORDER BY id ASC LIMIT 1"
    ).fetchone()


def get_menu_items() -> list[sqlite3.Row]:
    db = get_db()
    return db.execute("SELECT id, label, url, sort_order FROM menu_items ORDER BY sort_order ASC, id ASC").fetchall()


@app.context_processor
def inject_site_context() -> dict[str, Any]:
    return {
        "is_admin_logged_in": is_logged_in(),
        "menu_items": get_menu_items(),
        "active_theme": get_active_theme(),
    }


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
        "SELECT title, content, custom_css, custom_js, template_key, updated_at FROM pages WHERE slug = ? AND is_published = 1",
        (slug,),
    ).fetchone()
    if page is None:
        return render_template("not_found.html"), 404
        "SELECT title, content, updated_at FROM pages WHERE slug = ? AND is_published = 1",
        (slug,),
    ).fetchone()
    if page is None:
        abort(404)
    return render_template("public_page.html", page=page)


@app.route("/admin")
def admin_entry() -> str:
    if not is_logged_in():
        return redirect(url_for("admin_login", next="/admin"))

def admin_index() -> str:
    db = get_db()
    pages = db.execute(
        "SELECT id, title, slug, is_published, updated_at FROM pages ORDER BY updated_at DESC"
    ).fetchall()
    return render_template("admin_index.html", pages=pages)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login() -> str:
    next_url = request.args.get("next") or request.form.get("next") or url_for("admin_entry")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == get_admin_username() and validate_admin_password(password):
            session["is_admin"] = True
            flash("Welcome back. You are logged in.")
            return redirect(next_url)

        flash("Invalid username or password.")

    return render_template("admin_login.html", next_url=next_url)


@app.route("/admin/logout", methods=["POST"])
def admin_logout() -> str:
    session.clear()
    flash("You were logged out.")
    return redirect(url_for("public_index"))


@app.route("/admin/new", methods=["GET", "POST"])
def create_page() -> str:
    guard = require_login()
    if guard:
        return guard

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        custom_css = request.form.get("custom_css", "").strip()
        custom_js = request.form.get("custom_js", "").strip()
        template_key = request.form.get("template_key", "default")
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
                "INSERT INTO pages (title, slug, content, custom_css, custom_js, template_key, is_published) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (title, slug, content, custom_css, custom_js, template_key, is_published),
            )
            db.commit()
            flash("Page created successfully.")
            return redirect(url_for("admin_entry"))
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
    guard = require_login()
    if guard:
        return guard

    db = get_db()
    page = db.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
    if page is None:
        return render_template("not_found.html"), 404
    db = get_db()
    page = db.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
    if page is None:
        abort(404)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        custom_css = request.form.get("custom_css", "").strip()
        custom_js = request.form.get("custom_js", "").strip()
        template_key = request.form.get("template_key", "default")
        slug = normalize_slug(request.form.get("slug", "") or title)
        is_published = 1 if request.form.get("is_published") else 0

        if not title or not content or not slug:
            flash("Title, content, and slug are required.")
            return render_template("page_form.html", page=request.form, is_edit=True)

        try:
            db.execute(
                """
                UPDATE pages
                SET title = ?, slug = ?, content = ?, custom_css = ?, custom_js = ?, template_key = ?, is_published = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title, slug, content, custom_css, custom_js, template_key, is_published, page_id),
            )
            db.commit()
            flash("Page updated.")
            return redirect(url_for("admin_entry"))
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
    guard = require_login()
    if guard:
        return guard

    db = get_db()
    db.execute("DELETE FROM pages WHERE id = ?", (page_id,))
    db.commit()
    flash("Page deleted.")
    return redirect(url_for("admin_entry"))


@app.route("/admin/media", methods=["GET", "POST"])
def admin_media() -> str:
    guard = require_login()
    if guard:
        return guard

    if request.method == "POST":
        uploaded = request.files.get("file")
        if uploaded is None or uploaded.filename == "":
            flash("Select a file to upload.")
            return redirect(url_for("admin_media"))

        if not allowed_upload(uploaded.filename):
            allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
            flash(f"File type not allowed. Allowed: {allowed}")
            return redirect(url_for("admin_media"))

        filename = unique_upload_name(uploaded.filename)
        uploaded.save(UPLOADS_DIR / filename)
        flash(f"Uploaded {filename}")
        return redirect(url_for("admin_media"))

    files = []
    for p in sorted(UPLOADS_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file():
            files.append(
                {
                    "name": p.name,
                    "size_kb": round(p.stat().st_size / 1024, 1),
                    "url": url_for("uploaded_file", filename=p.name),
                    "embed_hint": make_embed_hint(p.name),
                }
            )

    return render_template("admin_media.html", files=files)


@app.route("/admin/themes", methods=["GET", "POST"])
def admin_themes() -> str:
    guard = require_login()
    if guard:
        return guard

    db = get_db()

    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "create":
            name = request.form.get("name", "").strip()
            css = request.form.get("custom_css", "")
            header_html = request.form.get("header_html", "")
            footer_html = request.form.get("footer_html", "")
            if not name:
                flash("Theme name is required.")
            else:
                try:
                    db.execute(
                        "INSERT INTO themes (name, custom_css, header_html, footer_html, is_active) VALUES (?, ?, ?, ?, 0)",
                        (name, css, header_html, footer_html),
                    )
                    db.commit()
                    flash("Theme created.")
                except sqlite3.IntegrityError:
                    flash("Theme name already exists.")
        elif action == "activate":
            theme_id = request.form.get("theme_id", type=int)
            if theme_id:
                db.execute("UPDATE themes SET is_active = 0")
                db.execute("UPDATE themes SET is_active = 1 WHERE id = ?", (theme_id,))
                db.commit()
                flash("Theme activated.")

        return redirect(url_for("admin_themes"))

    themes = db.execute(
        "SELECT id, name, custom_css, header_html, footer_html, is_active FROM themes ORDER BY id DESC"
    ).fetchall()
    return render_template("admin_themes.html", themes=themes)


@app.route("/admin/menus", methods=["GET", "POST"])
def admin_menus() -> str:
    guard = require_login()
    if guard:
        return guard

    db = get_db()

    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "create":
            label = request.form.get("label", "").strip()
            url = request.form.get("url", "").strip()
            sort_order = request.form.get("sort_order", type=int) or 0
            if not label or not url:
                flash("Menu label and URL are required.")
            else:
                db.execute(
                    "INSERT INTO menu_items (label, url, sort_order) VALUES (?, ?, ?)",
                    (label, url, sort_order),
                )
                db.commit()
                flash("Menu item added.")
        elif action == "delete":
            item_id = request.form.get("item_id", type=int)
            if item_id:
                db.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
                db.commit()
                flash("Menu item removed.")
        return redirect(url_for("admin_menus"))

    items = get_menu_items()
    return render_template("admin_menus.html", items=items)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(UPLOADS_DIR, filename)
    return redirect(url_for("admin_index"))


@app.route("/admin/export")
def export_pages() -> str:
    guard = require_login()
    if guard:
        return guard

    db = get_db()
    rows = db.execute(
        "SELECT title, slug, content, template_key, custom_css, custom_js, is_published, created_at, updated_at FROM pages"
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
