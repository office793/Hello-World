// Live captures from mottirozenfeld.com (Playwright + Chromium).
//
// usage: NODE_PATH=$(npm root -g) node tools/capture_site.js <work_dir>
//
// writes
//   site/enter/eNN.jpg   home page at phone size (390x844 css, DPR 2), scrolled 0..240 css px in 8 px steps
//   site/organ_0.jpg     V8.1 preview page, organ simulation: folder "מה חדש בעדכון V8.1"
//   site/organ_1.jpg     after tapping "02 Dance" (new dance styles 41-44)
//   site/organ_2.jpg     after tapping "08 DJ" (new DJ styles 51-55)
//   site/organ_boxes.json  element boxes (css px, relative to the panel) for tap / button overlays
//
// The cookie banner is accepted; floating widgets (chat button, accessibility launcher) are hidden.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const WORK = process.argv[2];
const HOME = 'https://mottirozenfeld.com/';
const PREVIEW = 'https://mottirozenfeld.com/updates/preview/cmuwlo1j4006582kdlw75x5th/#klidim';

async function acceptCookies(p) {
  const btn = await p.$('#qs-cookie-overlay >> text=הבנתי');
  if (btn) await btn.click().catch(() => {});
  await p.waitForTimeout(500);
}

// jump (no smooth scrolling) and wait until the page is really there
async function scrollExact(p, y) {
  await p.evaluate(yy => {
    document.documentElement.style.setProperty('scroll-behavior', 'auto', 'important');
    window.scrollTo({ top: yy, behavior: 'instant' });
  }, y);
  await p.waitForFunction(yy => Math.abs(window.scrollY - yy) < 1, y, { timeout: 5000 });
}

// hide position:fixed/sticky elements; keepHeader keeps the full-width bar at the top
async function hideFloating(p, keepHeader) {
  await p.addStyleTag({ content: '#qs-fab, #qs-cookie-overlay, #native-a11y-launcher, [id^="qs-"] { display: none !important; }' });
  await p.evaluate(keep => {
    document.querySelectorAll('#qs-fab, #qs-cookie-overlay, #native-a11y-launcher, [id^="qs-"], [class*="a11y-launcher"]')
      .forEach(e => e.style.setProperty('visibility', 'hidden', 'important'));
    document.querySelectorAll('body *').forEach(e => {
      const cs = getComputedStyle(e);
      if (cs.position !== 'fixed' && cs.position !== 'sticky') return;
      const r = e.getBoundingClientRect();
      const header = r.top <= 2 && r.width >= 380 && r.height < 160;
      if (!(keep && header)) e.style.setProperty('visibility', 'hidden', 'important');
    });
  }, keepHeader);
}

async function home(b) {
  const dir = path.join(WORK, 'site', 'enter');
  fs.mkdirSync(dir, { recursive: true });
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true,
    hasTouch: true, locale: 'he-IL' });
  const p = await ctx.newPage();
  await p.goto(HOME, { waitUntil: 'networkidle', timeout: 60000 });
  await p.waitForTimeout(2500);
  await acceptCookies(p);
  await scrollExact(p, 0);
  await p.waitForTimeout(1500);
  let n = 0;
  for (let y = 0; y <= 240; y += 8) {
    await scrollExact(p, y);
    await p.waitForTimeout(160);
    await hideFloating(p, true);
    await p.screenshot({ path: path.join(dir, `e${String(n++).padStart(2, '0')}.jpg`), type: 'jpeg', quality: 92 });
  }
  await ctx.close();
  return n;
}

async function openPanel(b) {
  const ctx = await b.newContext({ viewport: { width: 1280, height: 1000 }, deviceScaleFactor: 2, locale: 'he-IL' });
  const p = await ctx.newPage();
  await p.goto(PREVIEW, { waitUntil: 'networkidle', timeout: 60000 });
  await p.waitForTimeout(2000);
  await acceptCookies(p);
  await hideFloating(p, false);
  const k = await p.$('#klidim');
  await k.scrollIntoViewIfNeeded();
  await p.evaluate(() => window.scrollBy(0, -60));
  await p.waitForTimeout(600);
  return { ctx, p, k };
}

async function panelBoxes(p) {
  return p.evaluate(() => {
    const K = document.querySelector('#klidim').getBoundingClientRect();
    const rel = e => { const r = e.getBoundingClientRect(); return [r.left - K.left, r.top - K.top, r.width, r.height].map(Math.round); };
    const o = { panel: [0, 0, Math.round(K.width), Math.round(K.height)], rows: [], buttons: {} };
    document.querySelectorAll('#category-files button').forEach(e => o.rows.push({ text: e.textContent.trim(), box: rel(e) }));
    document.querySelectorAll('#klidim button.files, #break-btn').forEach(e => { o.buttons[e.getAttribute('aria-label')] = rel(e); });
    return o;
  });
}

async function organ(b) {
  const boxes = {};
  let { ctx, p, k } = await openPanel(b);
  await k.screenshot({ path: path.join(WORK, 'site', 'organ_0.jpg'), type: 'jpeg', quality: 90 });
  boxes.organ_0 = await panelBoxes(p);
  await p.click('#subfolder_0__0');
  await p.waitForTimeout(900);
  await k.screenshot({ path: path.join(WORK, 'site', 'organ_1.jpg'), type: 'jpeg', quality: 90 });
  boxes.organ_1 = await panelBoxes(p);
  await ctx.close();
  ({ ctx, p, k } = await openPanel(b));
  await p.click('#subfolder_0__1');
  await p.waitForTimeout(900);
  await k.screenshot({ path: path.join(WORK, 'site', 'organ_2.jpg'), type: 'jpeg', quality: 90 });
  boxes.organ_2 = await panelBoxes(p);
  await ctx.close();
  fs.writeFileSync(path.join(WORK, 'site', 'organ_boxes.json'), JSON.stringify(boxes, null, 1));
}

(async () => {
  const b = await chromium.launch();
  const n = await home(b);
  await organ(b);
  await b.close();
  console.log(`home frames: ${n}; organ states: 3`);
})().catch(e => { console.error(e); process.exit(1); });
