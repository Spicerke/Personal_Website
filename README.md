# Kai Spicer — personal site

Plain HTML/CSS/JS. No build step, no framework. Live at
[kai-spicer.com](https://kai-spicer.com) on Cloudflare Pages.

```
public/                       ← everything here is published; nothing else is
  index.html                  About / landing
  experience.html             Card index + publications (#publications)
    experience-l2-labs.html
    experience-direct-lab.html
    experience-pnnl.html
  projects.html               Card index
    project-claim-detection.html
    project-free-throw.html
    server-writeup.html       HTTP Server in C — self-contained, meant to be served BY that server
  resume.html                 Inline PDF reader + download button
  contact.html                Contact form + direct links
  styles.css                  Tokens, card/hover states, form focus, image styles
  analytics.js                PostHog init + custom event wiring (every page)
  contact.js                  Contact form submit handler (contact.html only)
  resume.js                   PDF.js résumé reader (resume.html only)
  _headers                    Security + cache headers, applied by Pages
  images/                     Screenshots and portrait
  Downloaders/                Résumé, CV, SULI report PDFs

server/                       Raspberry Pi contact endpoint — see server/README.md
```

Experience and projects are **card indexes**: each card is a single `<a class="card">`
in a `repeat(auto-fit, minmax(320px, 1fr))` grid, linking to its own detail page.
The card's box lives in the inline `style` on that anchor, not in `styles.css` —
layout inline, stylesheet for interactive state only. That is the design's own
convention, and it means a stale cached stylesheet can never strip the border or
let the global link underline bleed into the card text.
A card has five slots — title + date, role/tag line, one-sentence blurb, tech chips,
and a footer rule with `read more →`. `margin-top:auto` on the chips pins the footer
so cards of different text lengths still align along the bottom. To add one, copy a
card and change the five slots.

`server-writeup.html` is deliberately self-contained — no external CSS, fonts, or
scripts — because it is meant to be served by the C server itself as the demo. Its
log pane polls `/log` and falls back to sample lines when that route is absent, which
is what happens on Pages. Point the projects card at `http://your-host:8080/writeup.html`
once the server is running somewhere.

To work on it locally:

```bash
cd public && python3 -m http.server
```

Serve from `public/`, not the repo root — that's what Pages publishes, so it's
the only layout that matches production.

Everything except the pieces above is inline `style="…"` on the elements
themselves — intentional, so a page is self-contained and easy to tweak in
place.

Filenames are all lowercase because GitHub Pages serves from a case-sensitive
filesystem while macOS does not. A path that works locally can 404 in
production; keeping one casing convention avoids the whole class of bug.

## Deploying

Cloudflare Pages, connected to this repo. Every push to `main` deploys; pull
requests get their own preview URL.

One-time setup in [dash.cloudflare.com](https://dash.cloudflare.com) →
**Workers & Pages → Create → Pages → Connect to Git**:

| Setting | Value |
| --- | --- |
| Repository | `Spicerke/Personal_Website` |
| Production branch | `main` |
| Framework preset | None |
| Build command | *(leave blank)* |
| Build output directory | `public` |

Then **Custom domains → Set up a custom domain**, and add `kai-spicer.com` and
`www.kai-spicer.com`. Because the zone is already in the same Cloudflare
account, the DNS records are created for you — don't add them by hand.

**Why the `public/` directory exists.** Pages has no ignore file: whatever is in
the output directory gets published. Deploying from the repo root would put
`server/app.py` and the Pi setup notes on the public site at
`kai-spicer.com/server/…`. Nothing there is secret — it's a public repo — but
the contact endpoint's rate-limit thresholds aren't worth handing out. Keeping
the site in `public/` means the server code can't be published by accident.

`_headers` is read and applied by Pages, not served. The CSP in it is
deliberately `Content-Security-Policy-Report-Only` for now; see the comments in
that file for how to promote it to enforcing once you've confirmed no
violations in the console.

Cloudflare now points new projects at Workers static assets rather than Pages —
Pages is fully supported and not deprecated, but the feature work goes to
Workers. Nothing here is Pages-specific except `_headers`, so switching later
means adding a `wrangler.jsonc` with `assets.directory = "./public"`.


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


## Social cards and favicon

Every page carries `<meta name="description">`, a canonical URL, Open Graph and
Twitter card tags, and the icon set. All of it is generated, so a new page picks
it up automatically — add an entry to `DESCRIPTIONS` in `gen.py` and it's done.
Without one a page falls back to the homepage description, which is wrong but
never blank.

| File | What it is |
| --- | --- |
| `og-card.png` | 1200×630 share card: portrait, name, tagline, domain |
| `favicon.svg` | KS monogram in the accent green, scales to any size |
| `favicon-32.png` | raster fallback for browsers that ignore SVG icons |
| `favicon.ico` | 16/32/48 multi-size, for older browsers |
| `apple-touch-icon.png` | 180×180, used when the site is saved to an iOS home screen |

The card is 1200×630 on purpose: LinkedIn renders that ratio as a large card,
while a square image collapses to a small thumbnail beside the text. Regenerate
it by re-running the Pillow snippet in the session notes, or edit the PNG
directly — nothing reads its contents.

The homepage canonicalises to `https://kai-spicer.com/`, not `/index.html`, so
the two don't look like separate pages to a crawler.

**After deploying**, prime LinkedIn's cache with the
[Post Inspector](https://www.linkedin.com/post-inspector/) — it caches
aggressively, and a URL it fetched before the tags existed will keep showing a
bare link until you force a re-scrape.

## Design tokens

Defined once in `styles.css` `:root`:

| Token | Value | Use |
| --- | --- | --- |
| `--bg` | `#faf8f3` | page background |
| `--fg` | `#191813` | body text, logo |
| `--muted` | `#6b6558` | secondary text, labels, inactive nav |
| `--line` | `#e4ded1` | borders, rules |
| `--accent` | `oklch(0.48 0.07 150)` | links, focus, primary emphasis |
| `--card` | `#f4f1e8` | contact card, image placeholders |

Type: IBM Plex Sans for prose, IBM Plex Mono for labels, nav, metadata (loaded
from Google Fonts). Body copy 17px / 1.75; measure capped at 62–66ch. Content
column is 760px (900px on the résumé page).

Light only. Dark mode was removed deliberately — if you want it back, add a
`@media (prefers-color-scheme: dark)` block overriding the `:root` tokens;
nothing else needs to change.

## Analytics

`analytics.js` loads PostHog (US cloud) on every page. The `phc_…` project key
in that file is a public client-side key — it's meant to ship in the page, and
it can only write events, not read them.

Nothing calls `identify()`, so every visitor — you included — is anonymous: a
random `distinct_id` in a cookie, no email, no person profile. PostHog cannot
tell you apart from a stranger, which is why the two escape hatches below exist.

**Local development** already reports; the site does not need to be deployed.
`internal_or_test_user_hostname` flags `localhost` and `127.0.0.1` traffic as
internal so it still arrives (you can verify tracking works) but stays out of
your numbers — switch on *Project settings → Filter out internal and test users*
for that to take effect. Note that `file://` URLs are unreliable and ad blockers
block PostHog outright, so test on the local server in a normal window.

**Excluding yourself from the live site:** visit any page once with `?ph=off`.
That calls `opt_out_capturing()`, which persists in localStorage for that
browser; `?ph=on` reverses it.

Autocapture handles pageviews and raw clicks. On top of that:

| Event | Fires when |
| --- | --- |
| `document downloaded` | any `<a download>` — résumé, CV, SULI PDF |
| `email link clicked` | any `mailto:` link |
| `outbound link clicked` | any link to another hostname (GitHub, LinkedIn, L2 Labs) |
| `contact form submitted` | contact form submit, with `outcome: success \| error` |

## Résumé reader

`resume.js` renders `Downloaders/Spicer_Resume.pdf` to one canvas per page with
[PDF.js](https://mozilla.github.io/pdf.js/) 6.2.108, pinned by version on
cdnjs. The browser's own viewer is unreliable on mobile — iOS Safari shows only
the first page of an `<iframe>`d PDF — so this gives every device the same
continuous scroll, styled to the site instead of framed in browser chrome.

It's progressive enhancement: `resume.html` ships with the native viewer in
place, and it's only removed once every page has rendered. If the CDN is
blocked or the API drifts, the native viewer stays and a warning goes to the
console. Canvases re-render on resize so they never look upscaled.

To bump the version, change `PDFJS` at the top of `resume.js` — both the library
and its worker are loaded from that one constant.

Text isn't selectable in canvas mode (there's no text layer). The download
button is the way to get copyable text.

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

## Adding a section

Copy a card in `experience.html` or `projects.html`, change its five slots, and
add the matching detail page. The nav is flat and duplicated per page, so adding
a *top-level* page means updating the `<nav>` in every file — that's the one
thing to keep in sync. Detail pages need no nav change; they just highlight
their parent.
