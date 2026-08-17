# Contact endpoint — Raspberry Pi

Flask app that receives the contact form, appends it to a JSONL file, and emails
it to you. It listens only on `127.0.0.1:8080`; a Cloudflare Tunnel gives it a
public HTTPS hostname without forwarding a single port on your router.

```
browser ──POST /api/contact──▶ api.kai-spicer.com   (Cloudflare edge, TLS)
                                      │
                                  tunnel (outbound from the Pi)
                                      ▼
                            127.0.0.1:8080  gunicorn → app.py
                                      ├─ honeypot + rate limit + validation
                                      ├─ append messages.jsonl
                                      └─ SMTP ──▶ your inbox
```

## The domain

`kai-spicer.com`, registered through Cloudflare — so the nameservers already
point at Cloudflare and nothing needs changing at a registrar. That's the one
prerequisite for a named tunnel, and it's done.

The API lives at the `api.` subdomain; the site itself gets the apex. Step 4
below creates the `api` DNS record for you — don't add it by hand in the
dashboard, `cloudflared tunnel route dns` writes the right `CNAME` to the
tunnel automatically.

The hostname appears in three files, all already set to `kai-spicer.com`:
`cloudflared-config.yml`, `ALLOWED_ORIGINS` in the env file, and `ENDPOINT` at
the top of `../contact.js`.

Before you start, check the zone is actually active — a freshly registered
domain takes a few minutes:

```bash
dig +short NS kai-spicer.com     # should return two *.ns.cloudflare.com
```

## Order matters

Do these in sequence. Steps 3 and 4 copy files out of the folder you send in
step 1, and step 2's env file is meaningless until the service in step 3 exists
to read it.

## 1. Get the folder onto the Pi

Send the whole `server/` directory — later steps need the `.service` unit and
the tunnel config, not just the app:

```bash
# from your laptop, in the repo root:
scp -r server spicerke@pi5.local:~/kai-contact-setup
# or, skipping mDNS:  scp -r server spicerke@192.168.1.101:~/kai-contact-setup
```

Then, on the Pi, install the app itself into `/opt`:

```bash
sudo mkdir -p /opt/kai-contact /var/lib/kai-contact
sudo chown spicerke:spicerke /opt/kai-contact /var/lib/kai-contact

cp ~/kai-contact-setup/app.py ~/kai-contact-setup/requirements.txt /opt/kai-contact/

cd /opt/kai-contact
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`~/kai-contact-setup` is just a staging copy; `/opt/kai-contact` is what
actually runs. Once this repo is pushed to GitHub you can replace the `scp`
with `git clone https://github.com/Spicerke/Personal_Website.git` on the Pi and
`git pull` to update — but the `scp` works today, before anything is committed.

## 2. Configure

```bash
sudo cp ~/kai-contact-setup/.env.example /etc/kai-contact.env
sudo nano /etc/kai-contact.env      # fill in SMTP_USER, SMTP_PASS, MAIL_TO, ALLOWED_ORIGINS
sudo chmod 600 /etc/kai-contact.env
```

### Gmail App Password

Three settings do two different jobs, which is the thing that trips people up:

| Variable | Role |
| --- | --- |
| `SMTP_USER` / `SMTP_PASS` | the account that **sends** the mail |
| `MAIL_TO` | the inbox that **receives** it |

They're usually the same Gmail account — it sends to itself. That's normal and
works fine.

1. **Turn on 2-Step Verification** at
   [myaccount.google.com/signinoptions/two-step-verification](https://myaccount.google.com/signinoptions/two-step-verification).
   App Passwords do not exist as an option until this is on — if the page in
   step 2 gives you "the setting you are looking for is not available for your
   account," this is why.
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords),
   name it something like `pi-contact-form`, and create it.
3. Google shows a 16-character password as four groups of four. **Copy it
   without the spaces** into `SMTP_PASS`. It's shown once; you can't get it
   back, only delete it and make a new one.
4. Set `SMTP_USER` to that same Gmail address, and `MAIL_TO` to wherever you
   want the messages delivered.

Your normal account password will always be rejected — Google removed
"less secure app access" entirely, so an App Password is the only way for a
script to send through Gmail.

**Delivering somewhere other than Gmail.** `MAIL_TO` doesn't have to match
`SMTP_USER`. To get these at your Columbia address, leave `SMTP_USER` as the
Gmail account and set `MAIL_TO=kes2246@columbia.edu` — Gmail sends, Columbia
receives. Sending *from* a `@columbia.edu` address instead would mean using
Columbia's SMTP server and their credentials, and university accounts often
block app passwords by policy, so Gmail-as-sender is the path of least
resistance.

**Replying.** The mail arrives `From: kai-spicer.com <your-gmail>` with
`Reply-To:` set to the visitor. Hitting reply in Gmail goes to the visitor, not
to yourself. The From stays your own address on purpose — forging the visitor's
domain there would get the mail spam-filtered or rejected outright.

If messages land in spam, make a Gmail filter on subject `Portfolio contact —`
and mark it "never send to spam."

`ALLOWED_ORIGINS` is the CORS allowlist — the origin your *site* is served from,
not the API hostname. Comma-separated, no trailing slashes.

`https://kai-spicer.com` and `https://www.kai-spicer.com` are preset. Note that
`api.kai-spicer.com` is a *different origin* from `kai-spicer.com` as far as the
browser is concerned — sharing a registered domain doesn't exempt the request
from CORS, so this list matters even once everything is on your own domain. If
you deploy to GitHub Pages before the DNS is pointed, add
`https://spicerke.github.io` too.

## 3. Run it as a service

```bash
sudo cp ~/kai-contact-setup/kai-contact.service /etc/systemd/system/
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
sudo cp ~/kai-contact-setup/cloudflared-config.yml /etc/cloudflared/config.yml
sudo nano /etc/cloudflared/config.yml       # paste the UUID in both places

cloudflared tunnel route dns kai-contact api.kai-spicer.com   # creates the DNS record

sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

Then from anywhere:

```bash
curl https://api.kai-spicer.com/api/health
```

## 5. Verify end to end

```bash
curl -X POST https://api.kai-spicer.com/api/contact \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://kai-spicer.com' \
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
