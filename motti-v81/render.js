'use strict';
// Canvas interpreter for scene.json (preview renderer). Mirrors After Effects semantics:
// parenting without opacity inheritance, per-layer motion blur (180 deg shutter),
// text animators with expression-selector style amounts.

const W = 1080, H = 1920;
let SCENE = null;
const IMG = {};          // src -> ImageBitmap
const BLURRED = {};      // cache key -> canvas
const PATHS = {};        // svg d -> Path2D
const LAYOUT = {};       // text layout cache
let FOOT = null, FOOT_F = -1, FOOT_BLUR = { key: '', canvas: null };
const FREEZE = {};       // precomp@time -> canvas
let GRID_CANVAS = null;

const C = document.getElementById('c');
const X = C.getContext('2d', { willReadFrequently: true });

// ------------------------------------------------------------------ easing
const EASE = {
  linear: p => p,
  outExpo: p => (p >= 1 ? 1 : 1 - Math.pow(2, -10 * p)),
  inExpo: p => (p <= 0 ? 0 : Math.pow(2, 10 * p - 10)),
  outCubic: p => 1 - Math.pow(1 - p, 3),
  inCubic: p => p * p * p,
  inOutCubic: p => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
  inOutSine: p => -(Math.cos(Math.PI * p) - 1) / 2,
  outQuad: p => 1 - (1 - p) * (1 - p),
  inQuad: p => p * p,
  outBack: p => { const s = 1.70158, c3 = s + 1; return 1 + c3 * Math.pow(p - 1, 3) + s * Math.pow(p - 1, 2); },
  outBack2: p => { const s = 2.4, c3 = s + 1; return 1 + c3 * Math.pow(p - 1, 3) + s * Math.pow(p - 1, 2); },
  outBack14: p => { const s = 1.4, c3 = s + 1; return 1 + c3 * Math.pow(p - 1, 3) + s * Math.pow(p - 1, 2); },
};
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

// ------------------------------------------------------------------ tracks
function ev(tr, t) {
  if (tr === null || tr === undefined) return tr;
  if (typeof tr !== 'object' || Array.isArray(tr)) return tr;
  const k = tr.k;
  if (t <= k[0][0]) return k[0][1];
  const last = k[k.length - 1];
  if (t >= last[0]) return last[1];
  let lo = 0, hi = k.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (k[m][0] <= t + 1e-9) lo = m; else hi = m; }
  if (tr.h) return k[lo][1];
  const t0 = k[lo][0], v0 = k[lo][1], t1 = k[hi][0], v1 = k[hi][1];
  const p = (t - t0) / (t1 - t0);
  if (Array.isArray(v0)) return v0.map((a, i) => a + (v1[i] - a) * p);
  if (typeof v0 === 'string') return v0;
  return v0 + (v1 - v0) * p;
}
function holdText(src, t) {
  let s = src[0][1];
  for (const [kt, v] of src) { if (kt <= t + 1e-9) s = v; else break; }
  return s;
}

// ------------------------------------------------------------------ loading
async function loadBitmap(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error('load ' + url);
  return await createImageBitmap(await r.blob());
}

async function init(scenePath, assetRoot) {
  SCENE = await (await fetch(scenePath)).json();
  window.ASSET = assetRoot;
  const faces = [
    ['hebrew', 300, 'U+0307-0308,U+0590-05FF,U+200C-2010,U+20AA,U+25CC,U+FB1D-FB4F'],
    ['hebrew', 900, 'U+0307-0308,U+0590-05FF,U+200C-2010,U+20AA,U+25CC,U+FB1D-FB4F'],
    ['latin', 300, 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD'],
    ['latin', 900, 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD'],
  ];
  for (const [sub, w, range] of faces) {
    const ff = new FontFace('NotoHeb', `url(${assetRoot}/fonts/noto-sans-hebrew-${sub}-${w}-normal.woff2)`,
      { weight: String(w), unicodeRange: range });
    document.fonts.add(ff);
    await ff.load();
  }
  const srcs = new Set();
  const walk = comp => {
    for (const L of comp.layers) {
      if (L.type === 'image') srcs.add(L.src);
      if (L.type === 'seq') L.srcs.forEach(s => srcs.add(s));
    }
  };
  Object.values(SCENE.comps).forEach(walk);
  for (const s of srcs) IMG[s] = await loadBitmap(`${assetRoot}/${s}`);
  for (const comp of Object.values(SCENE.comps)) {
    comp.byName = {};
    comp.layers.forEach(L => (comp.byName[L.name] = L));
  }
  return { comps: Object.keys(SCENE.comps), images: srcs.size };
}

async function loadFootage(f) {
  const n = clamp(f, 0, 246) + 1;
  if (n === FOOT_F) return;
  FOOT = await loadBitmap(`${window.ASSET}/frames/f${String(n).padStart(3, '0')}.jpg`);
  FOOT_F = n;
}

// ------------------------------------------------------------------ helpers
function blurredCanvas(src, w, h, sigma, key) {
  if (sigma < 0.3) return src;
  if (BLURRED[key]) return BLURRED[key];
  const c = new OffscreenCanvas(w, h);
  const x = c.getContext('2d');
  const pad = sigma * 3;
  x.filter = `blur(${sigma}px)`;
  x.drawImage(src, -pad, -pad, w + 2 * pad, h + 2 * pad);
  BLURRED[key] = c;
  return c;
}

function path2d(d) {
  if (!PATHS[d]) PATHS[d] = new Path2D(d);
  return PATHS[d];
}

function hexA(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

const BLEND = { normal: 'source-over', multiply: 'multiply', screen: 'screen', add: 'lighter' };

function layerTime(L, t, tf) { return L.mb ? t : tf; }

function matrixOf(comp, L, t, tf) {
  let M = new DOMMatrix();
  if (L.parent) {
    const P = comp.byName[L.parent];
    M = matrixOf(comp, P, t, tf);
  }
  const tt = layerTime(L, t, tf);
  let p = ev(L.pos, tt) || [0, 0];
  if (L.xoff) { const o = ev(L.xoff, tf); p = [p[0] + o[0], p[1] + o[1]]; }
  const s = ev(L.scale, tt) || [100, 100];
  const r = ev(L.rot, tt) || 0;
  const a = L.anchor || [0, 0];
  return M.translate(p[0], p[1]).rotate(r).scale(s[0] / 100, s[1] / 100).translate(-a[0], -a[1]);
}

function parentMatrix(comp, L, t, tf) {
  return L.parent ? matrixOf(comp, comp.byName[L.parent], t, tf) : new DOMMatrix();
}

function setShadow(ctx, fx, alphaMul) {
  ctx.shadowColor = 'rgba(0,0,0,0)';
  ctx.shadowBlur = 0; ctx.shadowOffsetX = 0; ctx.shadowOffsetY = 0;
  if (!fx) return;
  for (const e of fx) {
    if (e.type === 'shadow') {
      const ang = (e.dir - 90) * Math.PI / 180;   // AE: 180 = straight down
      ctx.shadowColor = hexA(e.color, (e.op / 100) * alphaMul);
      ctx.shadowBlur = e.soft;
      ctx.shadowOffsetX = Math.cos(ang) * e.dist;
      ctx.shadowOffsetY = Math.sin(ang) * e.dist;
    } else if (e.type === 'glow') {
      ctx.shadowColor = hexA(e.color, (e.op / 100) * alphaMul);
      ctx.shadowBlur = e.soft;
    }
  }
}

// ------------------------------------------------------------------ text
function fontOf(L) {
  const f = SCENE.fonts[L.font];
  return `${f.weight} ${L.size}px ${f.family}`;
}

function layoutText(ctx, L, str) {
  const key = L.font + '|' + L.size + '|' + L.dir + '|' + L.just + '|' + str;
  if (LAYOUT[key]) return LAYOUT[key];
  ctx.font = fontOf(L);
  ctx.direction = L.dir;
  const total = ctx.measureText(str).width;
  let left;
  if (L.just === 'center') left = -total / 2;
  else if (L.just === 'right') left = -total;
  else left = 0;
  const right = left + total;
  const chars = [];
  let word = 0;
  for (let i = 0; i < str.length; i++) {
    const a = ctx.measureText(str.slice(0, i)).width;
    const b = ctx.measureText(str.slice(0, i + 1)).width;
    let x0, x1;
    if (L.dir === 'rtl') { x1 = right - a; x0 = right - b; } else { x0 = left + a; x1 = left + b; }
    if (str[i] === ' ') word++;
    chars.push({ ch: str[i], x0, x1, cx: (x0 + x1) / 2, word: str[i] === ' ' ? word - 1 : word });
  }
  const res = { total, left, right, chars };
  LAYOUT[key] = res;
  return res;
}

function selAmount(sel, i, n, t, wordIdx) {
  let k = sel.by === 'word' ? wordIdx : i;
  if (sel.order === 'rev') k = n - 1 - k;
  const st = sel.t0 + k * sel.stag;
  if (sel.step) return t < st - 1e-9 ? 1 : 0;
  const p = sel.dur > 0 ? clamp((t - st) / sel.dur, 0, 1) : (t >= st ? 1 : 0);
  const e = EASE[sel.ease](p);
  return sel.mode === 'in' ? 1 - e : e;
}

function drawTextGlyphs(ctx, L, str, lay, tt, alpha, fillOverride) {
  ctx.font = fontOf(L);
  ctx.direction = L.dir;
  ctx.textBaseline = 'alphabetic';
  const fill = fillOverride !== undefined ? fillOverride : L.fill;
  const doDraw = (s, x, align) => {
    ctx.textAlign = align;
    if (L.stroke && L.sw > 0) {
      ctx.lineWidth = L.sw; ctx.lineJoin = 'round'; ctx.strokeStyle = L.stroke;
      ctx.strokeText(s, x, 0);
    }
    if (fill) { ctx.fillStyle = fill; ctx.fillText(s, x, 0); }
  };
  if (!L.anims || !L.anims.length) {
    ctx.globalAlpha = alpha;
    doDraw(str, 0, L.just);
    return;
  }
  const n = lay.chars.length;
  for (let i = 0; i < n; i++) {
    const c = lay.chars[i];
    if (c.ch === ' ') continue;
    let dx = 0, dy = 0, sx = 100, sy = 100, op = 100, rot = 0;
    for (const A of L.anims) {
      const a = selAmount(A.sel, i, n, tt, c.word);
      const P = A.props;
      if (P.pos) { dx += P.pos[0] * a; dy += P.pos[1] * a; }
      if (P.scale) { sx *= (100 + a * (P.scale[0] - 100)) / 100; sy *= (100 + a * (P.scale[1] - 100)) / 100; }
      if (P.op !== undefined) op *= (100 + a * (P.op - 100)) / 100;
      if (P.rot) rot += P.rot * a;
    }
    op = clamp(op, 0, 100);
    if (op <= 0.05) continue;
    ctx.save();
    ctx.translate(c.cx + dx, dy);
    if (rot) ctx.rotate(rot * Math.PI / 180);
    ctx.scale(sx / 100 || 0.0001, sy / 100 || 0.0001);
    ctx.globalAlpha = alpha * op / 100;
    doDraw(c.ch, L.dir === 'rtl' ? (c.x1 - c.cx) : (c.x0 - c.cx), L.dir === 'rtl' ? 'right' : 'left');
    ctx.restore();
  }
}

function drawText(ctx, L, tt, tf, alpha) {
  const str = L.src ? holdText(L.src, tf) : L.text;
  const lay = layoutText(ctx, L, str);
  setShadow(ctx, L.fx, 1);
  drawTextGlyphs(ctx, L, str, lay, tt, alpha);
  setShadow(ctx, null, 1);
  if (L.light_sweep) {
    const s = L.light_sweep;
    if (tt >= s.t0 && tt <= s.t1) {
      const p = EASE.inOutSine((tt - s.t0) / (s.t1 - s.t0));
      const bx = s.x0 + (s.x1 - s.x0) * p - 540;
      const g = ctx.createLinearGradient(bx - s.width, -60, bx + s.width, 60);
      g.addColorStop(0, 'rgba(190,225,255,0)');
      g.addColorStop(0.5, 'rgba(235,246,255,0.95)');
      g.addColorStop(1, 'rgba(190,225,255,0)');
      ctx.save();
      ctx.globalCompositeOperation = 'source-over';
      drawTextGlyphs(ctx, L, str, lay, tt, alpha, g);
      ctx.restore();
    }
  }
}

// ------------------------------------------------------------------ shapes
function drawShape(ctx, L, tt, alpha) {
  setShadow(ctx, L.fx, 1);
  ctx.globalAlpha = alpha;
  let blurAmt = 0;
  for (const e of (L.fx || [])) if (e.type === 'blur') blurAmt = ev(e.amt, tt);
  if (blurAmt > 0.3) ctx.filter = `blur(${blurAmt}px)`;
  for (const it of L.items) {
    const c = it.c || [0, 0];
    let p = null;
    if (it.kind === 'rect') {
      const sz = ev(it.size, tt);
      p = new Path2D();
      const r = Math.min(it.r || 0, sz[0] / 2, sz[1] / 2);
      if (r > 0) p.roundRect(c[0] - sz[0] / 2, c[1] - sz[1] / 2, sz[0], sz[1], r);
      else p.rect(c[0] - sz[0] / 2, c[1] - sz[1] / 2, sz[0], sz[1]);
    } else if (it.kind === 'ellipse') {
      const sz = ev(it.size, tt);
      p = new Path2D();
      p.ellipse(c[0], c[1], Math.max(0.01, sz[0] / 2), Math.max(0.01, sz[1] / 2), 0, 0, Math.PI * 2);
    } else if (it.kind === 'path') {
      p = path2d(it.d);
    } else if (it.kind === 'glow') {
      const sz = it.size;
      ctx.save();
      ctx.translate(c[0], c[1]);
      ctx.scale(sz[0] / 2, sz[1] / 2);
      const g = ctx.createRadialGradient(0, 0, 0, 0, 0, 1);
      g.addColorStop(0, hexA(it.fill, 1));
      g.addColorStop(0.35, hexA(it.fill, 0.75));
      g.addColorStop(0.7, hexA(it.fill, 0.22));
      g.addColorStop(1, hexA(it.fill, 0));
      ctx.fillStyle = g;
      ctx.fillRect(-1, -1, 2, 2);
      ctx.restore();
      continue;
    }
    if (it.fill) { ctx.fillStyle = it.fill; ctx.fill(p, it.evenodd ? 'evenodd' : 'nonzero'); }
    if (it.stroke) {
      const sw = ev(it.sw, tt);
      if (sw > 0) {
        ctx.lineWidth = sw; ctx.strokeStyle = it.stroke;
        ctx.lineCap = it.cap || 'round'; ctx.lineJoin = it.join || 'round';
        ctx.stroke(p);
      }
    }
  }
  ctx.filter = 'none';
  setShadow(ctx, null, 1);
}

// ------------------------------------------------------------------ layers
function applyMasks(ctx, L, tt) {
  if (!L.masks) return;
  const p = new Path2D();
  let any = false;
  for (const m of L.masks) {
    if (m.rect) {
      const [x0, y0, x1, y1] = m.rect;
      if (m.r) p.roundRect(x0, y0, x1 - x0, y1 - y0, m.r); else p.rect(x0, y0, x1 - x0, y1 - y0);
      any = true;
    }
  }
  if (any) ctx.clip(p);
}

function drawLayer(ctx, comp, L, t, tf) {
  if (tf < L.in - 1e-6 || tf >= L.out - 1e-6) return;
  if (L.type === 'null') return;
  const tt = layerTime(L, t, tf);
  // AE motion blur samples transforms across the shutter, not opacity
  const alpha = clamp((ev(L.op, tf) ?? 100) / 100, 0, 1);
  if (alpha <= 0.002) return;
  ctx.save();
  ctx.globalCompositeOperation = BLEND[L.blend || 'normal'];
  if (L.clip) {
    ctx.setTransform(parentMatrix(comp, L, t, tf));
    const [x0, y0, x1, y1] = L.clip;
    ctx.beginPath(); ctx.rect(x0, y0, x1 - x0, y1 - y0); ctx.clip();
  }
  const M = matrixOf(comp, L, t, tf);
  ctx.setTransform(M);
  const ellipseMask = L.masks && L.masks.find(m => m.ellipse);
  if (!ellipseMask) applyMasks(ctx, L, tt);
  ctx.globalAlpha = alpha;
  switch (L.type) {
    case 'solid':
      ctx.fillStyle = L.color; ctx.fillRect(0, 0, L.w, L.h); break;
    case 'footage': {
      let amt = 0;
      for (const e of (L.fx || [])) if (e.type === 'blur') amt = ev(e.amt, tf);
      const key = FOOT_F + '|' + amt.toFixed(2);
      if (FOOT_BLUR.key !== key) {
        FOOT_BLUR.key = key;
        FOOT_BLUR.canvas = amt > 0.3 ? (() => {
          const c = new OffscreenCanvas(W, H); const x = c.getContext('2d');
          const pad = amt * 3; x.filter = `blur(${amt}px)`;
          x.drawImage(FOOT, -pad, -pad, W + 2 * pad, H + 2 * pad); return c;
        })() : FOOT;
      }
      ctx.drawImage(FOOT_BLUR.canvas, 0, 0, W, H);
      break;
    }
    case 'image': {
      let amt = 0;
      for (const e of (L.fx || [])) if (e.type === 'blur') amt = ev(e.amt, tf);
      const src = amt > 0.3 ? blurredCanvas(IMG[L.src], L.w, L.h, amt, L.src + '|' + amt) : IMG[L.src];
      setShadow(ctx, (L.fx || []).filter(e => e.type === 'shadow'), 1);
      ctx.drawImage(src, 0, 0, L.w, L.h);
      setShadow(ctx, null, 1);
      break;
    }
    case 'seq': {
      const i = clamp(Math.round(ev(L.idx, tf)), 0, L.srcs.length - 1);
      ctx.drawImage(IMG[L.srcs[i]], 0, 0, L.w, L.h);
      break;
    }
    case 'text':
      drawText(ctx, L, tt, tf, alpha); break;
    case 'shape':
      if (ellipseMask) drawEllipseMasked(ctx, L, tt, alpha, ellipseMask, M);
      else drawShape(ctx, L, tt, alpha);
      break;
    case 'precomp': {
      const sub = SCENE.comps[L.comp];
      if (L.tm !== null && L.tm !== undefined) {
        const tau = ev(L.tm, tf);
        const key = L.comp + '@' + tau.toFixed(4);
        if (!FREEZE[key]) throw new Error('freeze not prepared ' + key);
        const fc = FREEZE[key];
        if (L.masks && L.masks.length === 1 && L.masks[0].rect) {
          const [x0, y0, x1, y1] = L.masks[0].rect;
          const sx = Math.max(0, x0), sy = Math.max(0, y0), ex = Math.min(W, x1), ey = Math.min(H, y1);
          if (ex > sx && ey > sy) ctx.drawImage(fc, sx, sy, ex - sx, ey - sy, sx, sy, ex - sx, ey - sy);
        } else ctx.drawImage(fc, 0, 0);
      } else {
        renderComp(ctx, sub, t, tf);
      }
      break;
    }
  }
  ctx.restore();
}

function drawEllipseMasked(ctx, L, tt, alpha, m, M) {
  if (!GRID_CANVAS) {
    GRID_CANVAS = new OffscreenCanvas(W, H);
    const g = GRID_CANVAS.getContext('2d');
    drawShape(g, L, tt, 1);
  }
  const sz = ev(m.size, tt);
  ctx.setTransform(new DOMMatrix());
  if (sz[0] >= 2599) { ctx.globalAlpha = alpha; ctx.drawImage(GRID_CANVAS, 0, 0); return; }
  const tmp = new OffscreenCanvas(W, H);
  const x = tmp.getContext('2d');
  x.drawImage(GRID_CANVAS, 0, 0);
  x.globalCompositeOperation = 'destination-in';
  const r = Math.max(1, sz[0] / 2);
  const f = m.feather || 0;
  const g = x.createRadialGradient(m.ellipse[0], m.ellipse[1], Math.max(0, r - f), m.ellipse[0], m.ellipse[1], r + 1);
  g.addColorStop(0, 'rgba(0,0,0,1)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  x.fillStyle = g;
  x.fillRect(0, 0, W, H);
  ctx.globalAlpha = alpha;
  ctx.drawImage(tmp, 0, 0);
}

function renderComp(ctx, comp, t, tf) {
  for (const L of comp.layers) drawLayer(ctx, comp, L, t, tf);
}

function prepareFreezes(tf) {
  const main = SCENE.comps[SCENE.main];
  for (const L of main.layers) {
    if (L.type !== 'precomp' || L.tm === null || L.tm === undefined) continue;
    if (tf < L.in - 1e-6 || tf >= L.out - 1e-6) continue;
    const tau = ev(L.tm, tf);
    const key = L.comp + '@' + tau.toFixed(4);
    if (FREEZE[key]) continue;
    return { key, comp: L.comp, tau };
  }
  return null;
}

// ------------------------------------------------------------------ frame
const ACC = new Float32Array(W * H * 4);
const NSUB = 5;

async function renderFrame(f, opts) {
  opts = opts || {};
  const fps = SCENE.fps;
  const tf = f / fps;
  // freeze frames needed by time-remapped precomps
  for (;;) {
    const need = prepareFreezes(tf);
    if (!need) break;
    const fz = Math.round(need.tau * fps);
    await loadFootage(fz);
    const c = new OffscreenCanvas(W, H);
    const x = c.getContext('2d');
    x.fillStyle = '#000'; x.fillRect(0, 0, W, H);
    renderComp(x, SCENE.comps[need.comp], need.tau, need.tau);
    FREEZE[need.key] = c;
  }
  await loadFootage(f);
  const main = SCENE.comps[SCENE.main];
  const nsub = opts.nomb ? 1 : NSUB;
  if (nsub === 1) {
    X.setTransform(1, 0, 0, 1, 0, 0);
    X.fillStyle = '#000'; X.fillRect(0, 0, W, H);
    renderComp(X, main, tf, tf);
  } else {
    ACC.fill(0);
    const shutter = 0.5 / fps;
    for (let k = 0; k < nsub; k++) {
      const t = tf + (k / (nsub - 1) - 0.5) * shutter;
      X.setTransform(1, 0, 0, 1, 0, 0);
      X.globalAlpha = 1; X.globalCompositeOperation = 'source-over';
      X.fillStyle = '#000'; X.fillRect(0, 0, W, H);
      renderComp(X, main, t, tf);
      const d = X.getImageData(0, 0, W, H).data;
      for (let i = 0; i < d.length; i++) ACC[i] += d[i];
    }
    const out = X.createImageData(W, H);
    const od = out.data;
    for (let i = 0; i < od.length; i++) od[i] = ACC[i] / nsub + 0.5;
    X.setTransform(1, 0, 0, 1, 0, 0);
    X.putImageData(out, 0, 0);
  }
  if (opts.noreturn) return null;
  return C.toDataURL('image/png');
}

window.init = init;
window.renderFrame = renderFrame;
