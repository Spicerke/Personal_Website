#!/usr/bin/env python3
"""Check the Raspberry Pi's public endpoints and email on a state change.

Runs on GitHub Actions, deliberately not on the Pi -- a monitor hosted on the
machine it watches cannot tell you that machine is down.

Email goes out only when the state *changes* (up -> down, down -> up). The
previous state lives in a GitHub issue label rather than a file, because each
Actions run starts from a clean checkout with no memory of the last one.

Env:
  SMTP_USER, SMTP_PASS, MAIL_TO   Gmail account + app password
  GITHUB_TOKEN, GITHUB_REPOSITORY provided by Actions
  DRY_RUN=1                       check and report, send nothing
"""

import json
import os
import smtplib
import ssl
import sys
import time
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import formataddr

CHECKS = [
    ("contact API",  "https://api.kai-spicer.com/api/health",   True),
    ("claim demo",   "https://claims.kai-spicer.com/",          False),
    ("C web server", "https://demo.kai-spicer.com/",            False),
]

ATTEMPTS = 3          # a single failure is usually the network, not the Pi
BACKOFF = 5           # seconds between attempts
TIMEOUT = 15
ISSUE_TITLE = "Raspberry Pi is unreachable"


def probe(url, expect_json):
    """One request. Returns (ok, detail)."""
    req = urllib.request.Request(url, headers={"User-Agent": "kai-uptime/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(400)
            if r.status != 200:
                return False, f"HTTP {r.status}"
            if expect_json:
                try:
                    if not json.loads(body.decode()).get("ok"):
                        return False, "health returned ok=false"
                except Exception:
                    return False, "health returned non-JSON"
            return True, "200"
    except urllib.error.HTTPError as e:
        # 530 is Cloudflare error 1033: the tunnel has no connection.
        hint = " (tunnel down -- cloudflared not connected)" if e.code == 530 else ""
        return False, f"HTTP {e.code}{hint}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def run_checks():
    results = []
    for name, url, expect_json in CHECKS:
        ok, detail = False, ""
        for attempt in range(ATTEMPTS):
            ok, detail = probe(url, expect_json)
            if ok:
                break
            if attempt < ATTEMPTS - 1:
                time.sleep(BACKOFF)
        results.append((name, url, ok, detail))
    return results


# ---------------------------------------------------------------- gh state
def gh(method, path, payload=None):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not (token and repo):
        return None
    url = f"https://api.github.com/repos/{repo}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "kai-uptime/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode() or "null")
    except Exception as e:
        print(f"  github api {method} {path} failed: {e}", file=sys.stderr)
        return None


def open_incident():
    found = gh("GET", "/issues?state=open&labels=pi-down&per_page=1")
    return found[0] if found else None


# ------------------------------------------------------------------- email
def send(subject, body):
    user, pw, to = (os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS"),
                    os.environ.get("MAIL_TO"))
    if not (user and pw and to):
        print("  SMTP not configured; skipping email", file=sys.stderr)
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr(("kai-spicer.com uptime", user))
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
        s.starttls(context=ssl.create_default_context())
        s.login(user, pw)
        s.send_message(msg)
    print(f"  emailed {to}: {subject}")


def main():
    results = run_checks()
    down = [r for r in results if not r[2]]
    width = max(len(n) for n, *_ in results)
    for name, url, ok, detail in results:
        print(f"  {name.ljust(width)}  {'UP  ' if ok else 'DOWN'}  {detail}")

    incident = open_incident()
    dry = os.environ.get("DRY_RUN") == "1"
    stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    lines = "\n".join(f"  {n.ljust(width)}  {'UP' if o else 'DOWN'}  {d}"
                      for n, _, o, d in results)

    if down and not incident:
        body = (f"The Raspberry Pi stopped responding at {stamp}.\n\n{lines}\n\n"
                "All three services share one Cloudflare tunnel, so they fail together.\n"
                "Check in this order:\n"
                "  ssh spicerke@pi5                 # tailnet, works from any network\n"
                "  systemctl is-active cloudflared demo-web projdb kai-contact\n"
                "  sudo journalctl -u cloudflared -n 40\n\n"
                "If ssh also fails, the Pi is powered off or off the network.\n")
        print("\n  STATE CHANGE: up -> down")
        if dry:
            print("  (dry run, no email, no issue)")
        else:
            send("Pi is DOWN - kai-spicer.com services affected", body)
            gh("POST", "/issues", {"title": ISSUE_TITLE, "body": body, "labels": ["pi-down"]})

    elif not down and incident:
        body = f"The Raspberry Pi is responding again as of {stamp}.\n\n{lines}\n"
        print("\n  STATE CHANGE: down -> up")
        if dry:
            print("  (dry run, no email, issue left open)")
        else:
            send("Pi is back UP", body)
            gh("POST", f"/issues/{incident['number']}/comments", {"body": body})
            gh("PATCH", f"/issues/{incident['number']}", {"state": "closed"})

    else:
        print(f"\n  no state change (currently {'DOWN' if down else 'UP'})")

    return 0
if __name__ == "__main__":
    sys.exit(main())
