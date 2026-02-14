#!/usr/bin/env node
// Generates static HTML pages for all TLR cameras from tlrguide JSON data.
// Run: node build-cameras.js

const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(require('os').homedir(), 'tlrguide/data/cameras');
const OUT_DIR = path.join(__dirname, 'cameras');

// Read all camera JSON files
const files = fs.readdirSync(DATA_DIR).filter(f => f.endsWith('.json'));
const cameras = files.map(f => JSON.parse(fs.readFileSync(path.join(DATA_DIR, f), 'utf8')));

// Sort by brand then year
cameras.sort((a, b) => a.brand.localeCompare(b.brand) || a.yearStart - b.yearStart);

// Group by brand
const brands = {};
for (const cam of cameras) {
  if (!brands[cam.brand]) brands[cam.brand] = [];
  brands[cam.brand].push(cam);
}

// Brand display order
const brandOrder = ['Rollei', 'Yashica', 'Mamiya', 'Minolta'];

function escHtml(s) {
  if (!s) return '';
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatPrice(pricing) {
  if (!pricing) return '';
  const conditions = ['poor', 'average', 'good', 'excellent', 'mint'];
  const labels = ['Poor', 'Average', 'Good', 'Excellent', 'Mint'];
  let rows = '';
  for (let i = 0; i < conditions.length; i++) {
    const p = pricing[conditions[i]];
    if (p) {
      rows += `<tr><td>${labels[i]}</td><td>$${p.min} – $${p.max}</td></tr>`;
    }
  }
  if (!rows) return '';
  return `
    <div class="pricing-table">
      <h3>Current Market Prices (USD)</h3>
      <table>
        <thead><tr><th scope="col">Condition</th><th scope="col">Price Range</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${pricing.source ? `<p class="price-source">Source: ${escHtml(pricing.source)}</p>` : ''}
    </div>`;
}

function specsTable(specs) {
  if (!specs) return '';
  const fields = [
    ['takingLens', 'Taking Lens'],
    ['viewingLens', 'Viewing Lens'],
    ['elements', 'Lens Elements'],
    ['shutter', 'Shutter'],
    ['shutterSpeeds', 'Shutter Speeds'],
    ['meter', 'Light Meter'],
    ['filterMount', 'Filter Mount'],
    ['focusing', 'Focusing'],
    ['weight', 'Weight'],
  ];
  let rows = '';
  for (const [key, label] of fields) {
    if (specs[key]) {
      rows += `<tr><td>${label}</td><td>${escHtml(String(specs[key]))}</td></tr>`;
    }
  }
  return `<table class="specs-table" role="table" aria-label="Camera specifications"><tbody>${rows}</tbody></table>`;
}

function relatedCameras(cam) {
  // Find cameras from same brand, excluding self
  const siblings = (brands[cam.brand] || []).filter(c => c.id !== cam.id);
  if (siblings.length === 0) return '';
  const links = siblings.map(c =>
    `<a href="/cameras/${c.id}.html">${escHtml(c.fullName)}</a>`
  ).join(', ');
  return `<div class="related"><h3>More ${escHtml(cam.brand)} TLR Cameras</h3><p>${links}</p></div>`;
}

function articlesList(articles) {
  if (!articles || articles.length === 0) return '';
  const items = articles.map(a =>
    `<li><a href="${escHtml(a.url)}" target="_blank" rel="noopener">${escHtml(a.title)}</a> <span class="source">— ${escHtml(a.source)}</span></li>`
  ).join('\n');
  return `<div class="resources"><h3>Articles &amp; Reviews</h3><ul>${items}</ul></div>`;
}

function manualsList(manuals) {
  if (!manuals || manuals.length === 0) return '';
  const items = manuals.map(m =>
    `<li><a href="${escHtml(m.url)}" target="_blank" rel="noopener">${escHtml(m.source)}</a></li>`
  ).join('\n');
  return `<div class="resources"><h3>Manuals &amp; Documentation</h3><ul>${items}</ul></div>`;
}

function galleriesList(galleries) {
  if (!galleries || galleries.length === 0) return '';
  const items = galleries.map(g => {
    // nofollow Google Images links, keep editorial links (Flickr, Wikimedia) as dofollow
    const isGoogle = g.url && g.url.includes('google.com');
    const rel = isGoogle ? 'noopener nofollow' : 'noopener';
    return `<li><a href="${escHtml(g.url)}" target="_blank" rel="${rel}">${escHtml(g.label)}</a></li>`;
  }).join('\n');
  return `<div class="resources"><h3>Photo Galleries</h3><ul>${items}</ul></div>`;
}

function imageAttribution(attr) {
  if (!attr) return '';
  return `<p class="attribution">Photo: ${escHtml(attr.author)} · <a href="${escHtml(attr.licenseUrl)}" target="_blank" rel="noopener">${escHtml(attr.license)}</a> · <a href="${escHtml(attr.sourceUrl)}" target="_blank" rel="noopener">Source</a></p>`;
}

function jsonLd(cam) {
  const data = {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": cam.fullName,
    "description": cam.tagline || `${cam.fullName} twin-lens reflex camera`,
    "brand": { "@type": "Brand", "name": cam.brand },
    "category": "Twin-Lens Reflex Camera",
    "image": cam.localImage ? `https://metergeist.com/images/${path.basename(cam.localImage)}` : undefined,
  };
  if (cam.pricing && cam.pricing.average) {
    data.offers = {
      "@type": "AggregateOffer",
      "priceCurrency": "USD",
      "lowPrice": cam.pricing.poor?.min || cam.pricing.average.min,
      "highPrice": cam.pricing.mint?.max || cam.pricing.excellent?.max || cam.pricing.average.max,
      "offerCount": 1,
    };
  }
  return `<script type="application/ld+json">${JSON.stringify(data)}</script>`;
}

// Generate individual camera pages
for (const cam of cameras) {
  const years = cam.yearEnd ? `${cam.yearStart}–${cam.yearEnd}` : `${cam.yearStart}`;
  const taglineClean = (cam.tagline || 'Twin-lens reflex camera').replace(/\.\s*$/, '');
  const metaDesc = `${cam.fullName} (${years}) — ${taglineClean}. Specs, pricing, history, and resources.`;
  const imgFile = cam.localImage ? path.basename(cam.localImage) : null;

  const featuresHtml = cam.features && cam.features.length > 0
    ? `<ul class="features-list">${cam.features.map(f => `<li>${escHtml(f)}</li>`).join('')}</ul>`
    : '';

  const innovationsHtml = cam.innovations && cam.innovations.length > 0
    ? `<div class="innovations"><h3>Innovations</h3><ul>${cam.innovations.map(i => `<li>${escHtml(i)}</li>`).join('')}</ul></div>`
    : '';

  const famousUsersHtml = cam.famousUsers
    ? `<div class="famous-users"><h3>Notable Photographers</h3><p>${escHtml(cam.famousUsers)}</p></div>`
    : '';

  const popCultureHtml = cam.popCulture
    ? `<div class="pop-culture"><h3>Cultural Significance</h3><p>${escHtml(cam.popCulture)}</p></div>`
    : '';

  const notesHtml = cam.notes
    ? `<div class="collector-notes"><h3>Collector Notes</h3><p>${escHtml(cam.notes)}</p></div>`
    : '';

  const ebayHtml = cam.ebayUrl
    ? `<p class="shop-link"><a href="${escHtml(cam.ebayUrl)}" target="_blank" rel="noopener nofollow sponsored">Shop for ${escHtml(cam.fullName)} on eBay</a></p>`
    : '';

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escHtml(cam.fullName)} — TLR Camera Guide | metergeist</title>
  <meta name="description" content="${escHtml(metaDesc)}">
  <meta property="og:title" content="${escHtml(cam.fullName)} — TLR Camera Guide">
  <meta property="og:description" content="${escHtml(metaDesc)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="https://metergeist.com/cameras/${cam.id}.html">
  ${imgFile ? `<meta property="og:image" content="https://metergeist.com/images/${imgFile}">` : ''}
  <link rel="stylesheet" href="/style.css">
  <link rel="stylesheet" href="/cameras/cameras.css">
  <link rel="icon" href="/icon.png" type="image/png">
  <link rel="canonical" href="https://metergeist.com/cameras/${cam.id}.html">
  ${jsonLd(cam)}
</head>
<body>
  <a href="#main" class="skip-link">Skip to content</a>
  <nav aria-label="Main navigation">
    <a href="/" class="logo">
      <img src="/icon.png" alt="metergeist icon">
      <span>metergeist</span>
    </a>
    <div class="links">
      <a href="/cameras/">TLR Guide</a>
      <a href="/privacy.html">Privacy</a>
      <a href="/support.html">Support</a>
    </div>
  </nav>

  <main id="main">
  <div class="content camera-page">
    <p class="breadcrumb"><a href="/cameras/">TLR Camera Guide</a> &rsaquo; <a href="/cameras/#${cam.brand.toLowerCase()}">${escHtml(cam.brand)}</a> &rsaquo; ${escHtml(cam.fullName)}</p>

    <h1>${escHtml(cam.fullName)}</h1>
    ${cam.tagline ? `<p class="cam-tagline">${escHtml(cam.tagline)}</p>` : ''}

    <div class="cam-meta">
      <span class="cam-years">${years}</span>
      <span class="cam-format">${escHtml(cam.format)} on ${escHtml((cam.film || ['120']).join('/'))} film</span>
      ${cam.madeIn ? `<span class="cam-origin">Made in ${escHtml(cam.madeIn)}</span>` : ''}
    </div>

    <div class="cam-layout">
      ${imgFile ? `
      <div class="cam-image">
        <img src="/images/${imgFile}" alt="${escHtml(cam.fullName)} twin-lens reflex camera" loading="lazy">
        ${imageAttribution(cam.imageAttribution)}
      </div>` : ''}

      <div class="cam-details">
        <h2>Specifications</h2>
        ${specsTable(cam.specs)}
        ${featuresHtml}
      </div>
    </div>

    ${cam.history ? `<div class="cam-history"><h2>History</h2><p>${escHtml(cam.history)}</p></div>` : ''}

    ${famousUsersHtml}
    ${popCultureHtml}
    ${innovationsHtml}
    ${notesHtml}

    ${formatPrice(cam.pricing)}
    ${ebayHtml}

    ${articlesList(cam.articles)}
    ${manualsList(cam.manuals)}
    ${galleriesList(cam.galleries)}

    ${relatedCameras(cam)}

    <div class="app-cta">
      <h3>Shoot with your ${escHtml(cam.fullName)}</h3>
      <p><a href="/">metergeist</a> is a free <a href="/">light meter app</a> and <a href="/">film roll tracker</a> built for <a href="/cameras/">TLR</a> and medium format photographers. Meter light, load film, track every frame.</p>
    </div>
  </div>
  </main>

  <footer>
    &copy; 2026 metergeist
    <div class="links">
      <a href="/cameras/">TLR Guide</a>
      <a href="/privacy.html">Privacy</a>
      <a href="/support.html">Support</a>
    </div>
  </footer>
</body>
</html>`;

  fs.writeFileSync(path.join(OUT_DIR, `${cam.id}.html`), html);
}

// Generate index page
const brandSections = brandOrder.map(brand => {
  const cams = brands[brand] || [];
  const cards = cams.map(cam => {
    const imgFile = cam.localImage ? path.basename(cam.localImage) : null;
    const years = cam.yearEnd ? `${cam.yearStart}–${cam.yearEnd}` : `${cam.yearStart}`;
    const priceRange = cam.pricing?.average
      ? `$${cam.pricing.average.min}–$${cam.pricing.average.max}`
      : '';
    return `
      <a href="/cameras/${cam.id}.html" class="camera-card">
        ${imgFile ? `<img src="/images/${imgFile}" alt="${escHtml(cam.fullName)} TLR camera" loading="lazy">` : ''}
        <div class="card-info">
          <h3>${escHtml(cam.fullName)}</h3>
          <span class="card-years">${years}</span>
          ${priceRange ? `<span class="card-price">${priceRange} avg</span>` : ''}
        </div>
      </a>`;
  }).join('\n');

  return `
    <div class="brand-section" id="${brand.toLowerCase()}">
      <h2>${escHtml(brand)} TLR Cameras</h2>
      <div class="camera-grid">${cards}</div>
    </div>`;
}).join('\n');

const indexHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TLR Camera Guide — Twin Lens Reflex Cameras | metergeist</title>
  <meta name="description" content="Complete guide to 48 twin-lens reflex (TLR) cameras. Specs, history, pricing, and resources for Rolleiflex, Rolleicord, Yashica, Mamiya, and Minolta TLR cameras.">
  <meta property="og:title" content="TLR Camera Guide — Twin Lens Reflex Cameras">
  <meta property="og:description" content="Complete guide to 48 TLR cameras. Specs, history, pricing, and resources for Rolleiflex, Yashica, Mamiya, and Minolta.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://metergeist.com/cameras/">
  <link rel="stylesheet" href="/style.css">
  <link rel="stylesheet" href="/cameras/cameras.css">
  <link rel="icon" href="/icon.png" type="image/png">
  <link rel="canonical" href="https://metergeist.com/cameras/">
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "name": "TLR Camera Guide",
    "description": "Complete guide to 48 twin-lens reflex cameras from Rolleiflex, Yashica, Mamiya, and Minolta.",
    "url": "https://metergeist.com/cameras/",
    "numberOfItems": ${cameras.length}
  }
  </script>
</head>
<body>
  <a href="#main" class="skip-link">Skip to content</a>
  <nav aria-label="Main navigation">
    <a href="/" class="logo">
      <img src="/icon.png" alt="metergeist icon">
      <span>metergeist</span>
    </a>
    <div class="links">
      <a href="/cameras/">TLR Guide</a>
      <a href="/privacy.html">Privacy</a>
      <a href="/support.html">Support</a>
    </div>
  </nav>

  <main id="main">
  <div class="content">
    <h1>TLR Camera Guide</h1>
    <p class="guide-intro">A comprehensive guide to <strong>${cameras.length} twin-lens reflex cameras</strong> spanning 1928 to 1986. Explore specs, history, current market prices, manuals, and sample photos for every major TLR from <a href="#rollei">Rolleiflex</a>, <a href="#yashica">Yashica</a>, <a href="#mamiya">Mamiya</a>, and <a href="#minolta">Minolta</a>.</p>

    <p class="guide-intro">Whether you're buying your first medium format camera or researching a specific model, this guide covers every TLR from the affordable <a href="/cameras/yashica-a.html">Yashica-A</a> to the legendary <a href="/cameras/rolleiflex-28f.html">Rolleiflex 2.8F</a>.</p>

    <div class="brand-nav">
      <a href="#rollei">Rolleiflex &amp; Rolleicord</a>
      <a href="#yashica">Yashica</a>
      <a href="#mamiya">Mamiya</a>
      <a href="#minolta">Minolta</a>
    </div>

    ${brandSections}

    <div class="app-cta">
      <h2>Meter light for your TLR</h2>
      <p><a href="/">metergeist</a> is a free <a href="/">light meter app for film photography</a> built for <a href="/cameras/">TLR camera</a> and medium format shooters. Real-time metering, film roll tracking, and reference photos — all on your iPhone.</p>
    </div>
  </div>
  </main>

  <footer>
    &copy; 2026 metergeist
    <div class="links">
      <a href="/cameras/">TLR Guide</a>
      <a href="/privacy.html">Privacy</a>
      <a href="/support.html">Support</a>
    </div>
  </footer>
</body>
</html>`;

fs.writeFileSync(path.join(OUT_DIR, 'index.html'), indexHtml);

console.log(`Generated ${cameras.length} camera pages + index in ${OUT_DIR}`);
