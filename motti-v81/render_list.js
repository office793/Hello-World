// usage: node render_list.js <baseUrl> <outDir> <f1,f2,...> [mb]
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [,, base, outDir, list, mb] = process.argv;
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ args: ['--disable-gpu'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('console', m => console.log('[page]', m.text()));
  page.on('pageerror', e => console.error('[pageerror]', e.message));
  await page.goto(`${base}/build/render.html`);
  console.log('init', JSON.stringify(await page.evaluate(async () => await window.init('out/scene.json', '../work'))));
  for (const f of list.split(',').map(Number)) {
    const t0 = Date.now();
    const url = await page.evaluate(async ([f, nomb]) => await window.renderFrame(f, { nomb }), [f, !mb]);
    fs.writeFileSync(`${outDir}/f${String(f).padStart(4, '0')}.png`, Buffer.from(url.split(',')[1], 'base64'));
    console.log('frame', f, Date.now() - t0, 'ms');
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
