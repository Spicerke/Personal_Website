// Pi status banner. Everything dynamic on this site — the contact form, the
// Claim Detection demo, the C web server — runs on one Raspberry Pi behind one
// Cloudflare tunnel, so a single health check covers all of them.
//
// The banner starts hidden and is only revealed on a failed check, so a slow
// network never flashes a warning at someone whose services are fine.
(function () {
  var HEALTH = 'https://api.kai-spicer.com/api/health';
  var RECHECK_MS = 60000;

  var bar = document.getElementById('pi-status');
  if (!bar) return;

  // The banner is not dismissible -- if the Pi is down the contact form and the
  // demos genuinely do not work, and a visitor who dismissed it would be left
  // wondering why nothing responds.
  //
  // ?pi=down forces it on, ?pi=up forces it off. Lets you see what a visitor
  // sees during an outage without waiting for one, on the live site too.
  var force = new URLSearchParams(location.search).get('pi');

  // Locally the origin isn't in the API's ALLOWED_ORIGINS, so the check would
  // always fail and pin the banner open. Skip it during development -- unless
  // we were explicitly asked to preview.
  var host = location.hostname;
  var isLocal = (host === 'localhost' || host === '127.0.0.1' || host === '');


  function show() {
    bar.hidden = false;
    if (window.posthog) posthog.capture('pi down banner shown');
  }
  function hide() { bar.hidden = true; }

  function check() {
    // A real CORS response means the tunnel is up and Flask answered. When the
    // Pi is down Cloudflare returns 530 with no CORS headers, so fetch rejects
    // — which is exactly the signal we want.
    return fetch(HEALTH, { cache: 'no-store', mode: 'cors' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { (j && j.ok) ? hide() : show(); })
      .catch(show);
  }

  if (force === 'down') { show(); return; }
  if (force === 'up')   { hide(); return; }
  if (isLocal) return;

  check();
  setInterval(function () { if (!document.hidden) check(); }, RECHECK_MS);
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) check();
  });
})();
