# Contact endpoint — Raspberry Pi

Flask app that receives the contact form, appends it to a JSONL file, and emails
it to you. It listens only on `127.0.0.1:8080`; a Cloudflare Tunnel gives it a
public HTTPS hostname without forwarding a single port on your router.

```
browser ──POST /api/contact──▶ api.kaispicer.com   (Cloudflare edge, TLS)
                                      │
                                  tunnel (outbound from the Pi)
                                      ▼
                            127.0.0.1:8080  gunicorn → app.py
                                      ├─ honeypot + rate limit + validation
                                      ├─ append messages.jsonl
                                      └─ SMTP ──▶ your inbox
```

## Prerequisite: a domain on Cloudflare

**This is the one thing you can't skip.** A named tunnel hostname requires a
domain whose nameservers point at Cloudflare (the DNS itself is free; you still
buy the domain, ~$10/yr). Sign up at dash.cloudflare.com, add the domain, and
change the nameservers at your registrar.

There is a no-domain mode — `cloudflared tunnel --url http://localhost:8080` —
but it hands you a random `*.trycloudflare.com` URL that changes every restart,
so it's for testing only, not for the live form.

Everything below assumes `api.kaispicer.com`. Swap in whatever you register, in
three places: `cloudflared-config.yml`, `ALLOWED_ORIGINS` in the env file, and
`ENDPOINT` at the top of `../contact.js`.

## 1. Install the app

```bash
sudo mkdir -p /opt/kai-contact /var/lib/kai-contact
sudo chown kai:kai /opt/kai-contact /var/lib/kai-contact

# from your laptop, in the repo root:
scp server/app.py server/requirements.txt kai@raspberrypi.local:/opt/kai-contact/

# on the Pi:
cd /opt/kai-contact
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 2. Configure

```bash
sudo cp /path/to/.env.example /etc/kai-contact.env
sudo nano /etc/kai-contact.env      # fill in SMTP_USER, SMTP_PASS, MAIL_TO, ALLOWED_ORIGINS
sudo chmod 600 /etc/kai-contact.env
```

For Gmail, `SMTP_PASS` must be an **App Password** from
[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
(needs 2FA enabled). Your normal account password will be rejected.

`ALLOWED_ORIGINS` is the CORS allowlist — the origin your *site* is served from,
not the API hostname. Comma-separated, no trailing slashes. If you deploy to
GitHub Pages first, that's `https://spicerke.github.io`.

## 3. Run it as a service

```bash
sudo cp server/kai-contact.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kai-contact
sudo systemctl status kai-contact
curl -s localhost:8080/api/health      # → {"ok":true}
```

## 4. The tunnel

```bash
# install cloudflared (arm64 Pi OS)
curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

cloudflared tunnel login                    # opens a browser, pick your domain
cloudflared tunnel create kai-contact       # prints a UUID and writes a .json credentials file

sudo mkdir -p /etc/cloudflared
sudo mv ~/.cloudflared/<UUID>.json /etc/cloudflared/
sudo cp server/cloudflared-config.yml /etc/cloudflared/config.yml
sudo nano /etc/cloudflared/config.yml       # paste the UUID in both places

cloudflared tunnel route dns kai-contact api.kaispicer.com   # creates the DNS record

sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

Then from anywhere:

```bash
curl https://api.kaispicer.com/api/health
```

## 5. Verify end to end

```bash
curl -X POST https://api.kaispicer.com/api/contact \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://kaispicer.com' \
  -d '{"name":"Test","email":"test@example.com","message":"hello","website":""}'
```

Expect `{"ok":true}`, a new line in `/var/lib/kai-contact/messages.jsonl`, and
an email. Check `sudo journalctl -u kai-contact -f` if the email doesn't land —
the message is written to disk before SMTP is attempted, so a bad password
loses the mail but never the message.

## Spam handling

Three layers, no CAPTCHA:

- **Honeypot.** A `website` field, hidden with CSS and `tabindex="-1"`. Bots
  that fill every input trip it. The server answers `200 {"ok":true}` so the bot
  logs a success and moves on instead of retrying with the field blank.
- **Rate limit.** 5 submissions per IP per hour, sliding window, in memory.
  Tune with `RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW`. State lives in the process,
  which is why the service runs `--workers 1 --threads 4`; if you ever scale to
  multiple workers this needs Redis.
- **Validation.** Length caps, an email regex, a `MAX_CONTENT_LENGTH` of 64 KB,
  and a CR/LF check on the name and email so nobody can inject mail headers.

If it ever gets bad, Cloudflare's dashboard can add a WAF rate-limit rule or a
Turnstile challenge in front of the hostname without touching this code.

## Reading your messages

```bash
# most recent first, readable
tac /var/lib/kai-contact/messages.jsonl | python3 -c '
import json,sys
for line in sys.stdin:
    m = json.loads(line)
    print(f"{m[\"at\"]}  {m[\"name\"]} <{m[\"email\"]}>\n{m[\"message\"]}\n{\"-\"*50}")'
```
