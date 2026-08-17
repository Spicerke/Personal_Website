"""Contact-form endpoint for kai-spicer.com.

Runs on the Raspberry Pi behind a Cloudflare Tunnel, which terminates TLS and
forwards to this app on 127.0.0.1:8080. Nothing here is exposed to the LAN
directly and no ports are forwarded on the router.

Every accepted message is appended to messages.jsonl before the email is
attempted, so a broken SMTP config loses the mail but never the message.
"""

import json
import os
import re
import smtplib
import threading
import time
from collections import defaultdict, deque
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from pathlib import Path

from flask import Flask, jsonify, request

# ── config (all via environment; see .env.example) ──────────────────
ALLOWED_ORIGINS = {
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
}
MESSAGE_LOG = Path(os.environ.get("MESSAGE_LOG", "messages.jsonl"))

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
MAIL_TO = os.environ.get("MAIL_TO", "")

RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX", "5"))
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "3600"))  # seconds

MAX_NAME = 120
MAX_EMAIL = 254
MAX_MESSAGE = 5000
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # a text form; anything larger is not one

# ── rate limiting ───────────────────────────────────────────────────
# In-memory, so run a single worker process (see contact.service). A contact
# form on a personal site does not justify Redis.
_hits: "defaultdict[str, deque]" = defaultdict(deque)
_hits_lock = threading.Lock()


def client_ip() -> str:
    """Real client IP.

    Cloudflare sets CF-Connecting-IP; trust it only because this app is
    reachable exclusively through the tunnel. request.remote_addr would
    otherwise always be 127.0.0.1.
    """
    return request.headers.get("CF-Connecting-IP") or request.remote_addr or "unknown"


def rate_limited(ip: str) -> bool:
    now = time.monotonic()
    with _hits_lock:
        window = _hits[ip]
        while window and now - window[0] > RATE_LIMIT_WINDOW:
            window.popleft()
        if len(window) >= RATE_LIMIT_MAX:
            return True
        window.append(now)

        # Keep the dict from growing without bound on a long-lived process.
        if len(_hits) > 5000:
            for stale in [k for k, v in _hits.items() if not v]:
                del _hits[stale]
    return False


# ── CORS ────────────────────────────────────────────────────────────
@app.after_request
def add_cors(response):
    origin = request.headers.get("Origin")
    if origin and origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Max-Age"] = "86400"
    return response


# ── email ───────────────────────────────────────────────────────────
def send_email(name: str, email: str, message: str, ip: str) -> None:
    if not (SMTP_USER and SMTP_PASS and MAIL_TO):
        app.logger.warning("SMTP not configured; message logged only")
        return

    msg = EmailMessage()
    msg["Subject"] = f"Portfolio contact — {name}"
    msg["From"] = formataddr(("kai-spicer.com", SMTP_USER))
    msg["To"] = MAIL_TO
    # Reply goes to the sender, but the From stays our own address so the mail
    # is not rejected for spoofing a domain we do not control.
    msg["Reply-To"] = formataddr((name, email))
    msg.set_content(
        f"From: {name} <{email}>\n"
        f"IP:   {ip}\n"
        f"{'-' * 50}\n\n"
        f"{message}\n"
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)


# ── routes ──────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return jsonify(ok=True)


@app.route("/api/contact", methods=["POST", "OPTIONS"])
def contact():
    if request.method == "OPTIONS":
        return ("", 204)

    ip = client_ip()
    if rate_limited(ip):
        return jsonify(error="rate limited"), 429

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="expected a JSON object"), 400

    # Honeypot: a hidden field only a bot would fill. Answer 200 so the bot
    # records a success and does not retry with the field left blank.
    if str(data.get("website", "")).strip():
        app.logger.info("honeypot triggered from %s", ip)
        return jsonify(ok=True), 200

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip()
    message = str(data.get("message", "")).strip()

    if not name or not message:
        return jsonify(error="name and message are required"), 400
    if len(name) > MAX_NAME or len(email) > MAX_EMAIL or len(message) > MAX_MESSAGE:
        return jsonify(error="field too long"), 400
    if not EMAIL_RE.match(email) or parseaddr(email)[1] != email:
        return jsonify(error="invalid email"), 400
    if any(c in name + email for c in "\r\n"):  # header injection
        return jsonify(error="invalid input"), 400

    record = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ip": ip,
        "name": name,
        "email": email,
        "message": message,
    }
    MESSAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with MESSAGE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    try:
        send_email(name, email, message, ip)
    except Exception:
        # The message is already on disk, so report success to the sender and
        # leave a traceback for me rather than asking them to send it twice.
        app.logger.exception("failed to send contact email")

    return jsonify(ok=True), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
