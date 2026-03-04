# MiniCMS (simple WordPress-like starter)

A tiny CMS you can run locally and edit pages from a browser.

## Features
- Create, edit, delete pages.
- Draft or publish pages.
- Public pages available at `/p/<slug>`.
- Admin dashboard at `/admin`.
- JSON export of all pages.

## Local run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open: `http://localhost:5000`

## Deploy on Hostinger Ubuntu VPS (domain: `arodslandscaping.com`)

> Assumes you already SSH'd into the VPS as a sudo user.

### 1) Install system packages
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx
```

### 2) Upload app and install Python deps
```bash
mkdir -p ~/apps/webcms
cd ~/apps/webcms
# put your project files here (git clone or upload)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3) Set production environment variables
```bash
cat > .env <<'EOF'
SECRET_KEY=replace-with-a-long-random-secret
CMS_DB_PATH=/home/$USER/apps/webcms/data/cms.db
EOF
mkdir -p data
```

### 4) Create systemd service for Gunicorn
```bash
sudo tee /etc/systemd/system/webcms.service >/dev/null <<'EOF'
[Unit]
Description=MiniCMS Gunicorn Service
After=network.target

[Service]
User=%i
Group=www-data
WorkingDirectory=/home/%i/apps/webcms
EnvironmentFile=/home/%i/apps/webcms/.env
ExecStart=/home/%i/apps/webcms/.venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable webcms@$USER
sudo systemctl start webcms@$USER
sudo systemctl status webcms@$USER --no-pager
```

### 5) Configure Nginx reverse proxy
```bash
sudo tee /etc/nginx/sites-available/webcms >/dev/null <<'EOF'
server {
    listen 80;
    server_name cms.arodslandscaping.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/webcms /etc/nginx/sites-enabled/webcms
sudo nginx -t
sudo systemctl reload nginx
```

### 6) Point DNS from Hostinger panel
- Create an **A record**:
  - Host: `cms`
  - Value: `<your-vps-public-ip>`

Wait for DNS propagation, then open: `http://cms.arodslandscaping.com`

### 7) Enable HTTPS (recommended)
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d cms.arodslandscaping.com
```

## Online test checklist
1. Open `/admin`.
2. Create a page and mark it published.
3. Confirm it appears on `/` and `/p/<slug>`.
4. Edit and delete it from `/admin`.
5. Test `/admin/export` returns JSON.

## Notes
- Data is stored in SQLite (`cms.db` by default, `CMS_DB_PATH` in production).
- There is no authentication yet, so add login protection before public use.
