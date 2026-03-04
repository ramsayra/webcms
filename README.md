# MiniCMS

A simple CMS that behaves like a normal public website by default, with private management under `/admin`.

## What changed
- Public site shows no admin link.
- Admin tools are only reachable by typing `/admin`.
- `/admin` redirects to login when not authenticated, then loads full CMS dashboard after login.
- Added theme management (CSS + header/footer HTML areas).
- Added menu management (navigation links editable from admin).
- Added page template option (`default` or `landing`) plus page CSS/JS.
- Added media uploads for images, videos, PDF, documents, CSS and JS files.

## Local run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open:
- Public site: `http://localhost:5000`
- Admin entry: `http://localhost:5000/admin`

## Admin credentials
- Username: `admin`
- Password: `admin123`

Use env vars in production:
- `SECRET_KEY`
- `CMS_DB_PATH`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD_HASH`

Generate a password hash:
```bash
python3 - <<'PY'
from werkzeug.security import generate_password_hash
print(generate_password_hash("your-strong-password"))
PY
```

## Admin sections
- `/admin` → dashboard/pages
- `/admin/media` → uploads + embed snippets
- `/admin/themes` → create/activate themes and theme content areas
- `/admin/menus` → create menu links for public header

## VPS note (Hostinger)
You can keep the same Gunicorn + Nginx deployment from previous instructions; just redeploy updated files and restart service.
