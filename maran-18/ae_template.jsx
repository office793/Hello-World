// =====================================================================================
//  Yeshivat Maran - "18 NIS" typography ending  |  After Effects project builder
//  1080x1920 @ 29.97 fps, 15.5 s.  Generated from scene.json (same source as preview.mp4).
//
//  How to run:  1. Install the fonts in the "fonts" folder (right click > Install for all users).
//               2. After Effects 2020 or newer  ->  File > Scripts > Run Script File...
//                  and pick this file. Keep the "assets" folder next to it.
//  The script builds a new project and saves it next to itself as Maran_18.aep.
// =====================================================================================
(function Maran18Builder() {
    var SCENE = __SCENE__;
    var META = __META__;

    var LOG = [];
    function warn(msg) { LOG.push(msg); }

    var ROOT = File($.fileName).parent;
    function assetFile(rel) { return new File(ROOT.fsName + "/assets/" + rel); }

    // ------------------------------------------------------------------ fonts
    var FONT = {};
    var FONT_KEYS = [];
    for (var fk in SCENE.fonts) { if (SCENE.fonts.hasOwnProperty(fk)) { FONT[fk] = SCENE.fonts[fk].ps; FONT_KEYS.push(fk); } }
    var FONT_LABEL = { H: "Big words:", S: "Small words:", STAM: "מרן (STaM):", U: "Link (Latin):" };

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
        var w = new Window("dialog", "Maran 18 - fonts / פונטים");
        w.orientation = "column";
        w.alignChildren = ["fill", "top"];
        w.add("statictext", undefined,
            "PostScript names. Install the fonts from the 'fonts' folder first (then restart After Effects).",
            { multiline: true });
        var rows = {};
        var canSearch = false;
        try { canSearch = !!(app.fonts && app.fonts.allFonts); } catch (e0) {}
        function row(key) {
            var g = w.add("group");
            g.orientation = "row";
            var st = g.add("statictext", undefined, FONT_LABEL[key] || key);
            st.preferredSize.width = 120;
            var e = g.add("edittext", undefined, FONT[key]);
            e.characters = 28;
            var ok = g.add("statictext", undefined, fontExists(FONT[key]) ? "OK" : "missing");
            ok.preferredSize.width = 60;
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
        for (var i = 0; i < FONT_KEYS.length; i++) { row(FONT_KEYS[i]); }
        var bg = w.add("group");
        bg.alignment = "right";
        bg.add("button", undefined, "Cancel", { name: "cancel" });
        bg.add("button", undefined, "Build", { name: "ok" });
        if (w.show() !== 1) { return false; }
        for (var k = 0; k < FONT_KEYS.length; k++) {
            var key = FONT_KEYS[k];
            FONT[key] = rows[key].text;
            if (!fontExists(FONT[key])) { warn("Font not found: " + FONT[key] + " (install it from the fonts folder)"); }
        }
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

    function isStatic(tr, v) { return !isTrack(tr) && tr === v; }

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

    function setMatte(lyr, matteLayer) {
        // the matte sits directly above the layer, so both the new and the legacy API agree
        if (typeof lyr.setTrackMatte === "function") { lyr.setTrackMatte(matteLayer, TrackMatteType.ALPHA); }
        else { lyr.trackMatteType = TrackMatteType.ALPHA; }
        matteLayer.enabled = false;
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

    function setPercentParam(p, pct) {
        var mx = 100;
        try { if (p.hasMax && p.maxValue > 100) { mx = p.maxValue; } } catch (e) {}
        p.setValue(pct / 100 * mx);
    }

    function ease(name, p) {
        if (name === "inOutSine") { return -(Math.cos(Math.PI * p) - 1) / 2; }
        return p;
    }

    // ------------------------------------------------------------------ easing for expressions
    var EASE_EXPR = {
        linear: "p",
        outExpo: "(p>=1?1:1-Math.pow(2,-10*p))",
        outCubic: "(1-Math.pow(1-p,3))",
        inCubic: "(p*p*p)",
        outQuad: "(1-(1-p)*(1-p))",
        inOutCubic: "(p<0.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2)",
        inOutSine: "(-(Math.cos(Math.PI*p)-1)/2)",
        outBack: "(1+2.70158*Math.pow(p-1,3)+1.70158*Math.pow(p-1,2))"
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
        if (s.starts) {
            e += "var S = [" + s.starts.join(",") + "];\n";
            e += "var t1 = S[Math.min(k, S.length - 1)];\n";
        } else {
            e += "var t1 = t0 + k * st;\n";
        }
        e += "var p = dur > 0 ? Math.min(Math.max((time - t1) / dur, 0), 1) : (time >= t1 ? 1 : 0);\n";
        e += "var e = " + (EASE_EXPR[s.ease] || "p") + ";\n";
        e += (s.mode === "in") ? "(1 - e) * 100;" : "e * 100;";
        return e;
    }

    // ------------------------------------------------------------------ project
    if (!chooseFonts()) { return; }
    if (app.project && app.project.numItems > 0) {
        if (!app.newProject()) { return; }   // "save changes?" prompt was cancelled
    } else if (!app.project) {
        app.newProject();
    }
    app.beginUndoGroup("Maran 18 build");
    var proj = app.project;
    var top = proj.items.addFolder("Maran_18");
    var fAssets = proj.items.addFolder("assets");
    fAssets.parentFolder = top;

    function importAsset(rel) {
        var f = assetFile(rel);
        if (!f.exists) {
            f = File.openDialog("Locate " + rel);
            if (!f) { throw new Error("Missing asset: " + rel); }
        }
        var it = proj.importFile(new ImportOptions(f));
        it.parentFolder = fAssets;
        return it;
    }

    var ITEMS = { images: {}, audio: {} };
    for (var ii = 0; ii < META.images.length; ii++) { ITEMS.images[META.images[ii]] = importAsset(META.images[ii]); }
    for (var ai = 0; ai < META.audio.length; ai++) { ITEMS.audio[META.audio[ai]] = importAsset("audio/" + META.audio[ai]); }

    var spec = SCENE.comps[SCENE.main];
    var comp = proj.items.addComp(META.compName, spec.w, spec.h, 1, spec.dur, spec.fps);
    comp.parentFolder = top;
    comp.bgColor = [0.208, 0.039, 0.106];
    comp.motionBlur = true;
    try { comp.shutterAngle = 180; comp.shutterPhase = -90; } catch (e) {}
    try { comp.motionBlurSamplesPerFrame = 16; comp.motionBlurAdaptiveSampleLimit = 128; } catch (e2) {}

    // text metrics of the chosen fonts (base height for visual centring)
    var METRIC = {};
    var HB = {};
    function textMetric(fontKey, size, latin) {
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
        if (RTL_OK === null) {
            RTL_OK = ok;
            if (!ok) { warn("Paragraph direction could not be set from script: in Preferences > Type choose 'South Asian and Middle Eastern' and rebuild if Hebrew looks reversed."); }
        }
    }

    function makeText(L) {
        var lyr = comp.layers.addText(L.text);
        var tp = lyr.property("ADBE Text Properties").property("ADBE Text Document");
        var td = tp.value;
        try { td.resetCharStyle(); td.resetParagraphStyle(); } catch (e) {}
        try { td.font = FONT[L.font]; } catch (e1) { warn("font " + FONT[L.font] + " on " + L.name); }
        td.fontSize = L.size;
        td.applyFill = true;
        td.fillColor = hexRGB(L.grad ? "#FFFFFF" : L.fill);
        td.applyStroke = false;
        td.justification = L.just === "right" ? ParagraphJustification.RIGHT_JUSTIFY :
            (L.just === "left" ? ParagraphJustification.LEFT_JUSTIFY : ParagraphJustification.CENTER_JUSTIFY);
        td.tracking = L.track || 0;
        if (L.dir === "rtl") { setRTL(td); }
        td.text = L.text;
        tp.setValue(td);
        if (L.size >= 100) {
            var r = lyr.sourceRectAtTime(L["in"], false);
            if (r.width > META.maxTextWidth) {
                var d2 = tp.value; d2.fontSize = Math.floor(L.size * META.maxTextWidth / r.width); tp.setValue(d2);
                warn("Resized '" + L.name + "' to fit the frame (" + d2.fontSize + " px).");
            }
        }
        HB[L.name] = textMetric(L.font, tp.value.fontSize, L.dir === "ltr");
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
            if (P.blur) { AN().property("ADBE Text Animator Properties").addProperty("ADBE Text Blur").setValue([P.blur * META.blurScale, P.blur * META.blurScale]); }
        }
        return lyr;
    }

    // gold gradient: a ramp solid parented to the text layer and shown through the text's alpha
    function goldFill(L, lyr) {
        var g = L.grad;
        var sw = 2400, sh = Math.round((g.y1 - g.y0) + L.size * 1.6);
        var mid = (g.y0 + g.y1) / 2;
        var s = comp.layers.addSolid([1, 1, 1], L.name + " gold", sw, sh, 1, comp.duration);
        s.parent = lyr;
        var T = s.property("ADBE Transform Group");
        T.property("ADBE Anchor Point").setValue([sw / 2, sh / 2]);
        T.property("ADBE Position").setValue([0, mid]);
        T.property("ADBE Scale").setValue([100, 100]);
        T.property("ADBE Rotate Z").setValue(0);
        var r = s.property("ADBE Effect Parade").addProperty("ADBE Ramp");
        r.property("ADBE Ramp-0001").setValue([sw / 2, sh / 2 + (g.y0 - mid)]);
        r.property("ADBE Ramp-0002").setValue(hexRGBA(g.c0));
        r.property("ADBE Ramp-0003").setValue([sw / 2, sh / 2 + (g.y1 - mid)]);
        r.property("ADBE Ramp-0004").setValue(hexRGBA(g.c1));
        r.property("ADBE Ramp-0005").setValue(1);
        setTiming(s, L["in"], L.out);
        s.moveAfter(lyr);
        s.motionBlur = !!L.mb;
        setMatte(s, lyr);
        return { layer: s, sw: sw, sh: sh, mid: mid };
    }

    function lightSweep(target, L, cx0, cy0) {
        var ls = L.light_sweep;
        try {
            var fx = target.property("ADBE Effect Parade").addProperty("CC Light Sweep");
            var cen = fx.property(1);
            var n = Math.max(2, Math.round((ls.t1 - ls.t0) * SCENE.fps));
            var times = [], vals = [];
            for (var k = 0; k <= n; k++) {
                var p = k / n;
                times.push(ls.t0 + (ls.t1 - ls.t0) * p);
                vals.push([cx0 + ls.x0 + (ls.x1 - ls.x0) * ease("inOutSine", p), cy0]);
            }
            cen.setValuesAtTimes(times, vals);
            fx.property(2).setValue(-25);
            fx.property(4).setValue(ls.width);
            fx.property(5).setValue(Math.round(60 * (ls.op || 0.85)));
            try { fx.property(8).setValue([1, 0.97, 0.88, 1]); } catch (ec) {}
        } catch (e) { warn("CC Light Sweep not applied on " + L.name); }
    }

    function addShapeItems(lyr, items) {
        var glow = 0;
        for (var i = 0; i < items.length; i++) {
            var it = items[i];
            var g = lyr.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
            g.name = it.kind + "_" + (i + 1);
            var gi = g.propertyIndex;
            var G = function () { return lyr.property("ADBE Root Vectors Group").property(gi); };
            var V = function () { return G().property("ADBE Vectors Group"); };
            if (it.kind === "rect") {
                var rc = V().addProperty("ADBE Vector Shape - Rect");
                applyTrack(rc.property("ADBE Vector Rect Size"), it.size);
                rc.property("ADBE Vector Rect Position").setValue(it.c);
                rc.property("ADBE Vector Rect Roundness").setValue(it.r || 0);
            } else if (it.kind === "ellipse") {
                var el = V().addProperty("ADBE Vector Shape - Ellipse");
                applyTrack(el.property("ADBE Vector Ellipse Size"), it.size);
                el.property("ADBE Vector Ellipse Position").setValue(it.c);
            } else if (it.kind === "glow") {
                var eg = V().addProperty("ADBE Vector Shape - Ellipse");
                eg.property("ADBE Vector Ellipse Size").setValue([0.56 * it.size[0], 0.56 * it.size[1]]);
                eg.property("ADBE Vector Ellipse Position").setValue(it.c);
                glow = Math.max(glow, 0.10 * Math.min(it.size[0], it.size[1]) * META.blurScale);
            } else if (it.kind === "path") {
                var shapes = svgToShapes(it.d);
                for (var s = 0; s < shapes.length; s++) {
                    V().addProperty("ADBE Vector Shape - Group").property("ADBE Vector Shape").setValue(shapes[s]);
                }
            }
            if (it.trim && !(isStatic(it.trim.s, 0) && isStatic(it.trim.e, 100))) {
                var tr = V().addProperty("ADBE Vector Filter - Trim");
                applyTrack(tr.property("ADBE Vector Trim Start"), it.trim.s);
                applyTrack(tr.property("ADBE Vector Trim End"), it.trim.e);
            }
            if (it.stroke) {
                var st = V().addProperty("ADBE Vector Graphic - Stroke");
                st.property("ADBE Vector Stroke Color").setValue(hexRGBA(it.stroke));
                applyTrack(st.property("ADBE Vector Stroke Width"), it.sw);
                st.property("ADBE Vector Stroke Line Cap").setValue(it.cap === "butt" ? 1 : 2);
                st.property("ADBE Vector Stroke Line Join").setValue(2);
            }
            if (it.fill || it.kind === "glow") {
                var fl = V().addProperty("ADBE Vector Graphic - Fill");
                fl.property("ADBE Vector Fill Color").setValue(hexRGBA(it.fill));
                if (it.evenodd) { fl.property("ADBE Vector Fill Rule").setValue(2); }
            }
            if (it.op !== undefined) {
                applyTrack(G().property("ADBE Vector Transform Group").property("ADBE Vector Group Opacity"), it.op);
            }
        }
        if (glow > 0) {
            var b = lyr.property("ADBE Effect Parade").addProperty("ADBE Gaussian Blur 2");
            b.property("ADBE Gaussian Blur 2-0001").setValue(glow);
            try { b.property("ADBE Gaussian Blur 2-0003").setValue(1); } catch (e3) {}
        }
    }

    function addEffects(lyr, L) {
        var fx = L.fx || [];
        for (var i = 0; i < fx.length; i++) {
            var e = fx[i];
            try {
                if (e.type === "blur") {
                    if (isStatic(e.amt, 0)) { continue; }
                    var b = lyr.property("ADBE Effect Parade").addProperty("ADBE Gaussian Blur 2");
                    applyTrack(b.property("ADBE Gaussian Blur 2-0001"), e.amt, function (v) { return v * META.blurScale; });
                    try { b.property("ADBE Gaussian Blur 2-0003").setValue(1); } catch (e1) {}
                } else if (e.type === "shadow") {
                    var d = lyr.property("ADBE Effect Parade").addProperty("ADBE Drop Shadow");
                    d.property("ADBE Drop Shadow-0001").setValue(hexRGBA(e.color));
                    setPercentParam(d.property("ADBE Drop Shadow-0002"), e.op);
                    d.property("ADBE Drop Shadow-0003").setValue(e.dir);
                    d.property("ADBE Drop Shadow-0004").setValue(e.dist);
                    d.property("ADBE Drop Shadow-0005").setValue(e.soft);
                }
            } catch (err) { warn("effect " + e.type + " on " + L.name + ": " + err.toString()); }
        }
    }

    var byName = {};
    var mattes = [];
    for (var li = 0; li < spec.layers.length; li++) {
        var L = spec.layers[li];
        var lyr = null;
        try {
            if (L.type === "null") {
                lyr = comp.layers.addNull(comp.duration);
            } else if (L.type === "solid") {
                lyr = comp.layers.addSolid(hexRGB(L.color), L.name, L.w, L.h, 1, comp.duration);
            } else if (L.type === "image") {
                lyr = comp.layers.add(ITEMS.images[L.src], comp.duration);
            } else if (L.type === "text") {
                lyr = makeText(L);
            } else if (L.type === "shape") {
                lyr = comp.layers.addShape();
                addShapeItems(lyr, L.items);
            }
            lyr.name = L.name;
            byName[L.name] = lyr;
            if (L.parent) { setParent(lyr, byName[L.parent]); }
            setTiming(lyr, L["in"], L.out);
            var T = lyr.property("ADBE Transform Group");
            var anchor = L.anchor || [0, 0];
            if (L.type === "text") { anchor = [0, -HB[L.name] / 2]; }
            T.property("ADBE Anchor Point").setValue(anchor);
            applyTrack(T.property("ADBE Position"), L.pos);
            applyTrack(T.property("ADBE Scale"), L.scale);
            applyTrack(T.property("ADBE Rotate Z"), L.rot);
            applyTrack(T.property("ADBE Opacity"), L.op);
            addEffects(lyr, L);
            if (L.blend === "screen") { lyr.blendingMode = BlendingMode.SCREEN; }
            else if (L.blend === "add") { lyr.blendingMode = BlendingMode.ADD; }
            if (L.type !== "null") { lyr.motionBlur = !!L.mb; }
            if (L.type === "text" && L.grad) {
                var gs = goldFill(L, lyr);
                if (L.light_sweep) { lightSweep(gs.layer, L, gs.sw / 2, gs.sh / 2 + (-0.35 * L.size - gs.mid)); }
            } else if (L.type === "text" && L.light_sweep) {
                lightSweep(lyr, L, 0, -0.35 * L.size);
            }
            if (L.matte) { mattes.push([lyr, L.matte]); }
        } catch (err) {
            warn("layer " + L.name + ": " + err.toString() + (err.line ? " (line " + err.line + ")" : ""));
        }
    }
    for (var mi = 0; mi < mattes.length; mi++) {
        try { setMatte(mattes[mi][0], byName[mattes[mi][1]]); }
        catch (em) { warn("matte for " + mattes[mi][0].name + ": " + em.toString()); }
    }

    // audio: final mix on, stems off (for re-balancing)
    for (var s = META.audio.length - 1; s >= 0; s--) {
        var nm = META.audio[s];
        var al = comp.layers.add(ITEMS.audio[nm]);
        al.name = "AUDIO " + nm.replace(".wav", "");
        al.audioEnabled = (nm === META.mainAudio);
        al.moveToEnd();
    }

    try { comp.openInViewer(); } catch (eo) {}
    app.endUndoGroup();

    var saved = "";
    try {
        var outF = new File(ROOT.fsName + "/Maran_18.aep");
        for (var n = 2; outF.exists && n < 100; n++) { outF = new File(ROOT.fsName + "/Maran_18_" + n + ".aep"); }
        proj.save(outF);
        saved = outF.fsName;
    } catch (es) { warn("could not save the project: " + es.toString()); }

    var msg = "Maran 18 built.\nComp: \"" + META.compName + "\"";
    if (saved) { msg += "\nSaved: " + saved; }
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
