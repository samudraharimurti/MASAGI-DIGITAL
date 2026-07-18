# Deploy: account.masagi.io + hv.masagi.io + cro.masagi.io

One server (31.97.67.170), three subdomains, three services:

| Subdomain | Service | Port (localhost) |
|---|---|---|
| account.masagi.io | MASAGI Account portal (`portal/`) | 8015 |
| hv.masagi.io | MASAGI HV (`app/`) | 8010 (already running) |
| cro.masagi.io | MASAGI CROM (`cro/`) | 8016 |

SSO: the portal signs 60-second tokens with the shared secret in
`data/portal/sso_secret`; HV and CROM verify at their `/sso` endpoints.
Nothing else is shared — each app keeps its own sessions and users.

## Step 0 — DNS (hPanel, before anything else)

Add three **A records** for masagi.io, all pointing to `31.97.67.170`:
`account`, `hv`, `cro`. Wait until they resolve (a few minutes usually).

## Step 1 — code + services (browser console, as root)

```bash
cd /var/www/masagi-digital && git pull origin main
chown -R masagi:nginx /var/www/masagi-digital/cro /var/www/masagi-digital/portal /var/www/masagi-digital/data 2>/dev/null

cat > /etc/systemd/system/masagi-portal.service <<'EOF'
[Unit]
Description=MASAGI Account portal (gunicorn)
After=network.target
[Service]
Type=simple
User=masagi
Group=nginx
WorkingDirectory=/var/www/masagi-digital/portal
Environment=HV_URL=https://hv.masagi.io
Environment=CROM_URL=https://cro.masagi.io
ExecStart=/var/www/masagi-digital/app/venv/bin/gunicorn --workers 2 --timeout 60 --bind 127.0.0.1:8015 server:app
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
ProtectHome=true
[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/masagi-crom.service <<'EOF'
[Unit]
Description=MASAGI CROM (gunicorn)
After=network.target
[Service]
Type=simple
User=masagi
Group=nginx
WorkingDirectory=/var/www/masagi-digital/cro
ExecStart=/var/www/masagi-digital/app/venv/bin/gunicorn --workers 2 --timeout 60 --bind 127.0.0.1:8016 server:app
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
ProtectHome=true
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now masagi-portal.service masagi-crom.service
systemctl restart masagi-web.service   # reload HV: /sso endpoint + new theme

cat > /etc/nginx/conf.d/masagi-apps.conf <<'EOF'
# MASAGI Account portal
server {
    listen 80;
    listen [::]:80;
    server_name account.masagi.io;
    location / {
        proxy_pass http://127.0.0.1:8015;
        include /etc/nginx/proxy_params.conf;
    }
}
# MASAGI HV console
server {
    listen 80;
    listen [::]:80;
    server_name hv.masagi.io;
    location = / { return 302 https://account.masagi.io; }
    location / {
        proxy_pass http://127.0.0.1:8010;
        include /etc/nginx/proxy_params.conf;
    }
}
# MASAGI CROM
server {
    listen 80;
    listen [::]:80;
    server_name cro.masagi.io;
    location / {
        proxy_pass http://127.0.0.1:8016;
        include /etc/nginx/proxy_params.conf;
        client_max_body_size 25m;
    }
}
EOF
nginx -t && systemctl reload nginx && echo STEP1_OK
```

## Step 2 — TLS (after DNS resolves)

```bash
certbot --nginx -d account.masagi.io -d hv.masagi.io -d cro.masagi.io \
  --non-interactive --agree-tos -m samudra@mores.id --redirect && echo STEP2_OK
```

## Step 3 — credentials (IMPORTANT — the systems are now public)

```bash
# portal first-login password (sign in with this, then delete the file)
cat /var/www/masagi-digital/data/portal/FIRST-LOGIN.txt

# rotate HV demo passwords (seeded admin123 etc.)
cd /var/www/masagi-digital/app && venv/bin/python - <<'EOF'
import secrets
import database
from werkzeug.security import generate_password_hash
for name in database.list_databases():
    conn = database.get_db(name)
    for row in conn.execute("SELECT username FROM users").fetchall():
        pw = secrets.token_urlsafe(10)
        conn.execute("UPDATE users SET password_hash=? WHERE username=?",
                     (generate_password_hash(pw), row["username"]))
        print(f"{name} / {row['username']}: {pw}")
    conn.commit(); conn.close()
EOF

# rotate CROM demo passwords (seeded admin123 / inputter123 / client123)
cd /var/www/masagi-digital/cro && ../app/venv/bin/python - <<'EOF'
import secrets, sqlite3
from werkzeug.security import generate_password_hash
c = sqlite3.connect("data/crom.db"); c.row_factory = sqlite3.Row
for row in c.execute("SELECT email FROM users").fetchall():
    pw = secrets.token_urlsafe(10)
    c.execute("UPDATE users SET password_hash=? WHERE email=?",
              (generate_password_hash(pw), row["email"]))
    print(f"{row['email']}: {pw}")
c.commit()
EOF
```

Save the printed passwords somewhere safe. SSO from the portal keeps working
regardless — it maps accounts by username/email, not by password.

## Step 4 — verify

```bash
for h in account.masagi.io hv.masagi.io cro.masagi.io; do
  curl -sk -o /dev/null -w "$h -> %{http_code}\n" https://127.0.0.1/ -H "Host: $h"
done
curl -sk https://127.0.0.1/ -H "Host: account.masagi.io" | grep -o "<title>[^<]*</title>"
systemctl is-active masagi-web masagi-portal masagi-crom nginx
```

## Managing portal accounts

```bash
cd /var/www/masagi-digital/portal
sudo -u masagi ../app/venv/bin/python server.py add-user client@example.co.id "Client Name" 'TheirPassword' hv:username@MASAGI-GROUP crom:their-crom-email@example.co.id
sudo -u masagi ../app/venv/bin/python server.py list-users
systemctl restart masagi-portal   # not required for new users, only config changes
```

Grants are optional per system — a user with only `crom:` sees only CROM in
the chooser.
