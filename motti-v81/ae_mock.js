// Minimal After Effects scripting DOM mock: runs the generated .jsx outside AE and
// validates match names, value dimensions, timing and expressions.
// usage: node ae_mock.js <script.jsx> [--rtl]
'use strict';
const fs = require('fs');
const vm = require('vm');

const file = process.argv[2];
const RTL = process.argv.includes('--rtl');
const ERR = [], WARN = [];
const STATS = { layers: 0, keys: 0, expressions: 0, props: 0, comps: 0, masks: 0, effects: 0 };
function fail(m) { ERR.push(m); }

// ------------------------------------------------------------------ property specs
const NUM = { dims: 1 }, V2 = { dims: [2, 3] }, V3 = { dims: 3 }, COL = { dims: 4 }, SHAPE = { shape: true };
const LEAF = {
  'ADBE Anchor Point': V2, 'ADBE Position': V2, 'ADBE Scale': V2, 'ADBE Rotate Z': NUM, 'ADBE Opacity': NUM,
  'ADBE Time Remapping': NUM,
  'ADBE Text Document': { textdoc: true },
  'ADBE Text Expressible Amount': { dims: 3, exprOnly: true },
  'ADBE Text Position 3D': V3, 'ADBE Text Scale 3D': V3, 'ADBE Text Opacity': NUM, 'ADBE Text Rotation': NUM,
  'ADBE Vector Rect Size': { dims: 2 }, 'ADBE Vector Rect Position': { dims: 2 }, 'ADBE Vector Rect Roundness': NUM,
  'ADBE Vector Ellipse Size': { dims: 2 }, 'ADBE Vector Ellipse Position': { dims: 2 }, 'ADBE Vector Shape': SHAPE,
  'ADBE Vector Fill Color': COL, 'ADBE Vector Fill Rule': { dims: 1, range: [1, 2] }, 'ADBE Vector Fill Opacity': NUM,
  'ADBE Vector Stroke Color': COL, 'ADBE Vector Stroke Width': NUM, 'ADBE Vector Stroke Line Cap': { dims: 1, range: [1, 3] },
  'ADBE Vector Stroke Line Join': { dims: 1, range: [1, 3] },
  'ADBE Mask Shape': SHAPE, 'ADBE Mask Feather': { dims: 2 }, 'ADBE Mask Opacity': NUM, 'ADBE Mask Offset': NUM,
  'ADBE Gaussian Blur 2-0001': NUM, 'ADBE Gaussian Blur 2-0002': NUM, 'ADBE Gaussian Blur 2-0003': NUM,
  'ADBE Drop Shadow-0001': COL, 'ADBE Drop Shadow-0002': { dims: 1, max: 255 }, 'ADBE Drop Shadow-0003': NUM,
  'ADBE Drop Shadow-0004': NUM, 'ADBE Drop Shadow-0005': NUM, 'ADBE Drop Shadow-0006': NUM,
  'CCLS-1': { dims: 2 }, 'CCLS-2': NUM, 'CCLS-3': NUM, 'CCLS-4': NUM, 'CCLS-5': NUM,
};
const GROUPS = {
  'ADBE Transform Group': { fixed: ['ADBE Anchor Point', 'ADBE Position', 'ADBE Scale', 'ADBE Rotate Z', 'ADBE Opacity'] },
  'ADBE Effect Parade': { add: { 'ADBE Gaussian Blur 2': 1, 'ADBE Drop Shadow': 1, 'CC Light Sweep': 1 } },
  'ADBE Gaussian Blur 2': { fixed: ['ADBE Gaussian Blur 2-0001', 'ADBE Gaussian Blur 2-0002', 'ADBE Gaussian Blur 2-0003'] },
  'ADBE Drop Shadow': { fixed: ['ADBE Drop Shadow-0001', 'ADBE Drop Shadow-0002', 'ADBE Drop Shadow-0003', 'ADBE Drop Shadow-0004', 'ADBE Drop Shadow-0005', 'ADBE Drop Shadow-0006'] },
  'CC Light Sweep': { fixed: ['CCLS-1', 'CCLS-2', 'CCLS-3', 'CCLS-4', 'CCLS-5'] },
  'ADBE Mask Parade': { add: { 'ADBE Mask Atom': 1 } },
  'ADBE Mask Atom': { fixed: ['ADBE Mask Shape', 'ADBE Mask Feather', 'ADBE Mask Opacity', 'ADBE Mask Offset'], attrs: ['maskMode'] },
  'ADBE Text Properties': { fixed: ['ADBE Text Document', 'ADBE Text Animators'] },
  'ADBE Text Animators': { add: { 'ADBE Text Animator': 1 } },
  'ADBE Text Animator': { fixed: ['ADBE Text Selectors', 'ADBE Text Animator Properties'] },
  'ADBE Text Selectors': { add: { 'ADBE Text Expressible Selector': 1, 'ADBE Text Selector': 1 } },
  'ADBE Text Expressible Selector': { fixed: ['ADBE Text Expressible Amount'] },
  'ADBE Text Animator Properties': { add: { 'ADBE Text Position 3D': 1, 'ADBE Text Scale 3D': 1, 'ADBE Text Opacity': 1, 'ADBE Text Rotation': 1 } },
  'ADBE Root Vectors Group': { add: { 'ADBE Vector Group': 1 } },
  'ADBE Vector Group': { fixed: ['ADBE Vectors Group'] },
  'ADBE Vectors Group': { add: { 'ADBE Vector Shape - Rect': 1, 'ADBE Vector Shape - Ellipse': 1, 'ADBE Vector Shape - Group': 1, 'ADBE Vector Graphic - Fill': 1, 'ADBE Vector Graphic - Stroke': 1 } },
  'ADBE Vector Shape - Rect': { fixed: ['ADBE Vector Rect Size', 'ADBE Vector Rect Position', 'ADBE Vector Rect Roundness'] },
  'ADBE Vector Shape - Ellipse': { fixed: ['ADBE Vector Ellipse Size', 'ADBE Vector Ellipse Position'] },
  'ADBE Vector Shape - Group': { fixed: ['ADBE Vector Shape'] },
  'ADBE Vector Graphic - Fill': { fixed: ['ADBE Vector Fill Color', 'ADBE Vector Fill Rule', 'ADBE Vector Fill Opacity'] },
  'ADBE Vector Graphic - Stroke': { fixed: ['ADBE Vector Stroke Color', 'ADBE Vector Stroke Width', 'ADBE Vector Stroke Line Cap', 'ADBE Vector Stroke Line Join'] },
};

let CURRENT_LAYER = null;
class Shape { constructor() { this.vertices = []; this.inTangents = []; this.outTangents = []; this.closed = true; } }
class TextDocument {
  constructor(t) { this.text = t; this.font = 'ArialMT'; this.fontSize = 36; this.applyFill = true; this.fillColor = [1, 1, 1]; this.applyStroke = false; this.strokeColor = [0, 0, 0]; this.strokeWidth = 0; this.justification = 0; this.tracking = 0; }
  resetCharStyle() {} resetParagraphStyle() {}
}
function copyDoc(d) { const n = new TextDocument(d.text); Object.assign(n, d); return n; }

function checkValue(mn, spec, v, where) {
  if (spec.shape) {
    if (!(v instanceof Shape)) return fail(`${where}: ${mn} expects Shape`);
    const n = v.vertices.length;
    if (!n || v.inTangents.length !== n || v.outTangents.length !== n) fail(`${where}: ${mn} shape arrays mismatch ${n}/${v.inTangents.length}/${v.outTangents.length}`);
    for (const p of v.vertices) if (p.length !== 2 || p.some(x => !isFinite(x))) return fail(`${where}: bad vertex ${p}`);
    return;
  }
  if (spec.textdoc) { if (!(v instanceof TextDocument)) fail(`${where}: textdoc expected`); return; }
  const dims = spec.dims;
  if (dims === 1) {
    if (typeof v !== 'number' || !isFinite(v)) return fail(`${where}: ${mn} expects number, got ${JSON.stringify(v)}`);
    if (spec.range && (v < spec.range[0] || v > spec.range[1])) fail(`${where}: ${mn} out of range ${v}`);
    if (spec.max && v > spec.max) fail(`${where}: ${mn} > max ${v}`);
    return;
  }
  const ok = Array.isArray(dims) ? dims : [dims];
  if (!Array.isArray(v) || !ok.includes(v.length) || v.some(x => typeof x !== 'number' || !isFinite(x)))
    fail(`${where}: ${mn} expects ${ok.join('|')}D array, got ${JSON.stringify(v)}`);
}

class Prop {
  constructor(mn, parent, idx) { this.matchName = mn; this.name = mn; this.parentProperty = parent; this.propertyIndex = idx; this.spec = LEAF[mn]; this.keys = []; this._v = null; this._expr = ''; this.hasMax = !!(this.spec && this.spec.max); this.maxValue = this.spec && this.spec.max; STATS.props++; }
  where() { return `${CURRENT_LAYER ? CURRENT_LAYER.name : '?'}/${this.matchName}`; }
  setValue(v) { if (this.spec.exprOnly) {} else checkValue(this.matchName, this.spec, v, this.where()); if (this.keys.length) fail(`${this.where()}: setValue on keyed property`); this._v = v; }
  setValueAtTime(t, v) { if (typeof t !== 'number' || !isFinite(t)) fail(`${this.where()}: bad time ${t}`); checkValue(this.matchName, this.spec, v, this.where()); this.keys.push([t, v]); this.keys.sort((a, b) => a[0] - b[0]); STATS.keys++; }
  setValuesAtTimes(ts, vs) { if (ts.length !== vs.length) fail(`${this.where()}: times/values length mismatch`); for (let i = 0; i < ts.length; i++) this.setValueAtTime(ts[i], vs[i]); }
  get numKeys() { return this.keys.length; }
  removeKey(i) { if (i < 1 || i > this.keys.length) fail(`${this.where()}: removeKey ${i}`); this.keys.splice(i - 1, 1); }
  setInterpolationTypeAtKey(i, a, b) { if (i < 1 || i > this.keys.length) fail(`${this.where()}: interp key ${i}/${this.keys.length}`); if (a === undefined) fail(`${this.where()}: interp type undefined`); }
  get value() { if (this.spec.textdoc) return copyDoc(this._v || new TextDocument('')); return this._v; }
  set expression(e) { if (typeof e !== 'string') fail(`${this.where()}: expression not string`); this._expr = e; STATS.expressions++; EXPRS.push({ layer: CURRENT_LAYER, prop: this, expr: e }); }
  get expression() { return this._expr; }
}
const EXPRS = [];

class Group {
  constructor(mn, parent, idx) {
    this.matchName = mn; this.name = mn; this.parentProperty = parent; this.propertyIndex = idx; this.children = []; this.spec = GROUPS[mn];
    if (!this.spec) fail(`unknown group ${mn}`);
    if (this.spec && this.spec.fixed) for (const c of this.spec.fixed) this._mk(c);
    this.maskMode = undefined;
  }
  _mk(mn) { const idx = this.children.length + 1; const p = GROUPS[mn] ? new Group(mn, this, idx) : (LEAF[mn] ? new Prop(mn, this, idx) : null); if (!p) { fail(`no spec for ${mn}`); return null; } this.children.push(p); return p; }
  get numProperties() { return this.children.length; }
  property(k) {
    if (typeof k === 'number') { const p = this.children[k - 1]; if (!p) fail(`${this.matchName}: no property index ${k}`); return p; }
    const p = this.children.find(c => c.matchName === k || c.name === k);
    if (!p) fail(`${CURRENT_LAYER ? CURRENT_LAYER.name : '?'}: ${this.matchName} has no property "${k}"`);
    return p;
  }
  addProperty(mn) {
    if (!this.spec || !this.spec.add || !this.spec.add[mn]) { fail(`${this.matchName}: cannot addProperty "${mn}"`); return null; }
    if (mn === 'ADBE Mask Atom') STATS.masks++;
    if (this.matchName === 'ADBE Effect Parade') STATS.effects++;
    return this._mk(mn);
  }
}

let LAYER_SEQ = 0;
class Layer {
  constructor(comp, kind, src, dur) {
    this.comp = comp; this.kind = kind; this.source = src; this.name = kind + (++LAYER_SEQ); this.startTime = 0;
    this._in = 0; this._out = dur; this.srcDur = dur; this._parent = null; this.motionBlur = false; this.blendingMode = 0; this.audioEnabled = true; this.enabled = true; this._tre = false;
    this.props = { 'ADBE Transform Group': new Group('ADBE Transform Group', null, 1), 'ADBE Effect Parade': new Group('ADBE Effect Parade', null, 2), 'ADBE Mask Parade': new Group('ADBE Mask Parade', null, 3) };
    if (kind === 'text') this.props['ADBE Text Properties'] = new Group('ADBE Text Properties', null, 4);
    if (kind === 'shape') this.props['ADBE Root Vectors Group'] = new Group('ADBE Root Vectors Group', null, 4);
    if (['footage', 'precomp', 'seq', 'image'].includes(kind)) this.props['ADBE Time Remapping'] = new Prop('ADBE Time Remapping', null, 5);
    STATS.layers++;
    CURRENT_LAYER = this;
  }
  property(mn) { const p = this.props[mn]; if (p === undefined) { if (mn === 'ADBE Text Properties') return null; fail(`${this.name}: no top property ${mn}`); } CURRENT_LAYER = this; return p; }
  get inPoint() { return this._in; } set inPoint(v) { if (v >= this._out) fail(`${this.name}: inPoint ${v} >= outPoint ${this._out}`); this._in = v; }
  get outPoint() { return this._out; }
  set outPoint(v) { if (v <= this._in) fail(`${this.name}: outPoint ${v} <= inPoint`); if (!this._tre && this.srcDur !== null && v > this.srcDur + 1e-6 && ['footage', 'precomp', 'seq'].includes(this.kind)) fail(`${this.name}: outPoint ${v} beyond source ${this.srcDur} without time remap`); this._out = v; }
  get timeRemapEnabled() { return this._tre; }
  set timeRemapEnabled(v) { if (!this.props['ADBE Time Remapping']) fail(`${this.name}: no time remap`); this._tre = v; if (v) { const p = this.props['ADBE Time Remapping']; p.keys = [[0, 0], [this.srcDur, this.srcDur]]; } }
  get parent() { return this._parent; } set parent(p) { this._parent = p; }
  setParentWithJump(p) { if (p === this) fail('self parent'); this._parent = p; }
  get hasParent() { return !!this._parent; }
  sourceRectAtTime(t, ext) {
    if (this.kind !== 'text') return { top: 0, left: 0, width: 1080, height: 1920 };
    const d = this.props['ADBE Text Properties'].property('ADBE Text Document').value;
    const w = d.text.length * 0.66 * d.fontSize;
    return { top: -0.62 * d.fontSize, left: -w / 2, width: w, height: 0.8 * d.fontSize };
  }
  remove() { const i = this.comp._layers.indexOf(this); this.comp._layers.splice(i, 1); STATS.layers--; }
  moveToEnd() { const i = this.comp._layers.indexOf(this); this.comp._layers.splice(i, 1); this.comp._layers.push(this); }
  setTrackMatte(m, type) { const i = this.comp._layers.indexOf(this), j = this.comp._layers.indexOf(m); if (j !== i - 1) fail(`${this.name}: matte not directly above (${j} vs ${i})`); this.matte = m; }
  set trackMatteType(t) { const i = this.comp._layers.indexOf(this); if (i < 1) fail(`${this.name}: no layer above for matte`); this.matte = this.comp._layers[i - 1]; }
}

class CompItem {
  constructor(name, w, h, pa, dur, fps) { this.name = name; this.width = w; this.height = h; this.duration = dur; this.frameRate = fps; this._layers = []; this.parentFolder = null; STATS.comps++; const self = this;
    this.layers = {
      _add(l) { self._layers.unshift(l); return l; },
      add(item, dur) { const kind = item instanceof CompItem ? 'precomp' : (item.isSeq ? 'seq' : (item.isStill ? 'image' : (item.isAudio ? 'audio' : 'footage'))); const d = item instanceof CompItem ? item.duration : (item.isStill ? (dur || self.duration) : item.duration); return this._add(new Layer(self, kind, item, d)); },
      addSolid(color, name, w, h, pa, dur) { if (!Array.isArray(color) || color.length !== 3) fail(`addSolid color ${color}`); if (!(w >= 1 && h >= 1 && w <= 30000 && h <= 30000)) fail(`addSolid size ${w}x${h}`); const l = new Layer(self, 'solid', null, dur); l.name = name; return this._add(l); },
      addText(s) { if (typeof s !== 'string') fail('addText arg'); const l = new Layer(self, 'text', null, self.duration); const tp = l.props['ADBE Text Properties'].property('ADBE Text Document'); tp._v = new TextDocument(s); return this._add(l); },
      addShape() { return this._add(new Layer(self, 'shape', null, self.duration)); },
      addNull(dur) { return this._add(new Layer(self, 'null', null, dur)); },
    };
  }
  openInViewer() {}
}
class FolderItem { constructor(n) { this.name = n; this.parentFolder = null; } }
// frames of an image sequence = files in the folder sharing the first frame's prefix and extension
function seqFrames(f) {
  const rel = f.fsName.split('/assets/')[1];
  const dir = (rel ? ASSET_ROOT + '/' + rel : f.fsName).split('/').slice(0, -1).join('/');
  const m = f.name.match(/^(.*?)\d+\.(\w+)$/);
  const n = fs.readdirSync(dir).filter(x => x.startsWith(m[1]) && x.endsWith('.' + m[2])).length;
  if (n < 2) fail('sequence too short: ' + f.name);
  return n;
}
class FootageItem { constructor(f, seq) { this.file = f; this.name = f.name; const ext = f.name.split('.').pop().toLowerCase(); this.isSeq = !!seq; this.isStill = !seq && ['png', 'jpg'].includes(ext); this.isAudio = ext === 'wav'; this.duration = seq ? seqFrames(f) / 25 : (this.isAudio ? 14.88 : (this.isStill ? 0 : 9.88)); this.mainSource = { conformFrameRate: 0 }; this.parentFolder = null; } }

const ASSET_ROOT = process.env.ASSET_ROOT || '';
class FileImpl {
  constructor(p) { this.fsName = p; this.name = p.split('/').pop(); this.encoding = 'UTF-8'; }
  get exists() { const rel = this.fsName.split('/assets/')[1]; if (!rel) return fs.existsSync(this.fsName); const ok = fs.existsSync(ASSET_ROOT + '/' + rel); if (!ok) fail('missing asset ' + rel); return ok; }
  get parent() { return new FileImpl(this.fsName.split('/').slice(0, -1).join('/')); }
  open() { return true; } write(s) { this._w = s; } close() {}
  static openDialog() { fail('openDialog called'); return null; }
}
function File(p) { return new FileImpl(p); }
File.openDialog = FileImpl.openDialog;
class ImportOptions { constructor(f) { this.file = f; this.sequence = false; this.forceAlphabetical = false; } }

const ui = () => { const c = { children: [], add(type, b, label) { const x = ui(); x.type = type; x.text = typeof label === 'string' ? label : (label ? '' : ''); c.children.push(x); if (type === 'dropdownlist') { x.items = []; x.removeAll = () => (x.items = []); x.add = (t, s) => { x.items.push({ text: s }); return x.items[x.items.length - 1]; }; } return x; }, preferredSize: {}, characters: 0, alignment: null, orientation: null, alignChildren: null, show() { return 1; } }; return c; };
function Window() { return ui(); }

const ctx = {
  app: { project: null, newProject() { this.project = makeProject(); return this.project; }, beginUndoGroup() {}, endUndoGroup() {}, fonts: undefined },
  $: { fileName: '/mock/MOTTI_Update_V8.1_build.jsx' },
  File, ImportOptions, CompItem, Shape, Window, alert: m => console.log('[alert]', m),
  KeyframeInterpolationType: { LINEAR: 6612, BEZIER: 6613, HOLD: 6614 },
  BlendingMode: { NORMAL: 1, MULTIPLY: 2, SCREEN: 3, ADD: 4 },
  TrackMatteType: { ALPHA: 1, NO_TRACK_MATTE: 0 },
  ParagraphJustification: { LEFT_JUSTIFY: 1, RIGHT_JUSTIFY: 2, CENTER_JUSTIFY: 3 },
  MaskMode: { ADD: 1 },
};
if (RTL) { ctx.ParagraphDirection = { DIRECTION_LEFT_TO_RIGHT: 1, DIRECTION_RIGHT_TO_LEFT: 2 }; ctx.ComposerEngine = { UNIVERSAL_TYPE_ENGINE: 2 }; }
function makeProject() {
  const items = []; const p = {
    items: { addFolder(n) { const f = new FolderItem(n); items.push(f); return f; }, addComp(n, w, h, pa, d, fps) { if (!(w > 0 && h > 0 && d > 0 && fps > 0)) fail('addComp args'); const c = new CompItem(n, w, h, pa, d, fps); items.push(c); return c; } },
    importFile(io) { if (!io.file.exists) fail('import missing'); const it = new FootageItem(io.file, io.sequence); items.push(it); return it; },
    activeItem: null, _items: items,
    get numItems() { return items.length; },
    save(f) { if (!f || !/\.aep$/.test(f.fsName)) fail('save: bad file'); p._saved = f.fsName; console.log('[save]', f.fsName); },
  }; return p;
}
ctx.app.project = makeProject();
if (process.env.MOCK_BUSY) {   // simulate an open reference project: the build must go to a new project
  ctx.app.project.items.addFolder('reference project item');
  const ref = ctx.app.project;
  process.on('exit', () => { if (ctx.app.project === ref) { console.log('MOCK FAIL: built into the open reference project'); process.exitCode = 1; } });
}
vm.createContext(ctx);
let src = fs.readFileSync(file, 'utf8').replace(/^﻿/, '');
try { vm.runInContext(src, ctx, { filename: file }); } catch (e) { fail('RUNTIME: ' + e.stack.split('\n').slice(0, 4).join(' | ')); }

// ------------------------------------------------------------------ evaluate expressions
function evalExpr(x) {
  const L = x.layer;
  const fakeLayer = name => ({ sourceRectAtTime: () => ({ top: -120, left: -300, width: 600, height: 160 }), toComp: p => [p[0] + 540, p[1] + 960], transform: { scale: [100, 100] } });
  const isSel = x.prop.matchName === 'ADBE Text Expressible Amount';
  const results = [];
  const samples = isSel ? [[1, 0], [1, 5], [3, 5.7], [6, 9], [2, 10.4]] : [[0, 3.5], [0, 7.0], [0, 9.3]];
  for (const [ti, time] of samples) {
    const c = {
      Math, time, textIndex: ti, textTotal: 6,
      thisLayer: { text: { sourceText: 'מכל מה' }, hasParent: true, parent: { fromComp: p => [p[0] - 540, p[1] - 960] } },
      thisComp: { layer: fakeLayer }, value: [600, 96], clamp: (v, a, b) => Math.min(Math.max(v, a), b),
    };
    try { results.push(vm.runInNewContext(x.expr, c)); } catch (e) { fail(`expr on ${L.name}/${x.prop.matchName}: ${e.message}`); return; }
  }
  for (const r of results) {
    if (isSel) { if (typeof r !== 'number' || !isFinite(r)) fail(`selector expr on ${L.name} returned ${r}`); }
    else if (!Array.isArray(r) || r.length !== 2 || r.some(v => !isFinite(v))) fail(`expr on ${L.name} returned ${JSON.stringify(r)}`);
  }
}
for (const x of EXPRS) evalExpr(x);

// ------------------------------------------------------------------ structural checks
for (const it of ctx.app.project._items) {
  if (!(it instanceof CompItem)) continue;
  const names = new Set();
  for (const l of it._layers) {
    if (names.has(l.name) && !l.name.endsWith('matte')) WARN.push(`duplicate layer name ${l.name} in ${it.name}`);
    names.add(l.name);
    if (l._parent && !it._layers.includes(l._parent)) fail(`${l.name}: parent in another comp`);
  }
  console.log(`comp "${it.name}": ${it._layers.length} layers`);
}
console.log('stats', JSON.stringify(STATS));
if (WARN.length) console.log('warnings:', WARN.slice(0, 10));
if (ERR.length) { console.log(`ERRORS (${ERR.length}):`); ERR.slice(0, 40).forEach(e => console.log('  ' + e)); process.exit(1); }
console.log('MOCK RUN OK' + (RTL ? ' (rtl api present)' : ' (no rtl api)'));
