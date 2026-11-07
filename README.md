# Kai Spicer's personal site

Live at [kai-spicer.com](https://kai-spicer.com)

To work on it locally, use the dev server in the session scratchpad rather than
`python3 -m http.server`:

```bash
python3 serve.py 8000
```
## Deploying

The site is a **Worker serving `public/` as static assets**. `wrangler.jsonc` is
the entire configuration — there is no Worker script, and `assets.directory`
alone makes Cloudflare serve the folder from its edge.

**Every push to `main` deploys**, via `.github/workflows/deploy.yml`. 
After deploying it purges the Cloudflare edge cache (a zone Cache Rule caches
HTML and ignores query strings, so a green deploy can otherwise sit behind a
stale page), then checks every page in `public/` byte-for-byte against the live site.


Three repo secrets, **Settings → Secrets and variables → Actions**:

| Secret | Value |
| --- | --- |
| `CLOUDFLARE_API_TOKEN` | **My Profile → API Tokens → Create Token → Edit Cloudflare Workers**. That template grants Workers Scripts edit *and* Workers Routes edit; both are needed, since a deploy reconciles the custom domains in `wrangler.jsonc`. Also add **Zone → Cache Purge → Purge** for kai-spicer.com, for the purge step. |
| `CLOUDFLARE_ZONE_ID` | the Zone ID on the kai-spicer.com **Overview** page, right-hand sidebar |
| `CLOUDFLARE_ACCOUNT_ID` | the account ID from the dashboard sidebar, or `npx wrangler whoami` |

To deploy by hand — a one-off, or if Actions is unavailable:

```bash
npx wrangler deploy
```

A hand deploy doesn't purge the cache, so purge it afterwards (dashboard →
**Caching → Configuration → Purge Cache**). A query string does *not* get past
the cache here. Then verify against the edge rather than trusting a browser reload:

```bash
curl -s https://kai-spicer.com/experience | diff -q - public/experience.html && echo live
```

`npx wrangler deployments list` shows what is actually published and when, which
is the fastest way to answer "is my change live?".


## Uptime monitoring

Everything dynamic on this site runs on one Raspberry Pi behind one Cloudflare
tunnel — the contact endpoint, the Claim Detection demo, and the C web server —
so they fail together and a single check covers all three.

**On the site:** `status.js` calls `api.kai-spicer.com/api/health` on load and
every 60s while the tab is visible. On failure it reveals the `#pi-status`
banner at the top of the page. It starts hidden, so a slow network never
flashes a false warning, and it skips the check entirely on `localhost` (that
origin isn't in the API's `ALLOWED_ORIGINS`, so it would always fail locally).

**By email:** `.github/workflows/pi-uptime.yml` runs `monitor/check_pi.py` on
GitHub Actions every 15 minutes. It deliberately does *not* run on the Pi — a
monitor hosted on the machine it watches goes down with it.

Email fires only on a state *change*, never every run. Since each Actions run
starts from a clean checkout with no memory of the last, the previous state is
held in a GitHub issue labelled `pi-down`: opened on the way down, closed on the
way back up. Each endpoint is retried 3× with a 5s backoff first, so one flaky
request doesn't page you.

Requires three repo secrets — **Settings → Secrets and variables → Actions**:

| Secret | Value |
| --- | --- |
| `SMTP_USER` | the Gmail address that sends |
| `SMTP_PASS` | its 16-character App Password, no spaces |
| `MAIL_TO` | where alerts should land |

Test it without waiting for the cron: **Actions → Pi uptime → Run workflow**.
Locally, `DRY_RUN=1 python3 monitor/check_pi.py` checks and prints without
sending anything or touching issues.



## Contact form

`contact.js` POSTs JSON to `ENDPOINT` (top of the file) — the Flask app in
`server/`, running on the Raspberry Pi and exposed over HTTPS by a Cloudflare
Tunnel:

```json
{ "name": "…", "email": "…", "message": "…", "website": "" }
```

`website` is a honeypot; real users never see it. Any 2xx counts as success.

The endpoint **must** be `https://` — a site served over HTTPS cannot POST to a
plain `http://` address, so pointing this at the Pi's LAN IP will be blocked as
mixed content. Full setup in [`server/README.md`](server/README.md).
