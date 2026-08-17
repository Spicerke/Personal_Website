// Contact form → the Raspberry Pi endpoint, exposed over HTTPS by a Cloudflare Tunnel.
// See server/README.md for the Pi side. Must be https:// — a static site served over
// HTTPS cannot POST to a plain http:// address (browsers block it as mixed content).
const ENDPOINT = 'https://api.kaispicer.com/api/contact';

const form = document.getElementById('contact-form');
const status = document.getElementById('form-status');
const button = document.getElementById('submit-btn');

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function fail(message) {
  status.style.color = 'var(--muted)';
  status.textContent = message;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const payload = {
    name: form.name.value.trim(),
    email: form.email.value.trim(),
    message: form.message.value.trim(),
    website: form.website.value, // honeypot — real people never see this field
  };

  if (!payload.name || !payload.message) {
    return fail('Name and message are required.');
  }
  if (!EMAIL_RE.test(payload.email)) {
    return fail("That email doesn't look right.");
  }

  button.textContent = 'sending…';
  button.disabled = true;
  status.textContent = '';

  try {
    const res = await fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (res.status === 429) {
      throw new Error('rate_limited');
    }
    if (!res.ok) {
      throw new Error(String(res.status));
    }

    form.reset();
    status.style.color = 'var(--accent)';
    status.textContent = "Thanks — I'll get back to you.";
    if (window.posthog) {
      posthog.capture('contact form submitted', { outcome: 'success' });
    }
  } catch (err) {
    if (err.message === 'rate_limited') {
      fail('Too many messages just now — try again in a few minutes.');
    } else {
      fail('Something went wrong. Email me directly?');
    }
    if (window.posthog) {
      posthog.capture('contact form submitted', { outcome: 'error', reason: err.message });
    }
  } finally {
    button.textContent = 'send message';
    button.disabled = false;
  }
});
