'use strict';
// Canvas interpreter for scene.json (preview renderer). Mirrors After Effects semantics:
// parenting without opacity inheritance, per-layer motion blur (180 deg shutter), text animators
// with expression-selector style amounts, Trim Paths, gradient (ramp + alpha matte) text fills and
// alpha track mattes.

const W = 1080, H = 1920;
let SCENE = null;
const IMG = {};          // src -> ImageBitmap
const BLURRED = {};      // cache key -> canvas
const PATHS = {};        // svg d -> Path2D
const LAYOUT = {};       // text layout cache

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
  outQuart: p => 1 - Math.pow(1 - p, 4),
  outBack: p => { const s = 1.70158, c3 = s + 1; return 1 + c3 * Math.pow(p - 1, 3) + s * Math.pow(p - 1, 2); },
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
  return v0 + (v1 - v0) * p;
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
  for (const f of Object.values(SCENE.fonts)) {
    const ff = new FontFace(f.family, `url(${assetRoot}/fonts/${f.file})`);
    document.fonts.add(ff);
    await ff.load();
  }
  const srcs = new Set();
  for (const comp of Object.values(SCENE.comps)) {
    comp.byName = {};
    for (const L of comp.layers) {
      comp.byName[L.name] = L;
      if (L.type === 'image') srcs.add(L.src);
    }
  }
  for (const s of srcs) IMG[s] = await loadBitmap(`${assetRoot}/${s}`);
  return { comps: Object.keys(SCENE.comps), images: srcs.size };
}

// ------------------------------------------------------------------ helpers
function blurredCanvas(src, w, h, sigma, key) {
  if (sigma < 0.3) return src;
  if (BLURRED[key]) return BLURRED[key];
  const pad = Math.ceil(sigma * 3);
  const c = new OffscreenCanvas(w + 2 * pad, h + 2 * pad);
  const x = c.getContext('2d');
  x.filter = `blur(${sigma}px)`;
  x.drawImage(src, pad, pad, w, h);
  BLURRED[key] = { canvas: c, pad };
  return BLURRED[key];
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
  if (L.parent) M = matrixOf(comp, comp.byName[L.parent], t, tf);
  const tt = layerTime(L, t, tf);
  const p = ev(L.pos, tt) || [0, 0];
  const s = ev(L.scale, tt) || [100, 100];
  const r = ev(L.rot, tt) || 0;
  const a = L.anchor || [0, 0];
  return M.translate(p[0], p[1]).rotate(r).scale(s[0] / 100, s[1] / 100).translate(-a[0], -a[1]);
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
    }
  }
}

function layerBlur(L, t) {
  let amt = 0;
  for (const e of (L.fx || [])) if (e.type === 'blur') amt = ev(e.amt, t);
  return amt || 0;
}

// ------------------------------------------------------------------ text
function fontOf(L) {
  const f = SCENE.fonts[L.font];
  return `${L.size}px "${f.family}"`;
}

function layoutText(ctx, L, str) {
  const key = L.font + '|' + L.size + '|' + L.dir + '|' + L.just + '|' + (L.track || 0) + '|' + str;
  if (LAYOUT[key]) return LAYOUT[key];
  ctx.font = fontOf(L);
  ctx.direction = L.dir;
  ctx.letterSpacing = `${(L.track || 0) * L.size / 1000}px`;
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
  ctx.letterSpacing = '0px';
  return res;
}

function selAmount(sel, i, n, t, wordIdx, nWords) {
  let k = sel.by === 'word' ? wordIdx : i;
  const kn = sel.by === 'word' ? nWords : n;
  if (sel.order === 'rev') k = kn - 1 - k;
  const st = sel.starts ? sel.starts[Math.min(k, sel.starts.length - 1)] : sel.t0 + k * sel.stag;
  const p = sel.dur > 0 ? clamp((t - st) / sel.dur, 0, 1) : (t >= st ? 1 : 0);
  const e = EASE[sel.ease](p);
  return sel.mode === 'in' ? 1 - e : e;
}

function textFill(ctx, L, dy, fillOverride) {
  if (fillOverride !== undefined) return fillOverride;
  if (L.grad) {
    // AE: a ramp solid parented to the text layer, shown through the text's alpha. It does not
    // follow the per-character animator offsets, so the gradient is anchored in layer space.
    const g = ctx.createLinearGradient(0, L.grad.y0 - dy, 0, L.grad.y1 - dy);
    g.addColorStop(0, L.grad.c0);
    g.addColorStop(1, L.grad.c1);
    return g;
  }
  return L.fill;
}

function drawTextGlyphs(ctx, L, str, lay, tt, alpha, fillOverride, baseBlur) {
  baseBlur = baseBlur || 0;
  ctx.font = fontOf(L);
  ctx.direction = L.dir;
  ctx.textBaseline = 'alphabetic';
  const doDraw = (s, x, align, fill) => {
    ctx.textAlign = align;
    if (L.stroke && L.sw > 0) {
      ctx.lineWidth = L.sw; ctx.lineJoin = 'round'; ctx.strokeStyle = L.stroke;
      ctx.strokeText(s, x, 0);
    }
    if (fill) { ctx.fillStyle = fill; ctx.fillText(s, x, 0); }
  };
  const nWords = lay.chars.length ? lay.chars[lay.chars.length - 1].word + 1 : 0;
  if (!L.anims || !L.anims.length) {
    ctx.globalAlpha = alpha;
    ctx.filter = baseBlur > 0.3 ? `blur(${baseBlur.toFixed(2)}px)` : 'none';
    ctx.letterSpacing = `${(L.track || 0) * L.size / 1000}px`;
    doDraw(str, 0, L.just === 'center' ? 'center' : L.just, textFill(ctx, L, 0, fillOverride));
    ctx.letterSpacing = '0px';
    ctx.filter = 'none';
    return;
  }
  const n = lay.chars.length;
  for (let i = 0; i < n; i++) {
    const c = lay.chars[i];
    if (c.ch === ' ') continue;
    let dx = 0, dy = 0, sx = 100, sy = 100, op = 100, rot = 0, blur = 0;
    for (const A of L.anims) {
      const a = selAmount(A.sel, i, n, tt, c.word, nWords);
      const P = A.props;
      if (P.pos) { dx += P.pos[0] * a; dy += P.pos[1] * a; }
      if (P.scale) { sx *= (100 + a * (P.scale[0] - 100)) / 100; sy *= (100 + a * (P.scale[1] - 100)) / 100; }
      if (P.op !== undefined) op *= (100 + a * (P.op - 100)) / 100;
      if (P.rot) rot += P.rot * a;
      if (P.blur) blur += P.blur * a;
    }
    op = clamp(op, 0, 100);
    if (op <= 0.05) continue;
    ctx.save();
    ctx.translate(c.cx + dx, dy);
    if (rot) ctx.rotate(rot * Math.PI / 180);
    ctx.scale(sx / 100 || 0.0001, sy / 100 || 0.0001);
    ctx.globalAlpha = alpha * op / 100;
    const tb = Math.sqrt(blur * blur + baseBlur * baseBlur);
    ctx.filter = tb > 0.3 ? `blur(${tb.toFixed(2)}px)` : 'none';
    doDraw(c.ch, L.dir === 'rtl' ? (c.x1 - c.cx) : (c.x0 - c.cx), L.dir === 'rtl' ? 'right' : 'left',
      textFill(ctx, L, dy, fillOverride));
    ctx.filter = 'none';
    ctx.restore();
  }
}

function drawText(ctx, L, tt, tf, alpha) {
  const str = L.text;
  const lay = layoutText(ctx, L, str);
  const blur = layerBlur(L, tf);
  setShadow(ctx, L.fx, 1);
  drawTextGlyphs(ctx, L, str, lay, tt, alpha, undefined, blur);
  setShadow(ctx, null, 1);
  if (L.light_sweep) {
    const s = L.light_sweep;
    if (tt >= s.t0 && tt <= s.t1) {
      // CC Light Sweep: a soft bright band crossing the letters
      const p = EASE.inOutSine((tt - s.t0) / (s.t1 - s.t0));
      const bx = s.x0 + (s.x1 - s.x0) * p;
      const yc = -L.size * 0.35;
      const ang = 25 * Math.PI / 180;
      const dx = Math.cos(ang) * s.width, dy = Math.sin(ang) * s.width;
      const g = ctx.createLinearGradient(bx - dx, yc - dy, bx + dx, yc + dy);
      g.addColorStop(0, 'rgba(255,244,214,0)');
      g.addColorStop(0.5, `rgba(255,248,226,${s.op || 0.9})`);
      g.addColorStop(1, 'rgba(255,244,214,0)');
      ctx.save();
      drawTextGlyphs(ctx, L, str, lay, tt, alpha, g, blur);
      ctx.restore();
    }
  }
  ctx.filter = 'none';
}

// ------------------------------------------------------------------ shapes
function drawShape(ctx, L, tt, alpha) {
  setShadow(ctx, L.fx, 1);
  ctx.globalAlpha = alpha;
  const blurAmt = layerBlur(L, tt);
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
    const iop = it.op !== undefined ? clamp(ev(it.op, tt), 0, 100) / 100 : 1;
    if (iop <= 0.002) continue;
    ctx.globalAlpha = alpha * iop;
    if (it.fill) { ctx.fillStyle = it.fill; ctx.fill(p, it.evenodd ? 'evenodd' : 'nonzero'); }
    if (it.stroke) {
      const sw = ev(it.sw, tt);
      let s = 0, e = 100;
      if (it.trim) { s = ev(it.trim.s, tt); e = ev(it.trim.e, tt); }
      if (sw > 0 && e - s > 0.05) {
        ctx.lineWidth = sw; ctx.strokeStyle = it.stroke;
        ctx.lineCap = it.cap || 'round'; ctx.lineJoin = it.join || 'round';
        if (it.trim && (s > 0.01 || e < 99.99)) {
          const len = it.len;
          ctx.setLineDash([(e - s) / 100 * len, len * 2 + 10]);
          ctx.lineDashOffset = -s / 100 * len;
        }
        ctx.stroke(p);
        ctx.setLineDash([]);
        ctx.lineDashOffset = 0;
      }
    }
  }
  ctx.globalAlpha = alpha;
  ctx.filter = 'none';
  setShadow(ctx, null, 1);
}

// ------------------------------------------------------------------ layers
function drawLayerContent(ctx, comp, L, t, tf, alpha) {
  const tt = layerTime(L, t, tf);
  ctx.globalAlpha = alpha;
  switch (L.type) {
    case 'solid':
      ctx.fillStyle = L.color; ctx.fillRect(0, 0, L.w, L.h); break;
    case 'image': {
      const amt = layerBlur(L, tf);
      if (amt > 0.3) {
        const b = blurredCanvas(IMG[L.src], L.w, L.h, amt, L.src + '|' + amt.toFixed(2));
        ctx.drawImage(b.canvas, -b.pad, -b.pad);
      } else {
        ctx.drawImage(IMG[L.src], 0, 0, L.w, L.h);
      }
      break;
    }
    case 'text':
      drawText(ctx, L, tt, tf, alpha); break;
    case 'shape':
      drawShape(ctx, L, tt, alpha); break;
  }
}

function drawLayer(ctx, comp, L, t, tf) {
  if (tf < L.in - 1e-6 || tf >= L.out - 1e-6) return;
  if (L.type === 'null' || L.hidden_matte) return;
  const alpha = clamp((ev(L.op, tf) ?? 100) / 100, 0, 1);
  if (alpha <= 0.002) return;
  if (L.matte) {
    // alpha track matte: render layer and matte separately, keep the layer where the matte is opaque
    const M = comp.byName[L.matte];
    const a = new OffscreenCanvas(W, H), ax = a.getContext('2d');
    ax.setTransform(matrixOf(comp, L, t, tf));
    drawLayerContent(ax, comp, L, t, tf, alpha);
    const m = new OffscreenCanvas(W, H), mx = m.getContext('2d');
    const malpha = clamp((ev(M.op, tf) ?? 100) / 100, 0, 1);
    mx.setTransform(matrixOf(comp, M, t, tf));
    drawLayerContent(mx, comp, M, t, tf, malpha);
    ax.setTransform(1, 0, 0, 1, 0, 0);
    ax.globalAlpha = 1;
    ax.globalCompositeOperation = 'destination-in';
    ax.drawImage(m, 0, 0);
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalCompositeOperation = BLEND[L.blend || 'normal'];
    ctx.drawImage(a, 0, 0);
    ctx.restore();
    return;
  }
  ctx.save();
  ctx.globalCompositeOperation = BLEND[L.blend || 'normal'];
  ctx.setTransform(matrixOf(comp, L, t, tf));
  drawLayerContent(ctx, comp, L, t, tf, alpha);
  ctx.restore();
}

function renderComp(ctx, comp, t, tf) {
  for (const L of comp.layers) drawLayer(ctx, comp, L, t, tf);
}

// ------------------------------------------------------------------ frame
const ACC = new Float32Array(W * H * 4);
const NSUB = 5;

async function renderFrame(f, opts) {
  opts = opts || {};
  const fps = SCENE.fps;
  const tf = f / fps;
  const main = SCENE.comps[SCENE.main];
  const nsub = opts.nomb ? 1 : NSUB;
  if (nsub === 1) {
    X.setTransform(1, 0, 0, 1, 0, 0);
    X.globalAlpha = 1; X.globalCompositeOperation = 'source-over';
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
