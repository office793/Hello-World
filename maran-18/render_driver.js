// Drives render.html in headless Chromium and writes PNG frames.
// usage: node render_driver.js <baseUrl> <outDir> <from> <to> [nomb] [list=f1,f2,...]
// Layout served at <baseUrl>: app/ (this folder), work/ (assets), out/scene.json.
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [,, base, outDir, from, to, ...rest] = process.argv;
  const nomb = rest.includes('nomb');
  const listArg = rest.find(a => a.startsWith('list='));
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ args: ['--disable-gpu'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('console', m => console.log('[page]', m.text()));
  page.on('pageerror', e => { console.error('[pageerror]', e.message); });
  await page.goto(`${base}/app/render.html`);
  const info = await page.evaluate(async () => await window.init('../out/scene.json', '../work'));
  console.log('init', JSON.stringify(info));
  const frames = listArg ? listArg.slice(5).split(',').map(Number) : [];
  if (!frames.length) for (let f = +from; f <= +to; f++) frames.push(f);
  const t0 = Date.now();
  for (let i = 0; i < frames.length; i++) {
    const f = frames[i];
    const url = await page.evaluate(async ([f, nomb]) => await window.renderFrame(f, { nomb }), [f, nomb]);
    fs.writeFileSync(`${outDir}/f${String(f).padStart(4, '0')}.png`, Buffer.from(url.split(',')[1], 'base64'));
    if (i % 30 === 0) console.log('frame', f, ((Date.now() - t0) / (i + 1)).toFixed(0), 'ms/frame');
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
