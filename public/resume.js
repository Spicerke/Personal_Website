// Inline résumé reader.
//
// The browser's built-in PDF viewer is fine on desktop but unreliable on
// mobile — iOS Safari renders only the first page of an <iframe>ed PDF, and
// several Android browsers refuse entirely. PDF.js renders each page to a
// canvas instead, so every device gets the same continuous scroll, styled to
// match the site rather than framed in browser chrome.
//
// This is progressive enhancement: the markup already contains the native
// viewer. Only once every page has rendered successfully do we swap it out. If
// the CDN is blocked, the version drifts, or anything else throws, the native
// viewer is simply left alone.

const PDF_URL = 'Downloaders/Spicer_Resume.pdf';
const PDFJS = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/6.2.108';

const pagesEl = document.getElementById('pdf-pages');
const nativeEl = document.getElementById('pdf-native');
const statusEl = document.getElementById('pdf-status');

// Cap the backing store so a hi-DPI screen doesn't allocate a 4x canvas per page.
const DPR = Math.min(window.devicePixelRatio || 1, 2);

const canvasStyle =
  'display:block;width:100%;height:auto;border:1px solid var(--line);' +
  'border-radius:4px;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,0.06)';

let doc = null;

async function renderAll() {
  const width = pagesEl.clientWidth || nativeEl.clientWidth;
  if (!width) return;

  const rendered = document.createDocumentFragment();

  for (let n = 1; n <= doc.numPages; n++) {
    const page = await doc.getPage(n);

    // scale:1 is the PDF's intrinsic size; scale so the page fills the column.
    const base = page.getViewport({ scale: 1 });
    const viewport = page.getViewport({ scale: width / base.width });

    const canvas = document.createElement('canvas');
    canvas.width = Math.floor(viewport.width * DPR);
    canvas.height = Math.floor(viewport.height * DPR);
    canvas.style.cssText = canvasStyle;
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', `Résumé page ${n} of ${doc.numPages}`);

    await page.render({
      canvasContext: canvas.getContext('2d'),
      viewport,
      transform: DPR === 1 ? null : [DPR, 0, 0, DPR, 0, 0],
    }).promise;

    rendered.appendChild(canvas);
  }

  pagesEl.replaceChildren(rendered);
}

function debounce(fn, ms) {
  let t;
  return () => { clearTimeout(t); t = setTimeout(fn, ms); };
}

try {
  statusEl.textContent = 'loading résumé…';

  const pdfjsLib = await import(`${PDFJS}/pdf.min.mjs`);
  pdfjsLib.GlobalWorkerOptions.workerSrc = `${PDFJS}/pdf.worker.min.mjs`;

  doc = await pdfjsLib.getDocument(PDF_URL).promise;

  // Measure against the native container's width while #pdf-pages is still
  // hidden — a hidden element has clientWidth 0.
  pagesEl.style.cssText = 'display:flex;flex-direction:column;gap:16px;visibility:hidden';
  pagesEl.hidden = false;

  await renderAll();

  pagesEl.style.visibility = '';
  nativeEl.remove();
  statusEl.textContent = doc.numPages === 1 ? '1 page' : `${doc.numPages} pages`;

  // Re-render on resize so the canvases stay sharp instead of being upscaled.
  window.addEventListener('resize', debounce(() => {
    renderAll().catch(() => { /* keep the pages already on screen */ });
  }, 250));
} catch (err) {
  console.warn('PDF.js reader unavailable, using the browser viewer:', err);
  pagesEl.hidden = true;
  pagesEl.replaceChildren();
  statusEl.textContent = '';
}
