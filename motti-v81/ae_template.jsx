// =====================================================================================
//  MOTTI Rosenfeld - "Update V8.1"  |  After Effects project builder
//  1080x1920 @ 25 fps, 14.88 s.  Generated from scene.json (same source as preview.mp4).
//
//  How to run:  After Effects 2020 or newer  ->  File > Scripts > Run Script File...
//               pick this file. Keep the "assets" folder next to it.
//  Tip: select one heavy and one light text layer from the reference project before
//  running - the font dialog can read their fonts ("From selection").
// =====================================================================================
(function MottiV81Builder() {
    var SCENE = __SCENE__;
    var META = __META__;

    var LOG = [];
    function warn(msg) { LOG.push(msg); }

    var ROOT = File($.fileName).parent;
    function assetFile(rel) { return new File(ROOT.fsName + "/assets/" + rel); }

    // ------------------------------------------------------------------ fonts
    var FONT = { H: "NotoSansHebrew-Black", L: "NotoSansHebrew-Light" };

    function selectedTextFonts() {
        var out = [];
        var c = app.project ? app.project.activeItem : null;
        if (!c || !(c instanceof CompItem)) { return out; }
        var sel = c.selectedLayers;
        for (var i = 0; i < sel.length; i++) {
            var tp = sel[i].property("ADBE Text Properties");
            if (!tp) { continue; }
            var f = tp.property("ADBE Text Document").value.font;
            var seen = false;
            for (var j = 0; j < out.length; j++) { if (out[j] === f) { seen = true; } }
            if (!seen) { out.push(f); }
        }
        return out;
    }

    function fontExists(ps) {
        try {
            if (app.fonts && app.fonts.getFontsByPostScriptName) {
                return app.fonts.getFontsByPostScriptName(ps).length > 0;
            }
        } catch (e) {}
        return true; // cannot check on this version
    }

    function searchFonts(q) {
        var res = [];
        try {
            if (!app.fonts || !app.fonts.allFonts) { return res; }
            var fams = app.fonts.allFonts;
            q = q.toLowerCase();
            for (var i = 0; i < fams.length && res.length < 300; i++) {
                for (var j = 0; j < fams[i].length; j++) {
                    var f = fams[i][j];
                    var label = f.postScriptName + "   (" + f.familyName + " " + f.styleName + ")";
                    if (label.toLowerCase().indexOf(q) >= 0) { res.push(f.postScriptName); }
                }
            }
        } catch (e) {}
        return res;
    }

    function chooseFonts() {
        var sel = selectedTextFonts();
        if (sel.length >= 1) { FONT.H = sel[0]; }
        if (sel.length >= 2) { FONT.L = sel[1]; }
        var w = new Window("dialog", "MOTTI V8.1 - fonts / פונטים");
        w.orientation = "column";
        w.alignChildren = ["fill", "top"];
        w.add("statictext", undefined,
            "Fonts of the reference video (PostScript names). Heavy = big titles, Light = secondary words.",
            { multiline: true });
        var rows = {};
        var canSearch = false;
        try { canSearch = !!(app.fonts && app.fonts.allFonts); } catch (e0) {}
        function row(key, label) {
            var g = w.add("group");
            g.orientation = "row";
            var st = g.add("statictext", undefined, label);
            st.preferredSize.width = 110;
            var e = g.add("edittext", undefined, FONT[key]);
            e.characters = 30;
            var pick = 0;
            var b = g.add("button", undefined, "From selection");
            b.onClick = function () {
                if (!sel.length) { alert("Select text layers in the active comp before running the script."); return; }
                e.text = sel[pick % sel.length];
                pick++;
            };
            if (canSearch) {
                var dd = g.add("dropdownlist", undefined, []);
                dd.preferredSize.width = 220;
                var sb = g.add("button", undefined, "Search");
                sb.onClick = function () {
                    dd.removeAll();
                    var r = searchFonts(e.text);
                    for (var i = 0; i < r.length; i++) { dd.add("item", r[i]); }
                    if (r.length) { dd.selection = 0; e.text = r[0]; }
                };
                dd.onChange = function () { if (dd.selection) { e.text = dd.selection.text; } };
            }
            rows[key] = e;
        }
        row("H", "Heavy font:");
        row("L", "Light font:");
        var bg = w.add("group");
        bg.alignment = "right";
        bg.add("button", undefined, "Cancel", { name: "cancel" });
        bg.add("button", undefined, "Build", { name: "ok" });
        if (w.show() !== 1) { return false; }
        FONT.H = rows.H.text;
        FONT.L = rows.L.text;
        if (!fontExists(FONT.H)) { warn("Heavy font not found: " + FONT.H); }
        if (!fontExists(FONT.L)) { warn("Light font not found: " + FONT.L); }
        return true;
    }

    // ------------------------------------------------------------------ small utils
    function hexRGB(h) {
        var n = parseInt(h.substring(1), 16);
        return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
    }
    function hexRGBA(h) { var c = hexRGB(h); return [c[0], c[1], c[2], 1]; }
    function isTrack(v) { return v !== null && typeof v === "object" && !(v instanceof Array) && v.k !== undefined; }

    function applyTrack(prop, tr, map) {
        if (tr === null || tr === undefined) { return; }
        if (!isTrack(tr)) { prop.setValue(map ? map(tr) : tr); return; }
        var times = [], vals = [];
        for (var i = 0; i < tr.k.length; i++) {
            times.push(tr.k[i][0]);
            vals.push(map ? map(tr.k[i][1]) : tr.k[i][1]);
        }
        if (times.length === 1) { prop.setValue(vals[0]); return; }
        prop.setValuesAtTimes(times, vals);
        var interp = tr.h ? KeyframeInterpolationType.HOLD : KeyframeInterpolationType.LINEAR;
        for (var k = 1; k <= prop.numKeys; k++) { prop.setInterpolationTypeAtKey(k, interp, interp); }
    }

    function addTrack2(a, b) { return [a[0] + b[0], a[1] + b[1]]; }

    function setParent(child, parent) {
        if (!parent) { return; }
        if (typeof child.setParentWithJump === "function") { child.setParentWithJump(parent); }
        else { child.parent = parent; }
    }

    function setTiming(lyr, tin, tout) {
        if (tout > lyr.outPoint) { lyr.outPoint = tout; }
        lyr.inPoint = tin;
        lyr.outPoint = tout;
    }

    // SVG path ("M L C Z") -> AE Shape objects (one per sub-path)
    function svgToShapes(d) {
        var tok = d.replace(/([MLCZ])/g, " $1 ").replace(/,/g, " ").split(/\s+/);
        var shapes = [], cur = null, i = 0, prev = null;
        function num() { return parseFloat(tok[i++]); }
        function finish(closed) {
            if (!cur || cur.v.length < 2) { cur = null; return; }
            if (closed) {
                var a = cur.v[0], z = cur.v[cur.v.length - 1];
                if (Math.abs(a[0] - z[0]) < 0.01 && Math.abs(a[1] - z[1]) < 0.01) {
                    cur.it[0] = cur.it[cur.it.length - 1];
                    cur.v.pop(); cur.it.pop(); cur.ot.pop();
                }
            }
            var s = new Shape();
            s.vertices = cur.v; s.inTangents = cur.it; s.outTangents = cur.ot; s.closed = closed;
            shapes.push(s);
            cur = null;
        }
        while (i < tok.length) {
            var t = tok[i++];
            if (t === "") { continue; }
            if (t === "M") {
                if (cur) { finish(false); }
                var p = [num(), num()];
                cur = { v: [p], it: [[0, 0]], ot: [[0, 0]] };
                prev = p;
            } else if (t === "L") {
                var q = [num(), num()];
                cur.v.push(q); cur.it.push([0, 0]); cur.ot.push([0, 0]);
                prev = q;
            } else if (t === "C") {
                var c1 = [num(), num()], c2 = [num(), num()], e = [num(), num()];
                cur.ot[cur.ot.length - 1] = [c1[0] - prev[0], c1[1] - prev[1]];
                cur.v.push(e); cur.it.push([c2[0] - e[0], c2[1] - e[1]]); cur.ot.push([0, 0]);
                prev = e;
            } else if (t === "Z") {
                finish(true);
            }
        }
        if (cur) { finish(false); }
        return shapes;
    }

    function rectShape(r, rad) {
        var x0 = r[0], y0 = r[1], x1 = r[2], y1 = r[3];
        var s = new Shape();
        if (!rad) {
            s.vertices = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
            s.inTangents = [[0, 0], [0, 0], [0, 0], [0, 0]];
            s.outTangents = [[0, 0], [0, 0], [0, 0], [0, 0]];
        } else {
            var k = rad * 0.5523;
            s.vertices = [[x0 + rad, y0], [x1 - rad, y0], [x1, y0 + rad], [x1, y1 - rad],
                          [x1 - rad, y1], [x0 + rad, y1], [x0, y1 - rad], [x0, y0 + rad]];
            s.inTangents = [[-k, 0], [0, 0], [0, -k], [0, 0], [k, 0], [0, 0], [0, k], [0, 0]];
            s.outTangents = [[0, 0], [k, 0], [0, 0], [0, k], [0, 0], [-k, 0], [0, 0], [0, -k]];
        }
        s.closed = true;
        return s;
    }

    function ellipseShape(cx, cy, w, h) {
        var rx = Math.max(0.5, w / 2), ry = Math.max(0.5, h / 2), kx = rx * 0.5523, ky = ry * 0.5523;
        var s = new Shape();
        s.vertices = [[cx, cy - ry], [cx + rx, cy], [cx, cy + ry], [cx - rx, cy]];
        s.inTangents = [[-kx, 0], [0, -ky], [kx, 0], [0, ky]];
        s.outTangents = [[kx, 0], [0, ky], [-kx, 0], [0, -ky]];
        s.closed = true;
        return s;
    }

    function setPercentParam(p, pct) {
        var mx = 100;
        try { if (p.hasMax && p.maxValue > 100) { mx = p.maxValue; } } catch (e) {}
        p.setValue(pct / 100 * mx);
    }

    // ------------------------------------------------------------------ easing for expressions
    var EASE_EXPR = {
        linear: "p",
        outExpo: "(p>=1?1:1-Math.pow(2,-10*p))",
        inExpo: "(p<=0?0:Math.pow(2,10*p-10))",
        outCubic: "(1-Math.pow(1-p,3))",
        inCubic: "(p*p*p)",
        inQuad: "(p*p)",
        outQuad: "(1-(1-p)*(1-p))",
        inOutCubic: "(p<0.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2)",
        inOutSine: "(-(Math.cos(Math.PI*p)-1)/2)",
        outBack: "(1+2.70158*Math.pow(p-1,3)+1.70158*Math.pow(p-1,2))",
        outBack2: "(1+3.4*Math.pow(p-1,3)+2.4*Math.pow(p-1,2))",
        outBack14: "(1+2.4*Math.pow(p-1,3)+1.4*Math.pow(p-1,2))"
    };

    function selectorExpression(s) {
        var e = "// generated: per-character timing (same math as the preview)\n";
        e += "var t0=" + s.t0 + ", dur=" + s.dur + ", st=" + s.stag + ";\n";
        if (s.by === "word") {
            e += "var s = \"\" + thisLayer.text.sourceText; var k = 0;\n";
            e += "for (var i = 0; i < textIndex - 1; i++) { if (s.charAt(i) == \" \") k++; }\n";
        } else {
            e += "var k = textIndex - 1;\n";
        }
        if (s.order === "rev") { e += "k = textTotal - 1 - k;\n"; }
        e += "var t1 = t0 + k * st;\n";
        if (s.step) {
            e += "time < t1 ? 100 : 0;";
        } else {
            e += "var p = dur > 0 ? Math.min(Math.max((time - t1) / dur, 0), 1) : (time >= t1 ? 1 : 0);\n";
            e += "var e = " + (EASE_EXPR[s.ease] || "p") + ";\n";
            e += (s.mode === "in") ? "(1 - e) * 100;" : "e * 100;";
        }
        return e;
    }

    // ------------------------------------------------------------------ project
    if (!chooseFonts()) { return; }
    app.beginUndoGroup("MOTTI V8.1 build");
    if (!app.project) { app.newProject(); }
    var proj = app.project;
    var top = proj.items.addFolder("MOTTI_Update_V8.1");
    var fAssets = proj.items.addFolder("assets");
    fAssets.parentFolder = top;

    function importAsset(rel, asSequence) {
        var f = assetFile(rel);
        if (!f.exists) {
            f = File.openDialog("Locate " + rel);
            if (!f) { throw new Error("Missing asset: " + rel); }
        }
        var io = new ImportOptions(f);
        if (asSequence) { io.sequence = true; io.forceAlphabetical = true; }
        var it = proj.importFile(io);
        it.parentFolder = fAssets;
        if (asSequence) { try { it.mainSource.conformFrameRate = SCENE.fps; } catch (e) {} }
        return it;
    }

    var ITEMS = { footage: importAsset(META.footage, false), images: {}, seq: null, audio: {} };
    for (var ii = 0; ii < META.images.length; ii++) { ITEMS.images[META.images[ii]] = importAsset(META.images[ii], false); }
    if (META.seq) { ITEMS.seq = importAsset(META.seq, true); }
    for (var ai = 0; ai < META.audio.length; ai++) { ITEMS.audio[META.audio[ai]] = importAsset("audio/" + META.audio[ai], false); }

    var COMPS = {};
    function makeComp(name, label) {
        var c = SCENE.comps[name];
        var comp = proj.items.addComp(label, c.w, c.h, 1, c.dur, c.fps);
        comp.parentFolder = top;
        comp.bgColor = [0, 0, 0];
        comp.motionBlur = true;
        try { comp.shutterAngle = 180; comp.shutterPhase = -90; } catch (e) {}
        try { comp.motionBlurSamplesPerFrame = 16; comp.motionBlurAdaptiveSampleLimit = 128; } catch (e2) {}
        COMPS[name] = comp;
        return comp;
    }

    // text metrics of the chosen fonts (base height for visual centring, width for fitting)
    var METRIC = {};
    var HB = {};
    function textMetric(comp, fontKey, size, latin) {
        var key = fontKey + "|" + size + "|" + (latin ? 1 : 0);
        if (METRIC[key] !== undefined) { return METRIC[key]; }
        var tmp = comp.layers.addText(latin ? "H" : "שמ");
        var tp = tmp.property("ADBE Text Properties").property("ADBE Text Document");
        var td = tp.value;
        try { td.font = FONT[fontKey]; } catch (e) {}
        td.fontSize = size;
        tp.setValue(td);
        var r = tmp.sourceRectAtTime(0, false);
        tmp.remove();
        METRIC[key] = -r.top;
        return METRIC[key];
    }

    var RTL_OK = null;
    function setRTL(td) {
        var ok = false;
        try {
            if (typeof ParagraphDirection !== "undefined") {
                td.direction = ParagraphDirection.DIRECTION_RIGHT_TO_LEFT; ok = true;
            }
        } catch (e) { ok = false; }
        try { if (typeof ComposerEngine !== "undefined") { td.composerEngine = ComposerEngine.UNIVERSAL_TYPE_ENGINE; } } catch (e2) {}
        if (RTL_OK === null) { RTL_OK = ok; if (!ok) { warn("Paragraph direction could not be set from script; colon kept with RLM mark."); } }
    }
    function rtlText(s, L) {
        if (L.dir === "rtl" && RTL_OK === false && s.charAt(s.length - 1) === ":") { return s + "‏"; }
        return s;
    }

    function makeText(comp, L) {
        var lyr = comp.layers.addText(L.text);
        var tp = lyr.property("ADBE Text Properties").property("ADBE Text Document");
        var td = tp.value;
        try { td.resetCharStyle(); td.resetParagraphStyle(); } catch (e) {}
        try { td.font = FONT[L.font]; } catch (e1) { warn("font " + FONT[L.font] + " on " + L.name); }
        td.fontSize = L.size;
        td.applyFill = !!L.fill;
        if (L.fill) { td.fillColor = hexRGB(L.fill); }
        td.applyStroke = !!L.stroke;
        if (L.stroke) { td.strokeColor = hexRGB(L.stroke); td.strokeWidth = L.sw; td.strokeOverFill = true; }
        td.justification = L.just === "right" ? ParagraphJustification.RIGHT_JUSTIFY :
            (L.just === "left" ? ParagraphJustification.LEFT_JUSTIFY : ParagraphJustification.CENTER_JUSTIFY);
        td.tracking = L.track || 0;
        if (L.dir === "rtl") { setRTL(td); }
        td.text = rtlText(L.text, L);
        tp.setValue(td);
        // fit very wide words into the frame (fonts differ in width)
        if (L.size >= 100) {
            var r = lyr.sourceRectAtTime(L["in"], false);
            var maxW = META.maxTextWidth;
            if (r.width > maxW) {
                var d2 = tp.value; d2.fontSize = Math.floor(L.size * maxW / r.width); tp.setValue(d2);
                warn("Resized '" + L.name + "' to fit the frame (" + d2.fontSize + " px).");
            }
        }
        HB[L.name] = textMetric(comp, L.font, tp.value.fontSize, L.dir === "ltr");
        if (L.src) {
            var base = tp.value;
            for (var i = 0; i < L.src.length; i++) {
                base.text = rtlText(L.src[i][1], L);
                tp.setValueAtTime(L.src[i][0], base);
            }
        }
        // per-character animators (expression selectors -> independent of the font's metrics)
        var anims = L.anims || [];
        for (var a = 0; a < anims.length; a++) {
            var A = anims[a];
            var an = lyr.property("ADBE Text Properties").property("ADBE Text Animators").addProperty("ADBE Text Animator");
            an.name = "anim_" + (a + 1);
            var ai = an.propertyIndex;
            var AN = function () { return lyr.property("ADBE Text Properties").property("ADBE Text Animators").property(ai); };
            AN().property("ADBE Text Selectors").addProperty("ADBE Text Expressible Selector");
            AN().property("ADBE Text Selectors").property(1).property("ADBE Text Expressible Amount").expression = selectorExpression(A.sel);
            var P = A.props;
            if (P.pos) { AN().property("ADBE Text Animator Properties").addProperty("ADBE Text Position 3D").setValue([P.pos[0], P.pos[1], 0]); }
            if (P.scale) { AN().property("ADBE Text Animator Properties").addProperty("ADBE Text Scale 3D").setValue([P.scale[0], P.scale[1], 100]); }
            if (P.op !== undefined) { AN().property("ADBE Text Animator Properties").addProperty("ADBE Text Opacity").setValue(P.op); }
            if (P.rot) { AN().property("ADBE Text Animator Properties").addProperty("ADBE Text Rotation").setValue(P.rot); }
        }
        return lyr;
    }

    function addShapeItems(lyr, items) {
        var glow = 0;
        for (var i = 0; i < items.length; i++) {
            var it = items[i];
            var g = lyr.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
            var gi = g.propertyIndex;
            var V = function () { return lyr.property("ADBE Root Vectors Group").property(gi).property("ADBE Vectors Group"); };
            if (it.kind === "rect") {
                var rc = V().addProperty("ADBE Vector Shape - Rect");
                applyTrack(rc.property("ADBE Vector Rect Size"), it.size);
                rc.property("ADBE Vector Rect Position").setValue(it.c);
                rc.property("ADBE Vector Rect Roundness").setValue(it.r || 0);
            } else if (it.kind === "ellipse" || it.kind === "glow") {
                var el = V().addProperty("ADBE Vector Shape - Ellipse");
                applyTrack(el.property("ADBE Vector Ellipse Size"), it.size);
                el.property("ADBE Vector Ellipse Position").setValue(it.c);
                if (it.kind === "glow") { glow = Math.max(glow, 0.25 * Math.min(it.size[0], it.size[1])); }
            } else if (it.kind === "path") {
                var shapes = svgToShapes(it.d);
                for (var s = 0; s < shapes.length; s++) {
                    V().addProperty("ADBE Vector Shape - Group").property("ADBE Vector Shape").setValue(shapes[s]);
                }
            }
            if (it.fill) {
                var fl = V().addProperty("ADBE Vector Graphic - Fill");
                fl.property("ADBE Vector Fill Color").setValue(hexRGBA(it.fill));
                if (it.evenodd) { fl.property("ADBE Vector Fill Rule").setValue(2); }
            }
            if (it.stroke) {
                var st = V().addProperty("ADBE Vector Graphic - Stroke");
                st.property("ADBE Vector Stroke Color").setValue(hexRGBA(it.stroke));
                applyTrack(st.property("ADBE Vector Stroke Width"), it.sw);
                st.property("ADBE Vector Stroke Line Cap").setValue(it.cap === "butt" ? 1 : 2);
                st.property("ADBE Vector Stroke Line Join").setValue(2);
            }
        }
        if (glow > 0) {
            var b = lyr.property("ADBE Effect Parade").addProperty("ADBE Gaussian Blur 2");
            b.property("ADBE Gaussian Blur 2-0001").setValue(glow);
        }
    }

    function addEffects(lyr, L) {
        var fx = L.fx || [];
        for (var i = 0; i < fx.length; i++) {
            var e = fx[i];
            try {
                if (e.type === "blur") {
                    var b = lyr.property("ADBE Effect Parade").addProperty("ADBE Gaussian Blur 2");
                    applyTrack(b.property("ADBE Gaussian Blur 2-0001"), e.amt, function (v) { return v * META.blurScale; });
                    try { b.property("ADBE Gaussian Blur 2-0003").setValue(1); } catch (e1) {}
                } else if (e.type === "shadow" || e.type === "glow") {
                    var d = lyr.property("ADBE Effect Parade").addProperty("ADBE Drop Shadow");
                    d.name = e.type === "glow" ? "Glow" : "Shadow";
                    d.property("ADBE Drop Shadow-0001").setValue(hexRGBA(e.color));
                    setPercentParam(d.property("ADBE Drop Shadow-0002"), e.op);
                    d.property("ADBE Drop Shadow-0003").setValue(e.type === "glow" ? 0 : e.dir);
                    d.property("ADBE Drop Shadow-0004").setValue(e.type === "glow" ? 0 : e.dist);
                    d.property("ADBE Drop Shadow-0005").setValue(e.soft);
                }
            } catch (err) { warn("effect " + e.type + " on " + L.name + ": " + err.toString()); }
        }
    }

    function addMasks(lyr, L) {
        var ms = L.masks || [];
        for (var i = 0; i < ms.length; i++) {
            var m = ms[i];
            var mk = lyr.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
            mk.maskMode = MaskMode.ADD;
            var shp = mk.property("ADBE Mask Shape");
            if (m.rect) { shp.setValue(rectShape(m.rect, m.r || 0)); }
            if (m.ellipse) {
                if (isTrack(m.size)) {
                    var times = [], vals = [];
                    for (var k = 0; k < m.size.k.length; k++) {
                        times.push(m.size.k[k][0]);
                        vals.push(ellipseShape(m.ellipse[0], m.ellipse[1], m.size.k[k][1][0], m.size.k[k][1][1]));
                    }
                    shp.setValuesAtTimes(times, vals);
                } else {
                    shp.setValue(ellipseShape(m.ellipse[0], m.ellipse[1], m.size[0], m.size[1]));
                }
            }
            if (m.feather) { mk.property("ADBE Mask Feather").setValue([m.feather, m.feather]); }
        }
    }

    function addClipMatte(comp, L, lyr, byName) {
        var c = L.clip;
        var w = Math.max(4, Math.round(c[2] - c[0])), h = Math.max(4, Math.round(c[3] - c[1]));
        var m = comp.layers.addSolid([1, 1, 1], L.name + " matte", w, h, 1, comp.duration);
        if (L.parent) { setParent(m, byName[L.parent]); }
        m.property("ADBE Transform Group").property("ADBE Position").setValue([c[0] + w / 2, c[1] + h / 2]);
        setTiming(m, L["in"], L.out);
        if (typeof lyr.setTrackMatte === "function") { lyr.setTrackMatte(m, TrackMatteType.ALPHA); }
        else { lyr.trackMatteType = TrackMatteType.ALPHA; }
    }

    function leftOfExpression(spec) {
        return "var L = thisComp.layer(\"" + spec.layer + "\");\n" +
            "var r = L.sourceRectAtTime(time, false);\n" +
            "var p = L.toComp([r.left, r.top + r.height / 2]);\n" +
            "var q = thisLayer.hasParent ? thisLayer.parent.fromComp(p) : p;\n" +
            "[q[0] - " + spec.gap + ", value[1]];";
    }
    function edgeOfExpression(spec) {
        return "var L = thisComp.layer(\"" + spec.layer + "\");\n" +
            "var r = L.sourceRectAtTime(time, false);\n" +
            "var x = " + (spec.side < 0 ? "r.left" : "r.left + r.width") + ";\n" +
            "var p = L.toComp([x, r.top + r.height / 2]);\n" +
            "var q = thisLayer.hasParent ? thisLayer.parent.fromComp(p) : p;\n" +
            "[q[0] + (" + spec.side + ") * " + spec.gap + ", value[1]];";
    }
    function pillExpression(textLayer, finalW) {
        return "var L = thisComp.layer(\"" + textLayer + "\");\n" +
            "var r = L.sourceRectAtTime(time, false);\n" +
            "var full = r.width + 88;\n" +
            "var k = Math.min(Math.max((value[0] - 96) / (" + finalW + " - 96), 0), 1);\n" +
            "[96 + (full - 96) * k, value[1]];";
    }

    function buildComp(name, label) {
        var spec = SCENE.comps[name];
        var comp = COMPS[name] || makeComp(name, label);
        var byName = {};
        for (var i = 0; i < spec.layers.length; i++) {
            var L = spec.layers[i];
            var lyr = null;
            try {
                if (L.type === "null") {
                    lyr = comp.layers.addNull(comp.duration);
                } else if (L.type === "solid") {
                    lyr = comp.layers.addSolid(hexRGB(L.color), L.name, L.w, L.h, 1, comp.duration);
                } else if (L.type === "footage") {
                    lyr = comp.layers.add(ITEMS.footage);
                    lyr.audioEnabled = false;
                } else if (L.type === "image") {
                    lyr = comp.layers.add(ITEMS.images[L.src], comp.duration);
                } else if (L.type === "seq") {
                    lyr = comp.layers.add(ITEMS.seq);
                    lyr.timeRemapEnabled = true;
                } else if (L.type === "precomp") {
                    lyr = comp.layers.add(COMPS[L.comp]);
                    if (L.tm !== null && L.tm !== undefined) { lyr.timeRemapEnabled = true; }
                } else if (L.type === "text") {
                    lyr = makeText(comp, L);
                } else if (L.type === "shape") {
                    lyr = comp.layers.addShape();
                    addShapeItems(lyr, L.items);
                }
                lyr.name = L.name;
                byName[L.name] = lyr;
                if (L.parent) { setParent(lyr, byName[L.parent]); }
                if (lyr.timeRemapEnabled) {
                    var trp = lyr.property("ADBE Time Remapping");
                    while (trp.numKeys > 0) { trp.removeKey(trp.numKeys); }
                    if (L.type === "seq") { applyTrack(trp, L.idx, function (v) { return v / SCENE.fps; }); }
                    else { applyTrack(trp, L.tm); }
                }
                setTiming(lyr, L["in"], L.out);
                var T = lyr.property("ADBE Transform Group");
                var anchor = L.anchor || [0, 0];
                if (L.type === "text") { anchor = [0, -HB[L.name] / 2]; }
                T.property("ADBE Anchor Point").setValue(anchor);
                if (L.xoff && isTrack(L.xoff) && !isTrack(L.pos)) {
                    var base = L.pos;
                    applyTrack(T.property("ADBE Position"), L.xoff, function (v) { return addTrack2(base, v); });
                } else {
                    applyTrack(T.property("ADBE Position"), L.pos);
                }
                applyTrack(T.property("ADBE Scale"), L.scale);
                applyTrack(T.property("ADBE Rotate Z"), L.rot);
                applyTrack(T.property("ADBE Opacity"), L.op);
                if (L.ae_left_of) { T.property("ADBE Position").expression = leftOfExpression(L.ae_left_of); }
                if (L.ae_edge_of) { T.property("ADBE Position").expression = edgeOfExpression(L.ae_edge_of); }
                if (L.ae_pill_for) {
                    var rectSize = lyr.property("ADBE Root Vectors Group").property(1).property("ADBE Vectors Group").property(1).property("ADBE Vector Rect Size");
                    var fw = isTrack(L.items[0].size) ? L.items[0].size.k[L.items[0].size.k.length - 1][1][0] : L.items[0].size[0];
                    rectSize.expression = pillExpression(L.ae_pill_for, fw);
                }
                addMasks(lyr, L);
                addEffects(lyr, L);
                if (L.light_sweep) {
                    try {
                        var ls = lyr.property("ADBE Effect Parade").addProperty("CC Light Sweep");
                        var cen = ls.property(1);
                        cen.setValueAtTime(L.light_sweep.t0, [L.light_sweep.x0 - 540, -HB[L.name] / 2]);
                        cen.setValueAtTime(L.light_sweep.t1, [L.light_sweep.x1 - 540, -HB[L.name] / 2]);
                        ls.property(2).setValue(-25);
                        ls.property(4).setValue(L.light_sweep.width);
                    } catch (els) { warn("CC Light Sweep not applied on " + L.name); }
                }
                if (L.blend === "multiply") { lyr.blendingMode = BlendingMode.MULTIPLY; }
                else if (L.blend === "screen") { lyr.blendingMode = BlendingMode.SCREEN; }
                else if (L.blend === "add") { lyr.blendingMode = BlendingMode.ADD; }
                if (L.type !== "null") { lyr.motionBlur = !!L.mb; }
                if (L.clip) { addClipMatte(comp, L, lyr, byName); }
            } catch (err) {
                warn("layer " + L.name + ": " + err.toString() + (err.line ? " (line " + err.line + ")" : ""));
            }
        }
        return comp;
    }

    var part1 = makeComp("PART1", "PART1 - footage + captions");
    var main = makeComp("MAIN", "MOTTI - Update V8.1 (MAIN)");
    buildComp("PART1");
    buildComp("MAIN");

    // audio: final mix on, stems off (for re-balancing)
    for (var s = META.audio.length - 1; s >= 0; s--) {
        var nm = META.audio[s];
        var al = main.layers.add(ITEMS.audio[nm]);
        al.name = "AUDIO " + nm.replace(".wav", "");
        al.audioEnabled = (nm === META.mainAudio);
        al.moveToEnd();
    }

    try { main.openInViewer(); } catch (eo) {}
    app.endUndoGroup();

    var msg = "MOTTI V8.1 built.\nMain comp: \"MOTTI - Update V8.1 (MAIN)\"\nFonts: " + FONT.H + " / " + FONT.L;
    if (LOG.length) {
        msg += "\n\nNotes (" + LOG.length + "):\n" + LOG.slice(0, 12).join("\n");
        try {
            var lf = new File(ROOT.fsName + "/build_log.txt");
            lf.encoding = "UTF-8"; lf.open("w"); lf.write(LOG.join("\n")); lf.close();
            msg += "\n\nFull log: build_log.txt";
        } catch (el) {}
    }
    alert(msg);
})();
