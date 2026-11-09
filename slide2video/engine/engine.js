// Study-video engine: a pure function of time t -> one 1920x1080 canvas frame.
// A chapter page loads timing.js (window.TIMING, from lv/narrate.py), this file, then scenes.js,
// which calls Engine.assets({...}) and scene(id, draw, opts) once per scene in script.json.
// draw(g, t, s): g = 2D context, t = seconds since this scene started, s = scene info:
//   s.dur, s.speak (narration start, local s), s.cue('word', n) -> local time the nth
//   occurrence of that word is spoken, s.p(a, d, ease) -> 0..1 progress from local a over d s.
(function () {
  const W = 1920, H = 1080, XFADE = 0.45;
  const T = window.TIMING || { duration: 10, scenes: [], chapter: '', title: '' };
  const canvas = document.getElementById('c');
  const g = canvas.getContext('2d');
  const off = document.createElement('canvas'); off.width = W; off.height = H;
  const og = off.getContext('2d');
  const scenes = {}, imgs = {}, loads = [];
  const frameCache = new Map(); let pending = 0, waiters = [];

  // ---------- easing / math ----------
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const lerp = (a, b, k) => a + (b - a) * k;
  const E = {
    lin: k => k,
    out: k => 1 - Math.pow(1 - k, 3),
    in: k => k * k * k,
    inOut: k => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2),
    back: k => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2); },
    elastic: k => (k === 0 || k === 1 ? k : Math.pow(2, -10 * k) * Math.sin((k * 10 - 0.75) * (2 * Math.PI / 3)) + 1),
  };
  const P = (t, a, d = 0.6, ease = E.out) => ease(clamp((t - a) / d));
  function rng(seed) { let s = seed >>> 0 || 1; return () => { s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; }; }
  const noise = (i, t, f = 1) => Math.sin(t * f * 1.3 + i * 12.9898) * 0.5 + Math.sin(t * f * 0.71 + i * 78.233) * 0.35 + Math.sin(t * f * 2.17 + i * 3.7) * 0.15;

  // ---------- palette ----------
  const C = {
    navy: '#0B2545', deep: '#13315C', sea: '#134E6F', teal: '#1FA7A0', aqua: '#7FE0D6', foam: '#E8F7F5',
    sand: '#F6EFE2', paper: '#FBF8F1', ink: '#16212E', coral: '#FF6B57', sun: '#FFC145', leaf: '#3FB36B',
    purple: '#8E7DFF', pink: '#FF8FB1', grey: '#8A97A6', white: '#FFFFFF', salt: '#F2F2F2', water: '#4FC3F7',
  };
  // Colour roles the ready-made widgets use; Engine.theme() sets them. Unthemed, they are the original palette.
  Object.assign(C, { head: C.navy, main: C.teal, accent: C.coral, glow: C.aqua, soft: C.foam, note: C.sea });
  const FONT = '"Avenir Next", "Nunito", "Helvetica Neue", Arial, sans-serif';
  const HAND = '"Patrick Hand", "Avenir Next", sans-serif';

  // ---------- text ----------
  // Inline markup: *word* = accent color (opts.accent), _word_ = bold.
  function parseRich(str) {
    const out = []; let acc = false, bold = false, buf = '';
    for (const ch of String(str)) {
      if (ch === '*' || ch === '_') { if (buf) out.push({ s: buf, acc, bold }); buf = ''; if (ch === '*') acc = !acc; else bold = !bold; }
      else buf += ch;
    }
    if (buf) out.push({ s: buf, acc, bold });
    return out;
  }
  function fontStr(o, bold) { return `${o.italic ? 'italic ' : ''}${bold ? Math.max(o.weight || 500, 700) : (o.weight || 500)} ${o.size || 48}px ${o.font || FONT}`; }
  function wrapRich(ctx, str, o) {
    const runs = parseRich(str), words = [];
    for (const r of runs) for (const [i, w] of r.s.split(/(\s+)/).entries()) if (w) words.push({ ...r, s: w });
    const lines = [[]]; let lw = 0; const maxW = o.maxW || 1e9;
    for (const w of words) {
      ctx.font = fontStr(o, w.bold); const ww = ctx.measureText(w.s).width;
      if (/^\s+$/.test(w.s)) { if (lines[lines.length - 1].length) { lines[lines.length - 1].push({ ...w, w: ww }); lw += ww; } continue; }
      if (lw + ww > maxW && lines[lines.length - 1].length) { const L = lines[lines.length - 1]; while (L.length && /^\s+$/.test(L[L.length - 1].s)) L.pop(); lines.push([]); lw = 0; }
      lines[lines.length - 1].push({ ...w, w: ww }); lw += ww;
    }
    return lines.map(L => { while (L.length && /^\s+$/.test(L[L.length - 1].s)) L.pop(); return { runs: L, w: L.reduce((a, r) => a + r.w, 0) }; });
  }
  function text(ctx, str, x, y, o = {}) {
    o = { size: 48, color: C.ink, align: 'left', lh: 1.22, alpha: 1, accent: C.accent, ...o };
    if (o.alpha <= 0) return 0;
    ctx.save(); ctx.globalAlpha *= o.alpha; ctx.textBaseline = 'alphabetic';
    if (o.shadow) { ctx.shadowColor = o.shadow === true ? 'rgba(0,0,0,0.35)' : o.shadow; ctx.shadowBlur = 18; ctx.shadowOffsetY = 4; }
    const lines = wrapRich(ctx, str, o); const lh = o.size * o.lh;
    lines.forEach((L, i) => {
      let cx = o.align === 'center' ? x - L.w / 2 : o.align === 'right' ? x - L.w : x;
      const cy = y + o.size * 0.82 + i * lh;
      for (const r of L.runs) { ctx.font = fontStr(o, r.bold); ctx.fillStyle = r.acc ? o.accent : o.color; ctx.fillText(r.s, cx, cy); cx += r.w; }
    });
    ctx.restore();
    return lines.length * lh;
  }
  function measure(ctx, str, o = {}) { o = { size: 48, lh: 1.22, ...o }; const L = wrapRich(ctx, str, o); return { w: Math.max(0, ...L.map(l => l.w)), h: L.length * o.size * o.lh, lines: L.length }; }

  // ---------- shapes ----------
  function rr(ctx, x, y, w, h, r) { r = Math.min(r, w / 2, h / 2); ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
  function card(ctx, x, y, w, h, o = {}) {
    o = { fill: C.white, r: 28, alpha: 1, shadow: true, ...o }; if (o.alpha <= 0) return;
    ctx.save(); ctx.globalAlpha *= o.alpha;
    if (o.shadow) { ctx.shadowColor = 'rgba(5,20,40,0.28)'; ctx.shadowBlur = 30; ctx.shadowOffsetY = 10; }
    rr(ctx, x, y, w, h, o.r); ctx.fillStyle = o.fill; ctx.fill(); ctx.shadowColor = 'transparent';
    if (o.stroke) { ctx.lineWidth = o.lw || 4; ctx.strokeStyle = o.stroke; ctx.stroke(); }
    ctx.restore();
  }
  function circle(ctx, x, y, r, fill, o = {}) { ctx.save(); ctx.globalAlpha *= (o.alpha ?? 1); ctx.beginPath(); ctx.arc(x, y, Math.max(0, r), 0, Math.PI * 2); if (fill) { ctx.fillStyle = fill; ctx.fill(); } if (o.stroke) { ctx.lineWidth = o.lw || 3; ctx.strokeStyle = o.stroke; ctx.stroke(); } ctx.restore(); }
  // Arrow from (x1,y1) to (x2,y2); prog draws it progressively; bend curves it (px of sideways offset).
  function arrow(ctx, x1, y1, x2, y2, o = {}) {
    o = { color: C.ink, w: 8, head: 28, prog: 1, bend: 0, alpha: 1, dash: null, ...o }; if (o.prog <= 0 || o.alpha <= 0) return;
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2, dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy) || 1;
    const cx = mx - dy / L * o.bend, cy = my + dx / L * o.bend;
    const pt = k => [(1 - k) * (1 - k) * x1 + 2 * (1 - k) * k * cx + k * k * x2, (1 - k) * (1 - k) * y1 + 2 * (1 - k) * k * cy + k * k * y2];
    ctx.save(); ctx.globalAlpha *= o.alpha; ctx.strokeStyle = o.color; ctx.fillStyle = o.color; ctx.lineWidth = o.w; ctx.lineCap = 'round';
    if (o.dash) ctx.setLineDash(o.dash);
    const N = 40, end = o.prog; ctx.beginPath(); for (let i = 0; i <= N; i++) { const [px, py] = pt(end * i / N); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }
    const [ex, ey] = pt(end), [bx, by] = pt(Math.max(0, end - 0.02)); const ang = Math.atan2(ey - by, ex - bx);
    const hx = ex - Math.cos(ang) * o.head * 0.6, hy = ey - Math.sin(ang) * o.head * 0.6;
    ctx.stroke(); ctx.setLineDash([]);
    if (o.head > 0) { ctx.beginPath(); ctx.moveTo(ex + Math.cos(ang) * o.head * 0.25, ey + Math.sin(ang) * o.head * 0.25); ctx.lineTo(hx - Math.cos(ang + 1.57) * o.head * 0.55, hy - Math.sin(ang + 1.57) * o.head * 0.55); ctx.lineTo(hx + Math.cos(ang + 1.57) * o.head * 0.55, hy + Math.sin(ang + 1.57) * o.head * 0.55); ctx.closePath(); ctx.fill(); }
    ctx.restore();
  }
  function line(ctx, x1, y1, x2, y2, o = {}) { o = { color: C.ink, w: 4, prog: 1, alpha: 1, ...o }; ctx.save(); ctx.globalAlpha *= o.alpha; ctx.strokeStyle = o.color; ctx.lineWidth = o.w; ctx.lineCap = 'round'; if (o.dash) ctx.setLineDash(o.dash); ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(lerp(x1, x2, o.prog), lerp(y1, y2, o.prog)); ctx.stroke(); ctx.restore(); }
  function check(ctx, x, y, s, prog = 1, color = C.leaf) { if (prog <= 0) return; ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = s * 0.16; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.beginPath(); const pts = [[x - s * 0.4, y], [x - s * 0.1, y + s * 0.3], [x + s * 0.45, y - s * 0.35]]; const k = prog * 2; ctx.moveTo(...pts[0]); if (k < 1) ctx.lineTo(lerp(pts[0][0], pts[1][0], k), lerp(pts[0][1], pts[1][1], k)); else { ctx.lineTo(...pts[1]); ctx.lineTo(lerp(pts[1][0], pts[2][0], k - 1), lerp(pts[1][1], pts[2][1], k - 1)); } ctx.stroke(); ctx.restore(); }
  function cross(ctx, x, y, s, prog = 1, color = C.coral) { if (prog <= 0) return; const k = clamp(prog * 2), k2 = clamp(prog * 2 - 1); line(ctx, x - s / 2, y - s / 2, x + s / 2, y + s / 2, { color, w: s * 0.16, prog: k }); if (k2 > 0) line(ctx, x + s / 2, y - s / 2, x - s / 2, y + s / 2, { color, w: s * 0.16, prog: k2 }); }

  // ---------- images & clips ----------
  function assets(map) {
    for (const [k, src] of Object.entries(map)) {
      const im = new Image(); imgs[k] = im;
      loads.push(new Promise(ok => { im.onload = ok; im.onerror = () => { console.error('asset failed: ' + src); ok(); }; }));
      im.src = src;
    }
  }
  function drawImg(ctx, im, x, y, w, h, o = {}) {
    if (!im || !im.naturalWidth) { ctx.save(); ctx.fillStyle = '#ccd'; ctx.fillRect(x, y, w, h); ctx.restore(); return; }
    o = { fit: 'cover', alpha: 1, r: 0, zoom: 1, panX: 0, panY: 0, ...o }; if (o.alpha <= 0) return;
    const iw = im.naturalWidth, ih = im.naturalHeight;
    let s = o.fit === 'cover' ? Math.max(w / iw, h / ih) : Math.min(w / iw, h / ih); s *= o.zoom;
    const dw = iw * s, dh = ih * s; const dx = x + (w - dw) / 2 + o.panX * Math.max(0, dw - w) / 2, dy = y + (h - dh) / 2 + o.panY * Math.max(0, dh - h) / 2;
    ctx.save(); ctx.globalAlpha *= o.alpha;
    if (o.shadow) { ctx.save(); ctx.shadowColor = 'rgba(0,0,0,0.3)'; ctx.shadowBlur = 30; ctx.shadowOffsetY = 10; rr(ctx, o.fit === 'cover' ? x : dx, o.fit === 'cover' ? y : dy, o.fit === 'cover' ? w : dw, o.fit === 'cover' ? h : dh, o.r); ctx.fillStyle = o.bgFill || '#fff'; ctx.fill(); ctx.restore(); }
    if (o.r || o.fit === 'cover') { rr(ctx, o.fit === 'cover' ? x : dx, o.fit === 'cover' ? y : dy, o.fit === 'cover' ? w : dw, o.fit === 'cover' ? h : dh, o.r); ctx.clip(); }
    ctx.drawImage(im, dx, dy, dw, dh); ctx.restore();
  }
  const warned = new Set();
  function img(ctx, key, x, y, w, h, o) {
    if (!(key in imgs) && !warned.has(key)) { warned.add(key); console.error(`asset failed: no Engine.assets() entry for "${key}"`); }
    drawImg(ctx, imgs[key], x, y, w, h, o);
  }
  // Video clip as a JPEG frame sequence: dir/0001.jpg..; loaded lazily, renderer waits for pending loads.
  function clip(ctx, dir, n, t, x, y, w, h, o = {}) {
    const fps = o.fps || 24; let f = Math.floor(Math.max(0, t) * fps); f = o.loop ? f % n : Math.min(n - 1, f);
    const src = `${dir}/${String(f + 1).padStart(4, '0')}.jpg`;
    let im = frameCache.get(src);
    if (!im) {
      im = new Image(); frameCache.set(src, im); pending++;
      im.onload = im.onerror = e => { if (e.type === 'error') console.error('asset failed: ' + src); pending--; if (!pending) { waiters.forEach(r => r()); waiters = []; } };
      im.src = src;
      if (frameCache.size > 120) { const k = frameCache.keys().next().value; frameCache.delete(k); }
    }
    drawImg(ctx, im, x, y, w, h, o);
  }

  // ---------- backgrounds ----------
  // bg(g, kind, t): a named background, or 'title' / 'dark' / 'light' for the chapter's look (Engine.theme).
  // Without Engine.theme it works as it always did: the five original names, and the ocean for any other name.
  function bg(ctx, kind, t = 0) { paint(ctx, resolveBg(kind), t); }
  function resolveBg(kind) {
    if (!THEMED) {
      if (LEGACY_BG.includes(kind)) return kind;
      if (!warnedBg.has(kind)) { warnedBg.add(kind); console.warn(`bg('${kind}') needs Engine.theme(...) at the top of scenes.js; drawn as 'ocean'`); }
      return 'ocean';
    }
    if (Object.hasOwn(LOOK, kind)) return LOOK[kind];
    if (LEGACY_BG.includes(kind) || Object.hasOwn(MOTIFS, kind)) return kind;
    throw new Error(`bg: unknown background "${kind}"; use 'light', 'dark', or one of ${[...LIGHT_BG, ...DARK_BG].join(', ')}`);
  }
  function paint(ctx, kind, t = 0) {
    if (Object.hasOwn(MOTIFS, kind)) { MOTIFS[kind](ctx, t); return; }
    if (kind === 'paper') { ctx.fillStyle = C.paper; ctx.fillRect(0, 0, W, H); dotsGrid(ctx, 'rgba(19,49,92,0.07)'); return; }
    if (kind === 'sand') { ctx.fillStyle = C.sand; ctx.fillRect(0, 0, W, H); return; }
    if (kind === 'lab') { const gr = ctx.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, '#F3F7FA'); gr.addColorStop(1, '#DCE7EE'); ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H); dotsGrid(ctx, 'rgba(19,49,92,0.06)'); return; }
    // ocean / deep: gradient + light rays + drifting particles
    const gr = ctx.createLinearGradient(0, 0, 0, H);
    if (TINT) { gr.addColorStop(0, TINT[0]); gr.addColorStop(1, TINT[1]); }
    else if (kind === 'deep') { gr.addColorStop(0, '#0E3A5C'); gr.addColorStop(1, '#061325'); }
    else { gr.addColorStop(0, '#1C7FA6'); gr.addColorStop(0.55, '#0F4C75'); gr.addColorStop(1, '#0A2540'); }
    ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H);
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 6; i++) {
      const x0 = 200 + i * 320 + Math.sin(t * 0.25 + i) * 60, a = 0.035 + 0.02 * Math.sin(t * 0.6 + i * 2);
      const rg = ctx.createLinearGradient(0, 0, 0, H * 0.9); rg.addColorStop(0, `rgba(180,240,255,${a})`); rg.addColorStop(1, 'rgba(180,240,255,0)');
      ctx.fillStyle = rg; ctx.beginPath(); ctx.moveTo(x0 - 40, 0); ctx.lineTo(x0 + 40, 0); ctx.lineTo(x0 + 260, H); ctx.lineTo(x0 + 60, H); ctx.closePath(); ctx.fill();
    }
    ctx.restore();
    const r = rng(7);
    for (let i = 0; i < 60; i++) {
      const bx = r() * W, sp = 15 + r() * 40, by = (r() * H - t * sp) % H; const y = by < 0 ? by + H : by;
      circle(ctx, bx + Math.sin(t + i) * 10, y, 1.5 + r() * 3, `rgba(220,250,255,${0.15 + r() * 0.25})`);
    }
  }
  // ---------- looks: backgrounds and colours chosen for the deck's subject (Engine.theme) ----------
  // Unthemed, the title card is 'ocean', quizzes 'deep' and the recap 'paper', as before.
  const UNTHEMED = { title: 'ocean', dark: 'deep', light: 'paper' }, ROLE_KEYS = ['head', 'main', 'accent', 'glow', 'soft', 'note'];
  const LEGACY_BG = ['paper', 'sand', 'lab', 'ocean', 'deep'], LIGHT_BG = ['paper', 'sand', 'lab', 'grid', 'parchment', 'lined'];
  const DARK_BG = ['night', 'blueprint', 'sepia', 'stage', 'canopy', 'cosmos', 'ocean', 'deep'];
  const LOOK = { ...UNTHEMED }, warnedBg = new Set();
  let TINT = null, THEMED = false;  // TINT: [top, bottom] replaces the dark backgrounds' own gradient
  function gradient(ctx, top, bottom) { const [a, b] = TINT || [top, bottom]; const gr = ctx.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, a); gr.addColorStop(1, b); ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H); }
  function vignette(ctx, a = 0.45) { const rg = ctx.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, W * 0.75); rg.addColorStop(0, 'rgba(0,0,0,0)'); rg.addColorStop(1, `rgba(0,0,0,${a})`); ctx.fillStyle = rg; ctx.fillRect(0, 0, W, H); }
  function glowAt(ctx, x, y, r, rgb, a) { const rg = ctx.createRadialGradient(x, y, 0, x, y, r); rg.addColorStop(0, `rgba(${rgb},${a})`); rg.addColorStop(1, `rgba(${rgb},0)`); ctx.fillStyle = rg; ctx.fillRect(x - r, y - r, 2 * r, 2 * r); }
  function rules(ctx, step, color, o = {}) { ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = o.w || 1; ctx.beginPath(); if (!o.rowsOnly) for (let x = (o.x0 ?? step); x < W; x += step) { ctx.moveTo(x + 0.5, 0); ctx.lineTo(x + 0.5, H); } for (let y = (o.y0 ?? step); y < H; y += step) { ctx.moveTo(0, y + 0.5); ctx.lineTo(W, y + 0.5); } ctx.stroke(); ctx.restore(); }
  const MOTIFS = {
    // dark, for title cards, quizzes and dark scenes (white text)
    night(ctx, t) {  // any subject: calm ink-blue with slow soft lights
      gradient(ctx, '#232A45', '#0D1020'); const r = rng(11);
      for (let i = 0; i < 9; i++) { const x = r() * W + Math.sin(t * 0.12 + i) * 80, y = r() * H + Math.cos(t * 0.1 + i * 2) * 50; glowAt(ctx, x, y, 140 + r() * 160, '160,170,255', 0.05 + 0.03 * r()); }
      vignette(ctx, 0.4);
    },
    blueprint(ctx, t) {  // maths, engineering, technology: drafting grid with a slow light sweep
      gradient(ctx, '#1E4A8A', '#0D244A'); rules(ctx, 48, 'rgba(255,255,255,0.06)'); rules(ctx, 240, 'rgba(255,255,255,0.12)', { w: 2 });
      glowAt(ctx, (t * 60) % (W + 800) - 400, H * 0.4, 520, '150,200,255', 0.08); vignette(ctx, 0.35);
    },
    sepia(ctx, t) {  // history, geography, social studies: old-map brown with drifting dust
      gradient(ctx, '#4E3521', '#1D130A'); ctx.save(); ctx.strokeStyle = 'rgba(255,225,170,0.07)'; ctx.lineWidth = 2;
      for (let i = 1; i < 7; i++) { ctx.beginPath(); for (let x = 0; x <= W; x += 40) { const y = i * H / 7 + Math.sin(x / 260 + i * 1.7) * 26; x ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke(); }
      ctx.restore(); const r = rng(5);
      for (let i = 0; i < 50; i++) { const x = (r() * W + t * (6 + r() * 10)) % W, y = r() * H + Math.sin(t * 0.3 + i) * 8; circle(ctx, x, y, 1 + r() * 2, `rgba(255,220,160,${0.08 + r() * 0.12})`); }
      vignette(ctx, 0.5);
    },
    stage(ctx, t) {  // literature, drama, poetry, the arts: dark curtain with a swaying spotlight
      gradient(ctx, '#40122A', '#12050C'); const x = W / 2 + Math.sin(t * 0.3) * 120;
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; const rg = ctx.createLinearGradient(0, 0, 0, H); rg.addColorStop(0, 'rgba(255,230,190,0.13)'); rg.addColorStop(1, 'rgba(255,230,190,0.02)');
      ctx.fillStyle = rg; ctx.beginPath(); ctx.moveTo(x - 90, 0); ctx.lineTo(x + 90, 0); ctx.lineTo(x + 560, H); ctx.lineTo(x - 560, H); ctx.closePath(); ctx.fill(); ctx.restore();
      ctx.save(); ctx.fillStyle = 'rgba(0,0,0,0.12)'; for (let i = 0; i < 12; i++) { const fx = i * W / 12; ctx.fillRect(fx, 0, W / 24, H); } ctx.restore();
      vignette(ctx, 0.55);
    },
    canopy(ctx, t) {  // life science on land, health, ecology: deep green with dappled light
      gradient(ctx, '#21583A', '#0B2516'); const r = rng(3);
      for (let i = 0; i < 12; i++) { const x = r() * W + Math.sin(t * 0.2 + i) * 40, y = r() * H * 0.8 + Math.cos(t * 0.15 + i) * 30; glowAt(ctx, x, y, 90 + r() * 140, '210,255,170', 0.05 + 0.04 * r()); }
      for (let i = 0; i < 40; i++) { const x = (r() * W + t * (8 + r() * 14) + Math.sin(t + i) * 12) % W, y = (r() * H + t * (5 + r() * 8)) % H; circle(ctx, x, y, 1.5 + r() * 2, `rgba(230,255,200,${0.12 + r() * 0.15})`); }
      vignette(ctx, 0.4);
    },
    cosmos(ctx, t) {  // astronomy, physics, earth and space: night sky with twinkling stars
      gradient(ctx, '#17144A', '#040313'); glowAt(ctx, W * 0.72, H * 0.35, 620, '150,110,255', 0.10); glowAt(ctx, W * 0.2, H * 0.75, 480, '80,160,255', 0.07);
      const r = rng(9); for (let i = 0; i < 220; i++) { const x = r() * W, y = r() * H, b = 0.25 + 0.5 * r() * (0.6 + 0.4 * Math.sin(t * (1 + r() * 2) + i)); circle(ctx, x, y, 0.8 + r() * 1.8, `rgba(255,255,255,${b})`); }
    },
    // light, for content scenes and the recap (dark text)
    grid(ctx) { ctx.fillStyle = '#FBFCFE'; ctx.fillRect(0, 0, W, H); rules(ctx, 48, 'rgba(40,90,170,0.08)'); rules(ctx, 240, 'rgba(40,90,170,0.14)'); },
    parchment(ctx) { ctx.fillStyle = '#F6EDDA'; ctx.fillRect(0, 0, W, H); const rg = ctx.createRadialGradient(W / 2, H / 2, H * 0.4, W / 2, H / 2, W * 0.7); rg.addColorStop(0, 'rgba(160,110,50,0)'); rg.addColorStop(1, 'rgba(160,110,50,0.22)'); ctx.fillStyle = rg; ctx.fillRect(0, 0, W, H); },
    lined(ctx) { ctx.fillStyle = '#FFFDF6'; ctx.fillRect(0, 0, W, H); rules(ctx, 54, 'rgba(70,110,190,0.13)', { rowsOnly: true, y0: 216 }); ctx.fillStyle = 'rgba(215,80,80,0.28)'; ctx.fillRect(84, 0, 3, H); },
  };
  // Named looks: backgrounds plus colour roles. The style's guide says which fits which subject.
  const LOOKS = {
    ocean: { title: 'ocean', dark: 'deep', light: 'paper', head: '#0B2545', main: '#1FA7A0', accent: '#FF6B57', glow: '#7FE0D6', soft: '#E8F7F5', note: '#134E6F' },
    classroom: { title: 'night', dark: 'night', light: 'paper', head: '#1F2A44', main: '#3D6AE0', accent: '#D84A30', glow: '#FFD166', soft: '#E6E9F5', note: '#3D6AE0' },
    math: { title: 'blueprint', dark: 'blueprint', light: 'grid', head: '#1B3358', main: '#2B6DE0', accent: '#C2620F', glow: '#FFC94D', soft: '#DCE9FF', note: '#2B6DE0' },
    history: { title: 'sepia', dark: 'sepia', light: 'parchment', head: '#4A2C17', main: '#9A6630', accent: '#B23A48', glow: '#F2C879', soft: '#F5E6CC', note: '#7A4A21' },
    literature: { title: 'stage', dark: 'stage', light: 'lined', head: '#3B1832', main: '#8A3D7C', accent: '#C8553D', glow: '#F4C95D', soft: '#F6E3EC', note: '#8A3D7C' },
    life: { title: 'canopy', dark: 'canopy', light: 'lab', head: '#1E3D2B', main: '#257A4B', accent: '#C24E2E', glow: '#C5EBA0', soft: '#E7F5E1', note: '#257A4B' },
    space: { title: 'cosmos', dark: 'cosmos', light: 'lab', head: '#1B1F4B', main: '#5552D6', accent: '#C9472B', glow: '#B9B4FF', soft: '#E7E6FF', note: '#5552D6' },
  };
  // Engine.theme('history') or Engine.theme('math', { main: '#hex', accent: '#hex', tint: ['#top', '#bottom'] }):
  // call once at the top of scenes.js, before scene(). Sets the backgrounds bg('title'|'dark'|'light') and the
  // titleCard, quizQ, quizA and recap use, and the colour roles C.head, C.main, C.accent, C.glow, C.soft, C.note.
  // Each call replaces the previous look entirely; nothing changes unless the whole call is valid.
  function theme(name, over = {}) {
    if (name !== null && typeof name === 'object' && !Array.isArray(name)) { over = name; name = over.look; }
    const fail = msg => { throw new Error(`Engine.theme: ${msg}`); };
    if (typeof name !== 'string' || !Object.hasOwn(LOOKS, name)) fail(`unknown look "${name}"; use one of ${Object.keys(LOOKS).join(', ')}`);
    if (over === null || typeof over !== 'object' || Array.isArray(over)) fail('the second argument is { main, accent, tint }');
    for (const k of Object.keys(over)) if (!['look', 'title', 'dark', 'light', 'tint', ...ROLE_KEYS].includes(k)) fail(`unknown option "${k}"`);
    const o = { ...LOOKS[name], ...over }, hex = v => typeof v === 'string' && /^#[0-9a-fA-F]{6}$/.test(v);
    for (const k of ['title', 'dark']) if (!DARK_BG.includes(o[k])) fail(`"${o[k]}" can't be the ${k} background (white text): use one of ${DARK_BG.join(', ')}`);
    if (!LIGHT_BG.includes(o.light)) fail(`"${o.light}" can't be the light background: use one of ${LIGHT_BG.join(', ')}`);
    for (const k of ROLE_KEYS) if (!hex(o[k])) fail(`${k} must be a colour like '#1B3358', not ${JSON.stringify(o[k])}`);
    if (o.tint != null && !(Array.isArray(o.tint) && o.tint.length === 2 && o.tint.every(hex))) fail("tint must be ['#top', '#bottom']");
    THEMED = true; TINT = o.tint || null;
    for (const k of ['title', 'dark', 'light']) LOOK[k] = o[k];
    for (const k of ROLE_KEYS) C[k] = o[k];
    return { look: name, ...LOOK, tint: TINT };
  }
  function dotsGrid(ctx, color) { ctx.save(); ctx.fillStyle = color; for (let x = 40; x < W; x += 48) for (let y = 40; y < H; y += 48) { ctx.beginPath(); ctx.arc(x, y, 2, 0, 6.283); ctx.fill(); } ctx.restore(); }

  // ---------- teaching widgets ----------
  // Title + optional kicker at the top of a content scene (consistent position).
  function heading(ctx, str, t, o = {}) {
    o = { color: C.head, kicker: null, kickColor: C.main, at: 0, x: 120, y: 92, size: 72, ...o };
    const k = P(t, o.at, 0.7);
    if (o.kicker) text(ctx, o.kicker.toUpperCase(), o.x, o.y - 50, { size: 30, weight: 700, color: o.kickColor, alpha: k });
    text(ctx, str, o.x + (1 - k) * -40, o.y, { size: o.size, weight: 700, color: o.color, alpha: k, maxW: o.maxW || 1680, accent: o.accent || C.accent });
  }
  function badge(ctx, label, x, y, o = {}) {
    o = { fill: C.accent, color: '#fff', size: 30, alpha: 1, scale: 1, ...o }; if (o.alpha <= 0 || o.scale <= 0) return;
    ctx.save(); ctx.globalAlpha *= o.alpha; ctx.translate(x, y); ctx.scale(o.scale, o.scale);
    ctx.font = `800 ${o.size}px ${FONT}`; const w = ctx.measureText(label).width + o.size * 1.3, h = o.size * 1.7;
    rr(ctx, 0, -h / 2, w, h, h / 2); ctx.fillStyle = o.fill; ctx.fill();
    ctx.fillStyle = o.color; ctx.textBaseline = 'middle'; ctx.fillText(label, o.size * 0.65, 2); ctx.restore();
    return w;
  }
  // "TEST TIP" banner card that pops in at time `at`.
  function tip(ctx, str, t, at, o = {}) {
    // Sits with its bottom edge at o.bottom (default 900, clear of the captions) unless o.y is given.
    o = { x: 120, y: null, bottom: 900, w: 1680, label: 'TEST TIP', fill: '#FFF4E0', edge: C.accent, size: 40, ...o };
    const k = P(t, at, 0.55, E.back); if (k <= 0) return;
    const h = measure(ctx, str, { size: o.size, maxW: o.w - 300 }).h + 60;
    if (o.y == null) o.y = o.bottom - h;
    ctx.save(); ctx.translate(o.x + o.w / 2, o.y + h / 2); ctx.scale(0.85 + 0.15 * k, 0.85 + 0.15 * k); ctx.translate(-(o.x + o.w / 2), -(o.y + h / 2));
    card(ctx, o.x, o.y, o.w, h, { fill: o.fill, alpha: clamp(k * 1.5), r: 24 });
    ctx.save(); ctx.globalAlpha *= clamp(k * 1.5); rr(ctx, o.x, o.y, 14, h, 7); ctx.fillStyle = o.edge; ctx.fill(); ctx.restore();
    badge(ctx, o.label, o.x + 40, o.y + h / 2, { fill: o.edge, alpha: clamp(k * 1.5), size: 26 });
    text(ctx, str, o.x + 260, o.y + 30, { size: o.size, weight: 600, color: C.ink, maxW: o.w - 300, alpha: clamp(k * 1.5) });
    ctx.restore();
  }
  // Bullet list; each item i appears at times[i].
  function bullets(ctx, items, x, y, t, times, o = {}) {
    o = { size: 46, gap: 26, color: C.ink, dot: C.main, maxW: 1500, ...o }; let cy = y;
    items.forEach((it, i) => {
      const k = P(t, times[i] ?? 0, 0.5); const h = measure(ctx, it, { size: o.size, maxW: o.maxW }).h;
      if (k > 0) { circle(ctx, x + 14 + (1 - k) * -30, cy + o.size * 0.55, 11 * k, o.dot); text(ctx, it, x + 50 + (1 - k) * -30, cy, { size: o.size, color: o.color, maxW: o.maxW, alpha: k, weight: o.weight || 500, accent: o.accent || C.accent }); }
      cy += h + o.gap;
    });
    return cy;
  }
  // Leader-line label: dot at (px,py), text at (tx,ty).
  function label(ctx, str, px, py, tx, ty, k, o = {}) {
    o = { color: C.ink, line: C.accent, size: 36, align: tx < px ? 'right' : 'left', ...o }; if (k <= 0) return;
    circle(ctx, px, py, 9 * k, o.line); line(ctx, px, py, tx, ty, { color: o.line, w: 4, prog: clamp(k * 1.4) });
    const kk = clamp(k * 1.6 - 0.6); if (kk > 0) text(ctx, str, tx + (o.align === 'right' ? -14 : 14), ty - o.size * 0.62, { size: o.size, weight: 700, color: o.color, align: o.align, alpha: kk, maxW: o.maxW });
  }
  // Molecule field: n dots wander inside box {x,y,w,h}; drift(t) shifts their x (for flow animations).
  function wander(i, t, box, seed = 1, sp = 0.6) {
    const r = rng(Math.imul(seed * 1000 + i + 1, 2654435761)); const bx = r(), by = r(), ph = r() * 50;  // hashed seed: neighbouring i must not share a position
    const x = box.x + (bx + 0.08 * noise(i, t * sp + ph, 1)) * box.w, y = box.y + (by + 0.08 * noise(i + 99, t * sp + ph, 1.1)) * box.h;
    return [clamp(x, box.x + 10, box.x + box.w - 10), clamp(y, box.y + 10, box.y + box.h - 10)];
  }
  function molecule(ctx, x, y, kind, s = 1, alpha = 1) {
    ctx.save(); ctx.globalAlpha *= alpha;
    if (kind === 'water') { circle(ctx, x, y, 13 * s, C.water); circle(ctx, x - 10 * s, y - 9 * s, 6 * s, '#E3F6FF'); circle(ctx, x + 10 * s, y - 9 * s, 6 * s, '#E3F6FF'); }
    else if (kind === 'salt') { ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = '#9AA7B5'; ctx.lineWidth = 3 * s; const z = 14 * s; ctx.fillRect(x - z / 2, y - z / 2, z, z); ctx.strokeRect(x - z / 2, y - z / 2, z, z); }
    else if (kind === 'sugar') { circle(ctx, x, y, 12 * s, C.sun, { stroke: '#C98F00', lw: 3 }); }
    else if (kind === 'o2') { circle(ctx, x - 8 * s, y, 10 * s, '#FF5A5F'); circle(ctx, x + 8 * s, y, 10 * s, '#FF5A5F'); }
    else if (kind === 'co2') { circle(ctx, x, y, 10 * s, '#3D3D3D'); circle(ctx, x - 17 * s, y, 9 * s, '#FF5A5F'); circle(ctx, x + 17 * s, y, 9 * s, '#FF5A5F'); }
    else circle(ctx, x, y, 10 * s, kind);
    ctx.restore();
  }
  // Semipermeable membrane: vertical dashed wall with pores.
  function membrane(ctx, x, y1, y2, t, o = {}) {
    o = { color: '#E9C46A', w: 22, ...o };
    ctx.save(); ctx.fillStyle = o.color; for (let y = y1; y < y2; y += 44) { rr(ctx, x - o.w / 2, y, o.w, 30, 8); ctx.fill(); } ctx.restore();
  }
  // Countdown ring for "pause and think" quiz moments.
  function ring(ctx, x, y, r, k, o = {}) {
    o = { color: C.coral, track: 'rgba(255,255,255,0.25)', w: 14, ...o };
    ctx.save(); ctx.lineWidth = o.w; ctx.strokeStyle = o.track; ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.stroke();
    ctx.strokeStyle = o.color; ctx.lineCap = 'round'; ctx.beginPath(); ctx.arc(x, y, r, -Math.PI / 2, -Math.PI / 2 + 6.283 * clamp(k)); ctx.stroke(); ctx.restore();
  }
  // Table: rows = [[...header], [...], ...]; colW = [..]; k reveals rows progressively.
  function table(ctx, rows, x, y, colW, o = {}) {
    o = { rowH: 86, size: 36, head: C.head, headColor: '#fff', fill: '#fff', alt: '#F1F6F9', k: 1, rowTimes: null, t: 0, ...o };
    let cy = y; const totalW = colW.reduce((a, b) => a + b, 0);
    rows.forEach((row, ri) => {
      const k = o.rowTimes ? P(o.t, o.rowTimes[ri] ?? 0, 0.5) : clamp(o.k * rows.length - ri);
      if (k > 0) {
        ctx.save(); ctx.globalAlpha *= k;
        ctx.fillStyle = ri === 0 ? o.head : (ri % 2 ? o.fill : o.alt); ctx.fillRect(x, cy, totalW, o.rowH);
        let cx = x; row.forEach((cell, ci) => { text(ctx, String(cell), cx + 22, cy + (o.rowH - o.size * 1.15) / 2, { size: o.size, weight: ri === 0 || ci === 0 ? 700 : 500, color: ri === 0 ? o.headColor : (o.colColors?.[ci] || C.ink), maxW: colW[ci] - 30, accent: C.accent }); cx += colW[ci]; });
        ctx.restore();
      }
      cy += o.rowH;
    });
    return cy;
  }

  // ---------- emoji + standard scenes shared by every chapter ----------
  function emoji(ctx, ch, x, y, size, o = {}) {
    o = { alpha: 1, scale: 1, rot: 0, ...o }; if (o.alpha <= 0 || o.scale <= 0) return;
    ctx.save(); ctx.globalAlpha *= o.alpha; ctx.translate(x, y); ctx.rotate(o.rot); ctx.scale(o.scale, o.scale);
    ctx.font = `${size}px "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(ch, 0, size * 0.06); ctx.restore();
  }
  const pop = (t, a, d = 0.5) => P(t, a, d, E.back);
  // Big title card: kicker (small caps line), title, optional subtitle + emoji row.
  function titleCard(ctx, t, s, o = {}) {
    o = { kicker: '', title: '', sub: '', emojis: [], bg: null, ...o };
    if (o.bg == null) paint(ctx, LOOK.title, t + (s.start || 0)); else bg(ctx, o.bg, t + (s.start || 0));
    const k1 = P(t, 0.1, 0.8), k2 = P(t, 0.4, 0.8), k3 = P(t, 0.9, 0.8);
    if (o.kicker) badge(ctx, o.kicker.toUpperCase(), W / 2 - measureBadge(ctx, o.kicker.toUpperCase(), 30) / 2, 330, { fill: C.accent, alpha: k1, size: 30 });
    text(ctx, o.title, W / 2, 400 + (1 - k2) * 40, { size: 104, weight: 800, color: '#fff', align: 'center', maxW: 1600, alpha: k2, shadow: true, accent: C.glow, lh: 1.08 });
    if (o.sub) text(ctx, o.sub, W / 2, 640 + (1 - k3) * 30, { size: 46, weight: 500, color: C.soft, align: 'center', maxW: 1400, alpha: k3 });
    o.emojis.forEach((e, i) => emoji(ctx, e, W / 2 + (i - (o.emojis.length - 1) / 2) * 150, 800 + Math.sin(t * 2 + i) * 10, 96, { scale: pop(t, 1.2 + i * 0.15) }));
  }
  // ---------- intro: the opening scene as a short motion piece, never a copy of the deck's title slide ----------
  // intro(g, t, s, {mood, title, kicker, sub, by, logo, name, photo, main, accent, panel, emojis, at}); see guide.md.
  // Every text colour is checked against what is behind it (4.5:1 at least) and moved toward black or white until
  // it reads; the text block shrinks, and at worst is cut short, so it stays between the logo and the captions.
  const MOODS = {
    polished: { main: '#0B2545', accent: '#2563EB', stagger: 0.09, dur: 0.75 },
    cinematic: { main: '#134E6F', accent: '#FFC145', stagger: 0.09, dur: 0.9 },
    calm: { main: '#1F7A6D', accent: '#4FC3F7', stagger: 0.07, dur: 1.0 },
    energetic: { main: '#16212E', accent: '#FF6B57', stagger: 0.12, dur: 0.35 },
    playful: { main: '#0B2545', accent: '#FF6B57', stagger: 0.09, dur: 0.6 },
  };
  const INTRO_KEYS = ['mood', 'title', 'kicker', 'sub', 'by', 'logo', 'name', 'photo', 'main', 'accent', 'panel', 'emojis', 'at'];
  const AT_KEYS = ['logo', 'kicker', 'title', 'sub', 'by'], INK = '#16212E', WHITE = '#FFFFFF', BLACK = '#000000';
  const isHex = v => typeof v === 'string' && /^#[0-9a-fA-F]{6}$/.test(v);
  const hexRgb = c => { const n = parseInt(c.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; };
  const toHex = v => '#' + v.map(x => Math.round(clamp(x, 0, 255)).toString(16).padStart(2, '0')).join('');
  const mixHex = (a, b, k) => { const x = hexRgb(a), y = hexRgb(b); return toHex(x.map((v, i) => lerp(v, y[i], clamp(k)))); };
  const rgba = (c, a) => `rgba(${hexRgb(c).join(',')},${a})`;
  function lum(c) { return hexRgb(c).reduce((s, v, i) => { v /= 255; return s + [0.2126, 0.7152, 0.0722][i] * (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4); }, 0); }
  function contrast(a, b) { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
  // c, moved toward black (on light colours) or white (on dark ones) until it reads at min:1 on every colour of `on`.
  function readable(c, on, min) {
    on = [].concat(on); const ok = x => on.every(b => contrast(x, b) >= min);
    if (ok(c)) return c;
    const to = on.reduce((s, b) => s + lum(b), 0) / on.length > 0.179 ? BLACK : WHITE;
    for (let k = 0.05; k < 1; k += 0.05) { const x = mixHex(c, to, k); if (ok(x)) return x; }
    return to;
  }
  function introOptions(o) {
    const fail = m => { throw new Error(`Engine.intro: ${m}`); };
    if (o === null || typeof o !== 'object' || Array.isArray(o)) fail('the fourth argument is { mood, title, ... }');
    if (Object.hasOwn(o, 'look')) fail('`look` is now `mood`: one of ' + Object.keys(MOODS).join(', '));
    for (const k of Object.keys(o)) if (!INTRO_KEYS.includes(k)) fail(`unknown option "${k}"; use ${INTRO_KEYS.join(', ')}`);
    if (typeof o.mood !== 'string' || !Object.hasOwn(MOODS, o.mood)) fail(`unknown mood ${JSON.stringify(o.mood)}; use one of ${Object.keys(MOODS).join(', ')}`);
    if (typeof o.title !== 'string' || !o.title.trim()) fail("title must be the title slide's title, a non-empty string");
    for (const k of ['kicker', 'sub', 'by', 'name', 'logo', 'photo']) if (o[k] != null && typeof o[k] !== 'string') fail(`${k} must be a string, not ${JSON.stringify(o[k])}`);
    for (const k of ['main', 'accent']) if (o[k] != null && !isHex(o[k])) fail(`${k} must be a colour like '#1B3358', not ${JSON.stringify(o[k])}`);
    if (o.panel != null && typeof o.panel !== 'boolean') fail('panel must be true or false');
    if (o.photo != null && o.mood !== 'cinematic') fail('photo is drawn only by the cinematic mood');
    if (o.emojis != null && !(Array.isArray(o.emojis) && o.emojis.every(e => typeof e === 'string'))) fail("emojis must be a list like ['🌍', '📜']");
    if (o.emojis?.length && o.mood !== 'playful') fail('emojis are drawn only by the playful mood');
    const at = o.at ?? {};
    if (at === null || typeof at !== 'object' || Array.isArray(at)) fail('at must be { logo, kicker, title, sub, by } times in seconds');
    for (const [k, v] of Object.entries(at)) {
      if (!AT_KEYS.includes(k)) fail(`unknown at.${k}; use ${AT_KEYS.join(', ')}`);
      if (typeof v !== 'number' || !Number.isFinite(v) || v < 0) fail(`at.${k} must be a time in seconds, not ${JSON.stringify(v)}`);
    }
    const d = MOODS[o.mood];
    return { kicker: o.kicker || '', sub: o.sub || '', by: o.by || '', name: o.name || '', logo: o.logo || null, photo: o.photo || null,
      emojis: o.emojis || [], panel: o.panel, title: o.title, mood: o.mood, main: o.main || d.main, accent: o.accent || d.accent, at };
  }

  // ---- text: wrapping that also breaks scripts written without spaces, shrinking, cutting short ----
  const NOSPACE = /[฀-໿က-႟ក-៿⺀-鿿ꥠ-퟿豈-﫿︰-﹏＀-￯]/;
  const segmenters = {};
  function pieces(s, granularity) {
    try { segmenters[granularity] ||= new Intl.Segmenter(undefined, { granularity }); return [...segmenters[granularity].segment(s)].map(x => x.segment); }
    catch (e) { return Array.from(s); }
  }
  // Lines of runs, like wrapRich, but Chinese, Japanese, Thai... and any word wider than maxW also break inside.
  function introWrap(ctx, str, o) {
    const toks = [];
    for (const r of parseRich(str)) for (const w of r.s.split(/(\s+)/)) {
      if (!w) continue;
      ctx.font = fontStr(o, r.bold);
      if (/^\s+$/.test(w)) { toks.push({ acc: r.acc, bold: r.bold, s: ' ', w: ctx.measureText(' ').width, sp: true }); continue; }
      const parts = (NOSPACE.test(w) ? pieces(w, 'word') : [w]).flatMap(p => ctx.measureText(p).width > o.maxW ? pieces(p, 'grapheme') : [p]);
      for (const p of parts) toks.push({ acc: r.acc, bold: r.bold, s: p, w: ctx.measureText(p).width });
    }
    const lines = [[]]; let lw = 0;
    for (const tk of toks) {
      const L = lines[lines.length - 1];
      if (tk.sp) { if (L.length) { L.push(tk); lw += tk.w; } continue; }
      if (lw + tk.w > o.maxW && L.length) { while (L.length && L[L.length - 1].sp) L.pop(); lines.push([]); lw = 0; }
      lines[lines.length - 1].push(tk); lw += tk.w;
    }
    return lines.map(L => { while (L.length && L[L.length - 1].sp) L.pop(); return { runs: L, w: L.reduce((a, r) => a + r.w, 0) }; }).filter(L => L.runs.length);
  }
  // At most n lines; when lines are dropped, the last one kept ends with an ellipsis.
  function cutLines(ctx, lines, n, o) {
    if (lines.length <= n) return lines;
    if (n <= 0) return [];
    const out = lines.slice(0, n), runs = [...out[n - 1].runs];
    ctx.font = fontStr(o, false); const ew = ctx.measureText('…').width;
    let w = out[n - 1].w;
    while (runs.length > 1 && (w + ew > o.maxW || runs[runs.length - 1].sp)) w -= runs.pop().w;
    const last = runs[runs.length - 1];
    runs.push({ acc: last.acc, bold: last.bold, s: '…', w: ew });
    out[n - 1] = { runs, w: w + ew };
    return out;
  }
  const SLOTS = { title: { weight: 800, lh: 1.06 }, sub: { weight: 600, lh: 1.22 }, by: { weight: 500, lh: 1.22 }, kick: { weight: 800, lh: 1.22 } };
  // Sizes and lines for the kicker, title, sub and by lines that fit maxH: the title shrinks first (to 64 px, then to
  // 44 px over four lines), then sub and by (to 34 and 30 px), then lines are cut short, last of all the title's.
  function introLayout(ctx, o, st, maxH) {
    const size = { title: st.size, sub: 46, by: 36, kick: 30 }, n = { title: 3, sub: 3, by: 2, kick: 1 };
    const text = { title: o.title, sub: o.sub, by: o.by, kick: o.kicker.toUpperCase() };
    const maxW = k => k === 'kick' ? st.maxW - (st.badge ? 60 : 80) : st.maxW;
    const wrap = k => text[k] ? introWrap(ctx, text[k], { size: size[k], weight: SLOTS[k].weight, maxW: maxW(k) }) : [];
    const build = () => {
      const L = {};
      for (const k of ['kick', 'title', 'sub', 'by']) L[k] = cutLines(ctx, wrap(k), n[k], { size: size[k], weight: SLOTS[k].weight, maxW: maxW(k) });
      const h = (L.kick.length ? 70 : 0) + L.title.length * size.title * SLOTS.title.lh + (st.rule ? 40 : 0)
        + (L.sub.length ? 16 + L.sub.length * size.sub * SLOTS.sub.lh : 0) + (L.by.length ? 12 + L.by.length * size.by * SLOTS.by.lh : 0)
        + (st.extra || 0);
      return { L, h, size: { ...size } };
    };
    while (size.title > 64 && wrap('title').length > 3) size.title -= 4;
    if (wrap('title').length > 3) { n.title = 4; while (size.title > 44 && wrap('title').length > 4) size.title -= 4; }
    let r = build();
    while (r.h > maxH && size.title > 64) { size.title -= 4; r = build(); }
    while (r.h > maxH && (size.sub > 34 || size.by > 30)) { size.sub = Math.max(34, size.sub - 2); size.by = Math.max(30, size.by - 2); r = build(); }
    while (r.h > maxH && size.title > 44) { size.title -= 4; r = build(); }
    while (r.h > maxH && (n.by > 0 || n.sub > 0 || n.title > 1)) {
      if (n.by > 1) n.by--; else if (n.sub > 1) n.sub--; else if (n.title > 2) n.title--; else if (n.by) n.by = 0; else if (n.sub) n.sub = 0; else n.title--;
      r = build();
    }
    return r;
  }
  const pieceCount = lines => lines.reduce((s, L) => s + L.runs.filter(r => !r.sp).length, 0);
  // One laid-out block at (x, y). With a mode, its pieces come in one by one ('rise', 'slam', 'bounce', 'focus',
  // 'fade'); without, the block slides in as one at `at`. Returns its height.
  function drawBlock(ctx, lines, x, y, size, slot, o, t, at, mode, stagger = 0, dur = 0.7) {
    const f = { size, weight: SLOTS[slot].weight }, lh = size * SLOTS[slot].lh; let i = 0;
    lines.forEach((L, li) => {
      const top = y + li * lh, base = top + size * 0.82; let cx = x;
      for (const r of L.runs) {
        if (r.sp) { cx += r.w; continue; }
        const k = mode ? P(t, at + i++ * stagger, dur, mode === 'bounce' ? E.back : E.out) : P(t, at, 0.7);
        if (k > 0) {
          ctx.save(); ctx.font = fontStr(f, r.bold); ctx.fillStyle = r.acc ? o.accent : o.color; ctx.textBaseline = 'alphabetic';
          if (o.shadow) { ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = 24; ctx.shadowOffsetY = 4; }
          const mx = cx + r.w / 2, my = base - size * 0.35;
          if (!mode) { ctx.globalAlpha *= k; ctx.fillText(r.s, cx + (1 - k) * 40, base); }
          else if (mode === 'rise') { ctx.beginPath(); ctx.rect(cx - 30, top - size * 0.15, r.w + 60, size * 1.25); ctx.clip(); ctx.fillText(r.s, cx, base + (1 - k) * size * 1.3); }
          else if (mode === 'slam') { const z = 1 + 0.7 * (1 - k); ctx.globalAlpha *= clamp(k * 2.5); ctx.translate(mx, my); ctx.scale(z, z); ctx.fillText(r.s, -r.w / 2, size * 0.35); }
          else if (mode === 'bounce') { ctx.globalAlpha *= clamp(k * 3); ctx.translate(mx, my); ctx.scale(Math.max(0, k), Math.max(0, k)); ctx.rotate((1 - k) * 0.25); ctx.fillText(r.s, -r.w / 2, size * 0.35); }
          else if (mode === 'focus') { const z = 1 + 0.12 * (1 - k); ctx.globalAlpha *= k; if (k < 1) ctx.filter = `blur(${((1 - k) * 14).toFixed(1)}px)`; ctx.translate(mx, my); ctx.scale(z, z); ctx.fillText(r.s, -r.w / 2, size * 0.35); }
          else { ctx.globalAlpha *= k; ctx.fillText(r.s, cx, base + (1 - k) * 26); }
          ctx.restore();
        }
        cx += r.w;
      }
    });
    return lines.length * lh;
  }
  // Kicker, title, rule, sub and by, left-aligned at st.x: centred between st.y0 and st.y1, or resting on st.y1.
  function introText(ctx, t, a, st, lay) {
    const { L, size } = lay;
    let y = st.anchor === 'bottom' ? st.y1 - lay.h : clamp(590 - lay.h / 2, st.y0, st.y1 - lay.h);
    const top = y, x = st.x;
    ctx.save();
    if (st.skew) ctx.transform(1, 0, -st.skew, 1, st.skew * (top + lay.h / 2), 0);
    if (L.kick.length) {
      const k = P(t, a.kicker, 0.6);
      if (st.badge) badge(ctx, L.kick[0].runs.map(r => r.s).join(''), x, y + 22, { fill: st.badge, size: 30, scale: pop(t, a.kicker) });
      else {
        ctx.save(); ctx.globalAlpha *= k; ctx.fillStyle = st.kick; ctx.fillRect(x, y + 12, 56 * k, 6); ctx.restore();
        drawBlock(ctx, L.kick, x + 76, y - 4, size.kick, 'kick', { color: st.kick, accent: st.kick }, t, a.kicker, null);
      }
      y += 70;
    }
    y += drawBlock(ctx, L.title, x, y, size.title, 'title', { color: st.title, accent: st.accent, shadow: st.shadow }, t, a.title, st.mode, a.stagger, st.dur);
    if (st.rule) { const k = P(t, a.sub - 0.3, 0.9, E.inOut); ctx.save(); ctx.fillStyle = st.rule; ctx.fillRect(x, y + 18, 280 * k, 8); ctx.restore(); y += 40; }
    if (L.sub.length) y += 16 + drawBlock(ctx, L.sub, x, y + 16, size.sub, 'sub', { color: st.sub, accent: st.accent, shadow: st.shadow }, t, a.sub, null);
    if (L.by.length) y += 12 + drawBlock(ctx, L.by, x, y + 12, size.by, 'by', { color: st.by, accent: st.accent, shadow: st.shadow }, t, a.by, null);
    ctx.restore();
    return y;
  }

  // ---- logo and photo ----
  const tones = {}, scrims = {}, warnedIntro = new Set();
  function warnOnce(m) { if (!warnedIntro.has(m)) { warnedIntro.add(m); console.warn(m); } }
  function loaded(key) { return !!key && Object.hasOwn(imgs, key) && imgs[key].naturalWidth > 0; }
  // The logo's average colour (by opacity), to keep it visible on its background.
  function logoTone(key) {
    if (Object.hasOwn(tones, key)) return tones[key];
    let c = INK;
    try {
      const cv = document.createElement('canvas'); cv.width = cv.height = 48; const x = cv.getContext('2d'); x.drawImage(imgs[key], 0, 0, 48, 48);
      const d = x.getImageData(0, 0, 48, 48).data; let r = 0, g = 0, b = 0, w = 0;
      for (let i = 0; i < d.length; i += 4) { const q = d[i + 3] / 255; r += d[i] * q; g += d[i + 1] * q; b += d[i + 2] * q; w += q; }
      if (w > 0) c = toHex([r / w, g / w, b / w]);
    } catch (e) { /* pixels unreadable: treat it as a dark logo */ }
    return (tones[key] = c);
  }
  // How dark the photo is made behind the text: enough for white text at 7:1 on its brightest tenth there.
  function photoScrim(key) {
    if (Object.hasOwn(scrims, key)) return scrims[key];
    let a = 0.62;
    try {
      const cv = document.createElement('canvas'); cv.width = 96; cv.height = 54; const x = cv.getContext('2d');
      drawImg(x, imgs[key], 0, 0, 96, 54, { fit: 'cover', zoom: 1.1 });
      const d = x.getImageData(0, 13, 70, 35).data, px = [];
      for (let i = 0; i < d.length; i += 4) px.push(toHex([d[i], d[i + 1], d[i + 2]]));
      px.sort((p, q) => lum(p) - lum(q)); const p90 = px[Math.floor(px.length * 0.9)];
      a = 0.3; while (a < 0.95 && contrast(WHITE, mixHex(p90, BLACK, a * 0.85)) < 7) a += 0.03;
    } catch (e) { /* pixels unreadable: keep the strong default */ }
    return (scrims[key] = a);
  }
  // The logo (with the name beside it when both are given), or the name alone, at (x, y), h tall. A panel goes under
  // it when the mood uses one (or `panel: true`), or when the logo would be hard to see on the background behind it.
  function introLogo(ctx, o, k, x, y, h, st) {
    if (k <= 0) return;
    const logo = loaded(o.logo);
    if (o.logo && !logo) warnOnce(`Engine.intro: no loaded Engine.assets() entry "${o.logo}" for the logo; drawing ${o.name ? 'the name' : 'no logo'} instead`);
    if (!logo && !o.name) return;
    const tone = logo ? logoTone(o.logo) : null, dark = readable(o.main, WHITE, 7);
    let panel = o.panel ?? st.panel, fill = WHITE;
    if (logo && !panel && contrast(tone, st.behind) < 2) { panel = true; fill = lum(st.behind) > 0.179 ? dark : WHITE; }
    if (logo && panel && contrast(tone, fill) < 2) fill = fill === WHITE ? dark : WHITE;   // a light logo goes on a dark panel
    const ar = logo ? imgs[o.logo].naturalWidth / imgs[o.logo].naturalHeight : 0, lw = logo ? Math.min(560, h * ar) : 0;
    const nameColor = readable(panel ? (fill === WHITE ? INK : WHITE) : st.title, panel ? fill : st.behind, 4.5), nf = { size: 40, weight: 800 };
    const nl = o.name ? cutLines(ctx, introWrap(ctx, o.name, { ...nf, maxW: 640 }), 1, { ...nf, maxW: 640 }) : [];
    const nw = nl.length ? nl[0].w : 0, gap = logo && nw ? 28 : 0;
    ctx.save(); ctx.globalAlpha *= clamp(k * 1.5); ctx.translate((1 - k) * -50, 0);
    if (panel) card(ctx, x - 28, y - 20, lw + gap + nw + 56, h + 40, { fill, r: 22 });
    if (logo) img(ctx, o.logo, x, y, lw, h, { fit: 'contain' });
    if (nl.length) drawBlock(ctx, nl, x + lw + gap, y + (h - 49) / 2, 40, 'kick', { color: nameColor, accent: nameColor }, 99, 0, null);
    ctx.restore();
  }

  // ---- the moods ----
  function introStyle(ctx, o, t, s) {
    const M = o.main, A = o.accent;
    if (o.mood === 'polished') {
      const light = contrast(M, INK) > contrast(M, WHITE);
      const base = light ? readable(M, INK, 7) : readable(M, WHITE, 7), ends = light ? [mixHex(base, WHITE, 0.35), base] : [base, mixHex(base, BLACK, 0.5)];
      const text = light ? INK : WHITE, acc = readable(light ? A : mixHex(A, WHITE, 0.35), ends, 4.5);
      return { x: 140, maxW: 1040, size: 116, y0: 260, y1: 880, mode: 'rise', panel: true, behind: ends[0], ends,
        title: readable(text, ends, 7), accent: acc, kick: acc, sub: readable(mixHex(text, base, 0.14), ends, 4.5), by: readable(mixHex(text, base, 0.2), ends, 4.5),
        rule: readable(A, ends, 3), tile: readable(A, ends, 3), ink: text, logo: [148, 110, 100] };
    }
    if (o.mood === 'cinematic') {
      const photo = !!o.photo && loaded(o.photo);
      if (o.photo && !photo) warnOnce(`Engine.intro: no loaded Engine.assets() entry "${o.photo}" for the photo; drawing a sky instead`);
      const base = readable(M, WHITE, 7), behind = photo ? '#595959' : base;   // #595959: the scrimmed photo is at most this bright
      const acc = readable(mixHex(A, WHITE, 0.15), behind, 4.5);
      return { x: 140, maxW: 1250, size: 132, y0: 270, y1: 860, anchor: 'bottom', mode: 'focus', panel: true, behind: '#000000', photo, base,
        title: WHITE, accent: acc, kick: acc, sub: readable('#EBEBEB', behind, 4.5), by: readable('#EBEBEB', behind, 4.5), shadow: true, logo: [148, 146, 84] };
    }
    if (o.mood === 'calm') {
      const ends = [WHITE, mixHex(WHITE, M, 0.12)], acc = readable(M, ends, 4.5);
      return { x: 140, maxW: 900, size: 100, y0: 260, y1: 880, mode: 'fade', panel: false, behind: WHITE, ends,
        title: readable(mixHex(M, BLACK, 0.45), ends, 7), accent: acc, kick: acc, sub: readable('#3D4B5C', ends, 7), by: readable('#3D4B5C', ends, 7),
        rule: readable(mixHex(A, M, 0.3), ends, 3), line: readable(M, ends, 3), logo: [148, 110, 100] };
    }
    if (o.mood === 'energetic') {
      const base = readable(mixHex(M, '#08090C', 0.55), WHITE, 12), acc = readable(A, base, 4.5);
      return { x: 160, maxW: 1000, size: 124, y0: 260, y1: 880, mode: 'slam', panel: true, behind: base, base, skew: 0.12,
        title: WHITE, accent: acc, kick: acc, sub: readable(mixHex(WHITE, base, 0.12), base, 7), by: readable(mixHex(WHITE, base, 0.2), base, 4.5),
        rule: readable(A, base, 3), logo: [148, 110, 100] };
    }
    const paper = C.paper, acc = readable(A, paper, 4.5);   // playful
    return { x: 140, maxW: 1000, size: 108, y0: 260, y1: 880, mode: 'bounce', panel: false, behind: paper, badge: readable(A, WHITE, 4.5),
      title: readable(M, paper, 4.5), accent: acc, kick: acc, sub: readable(C.sea, paper, 4.5), by: readable(C.sea, paper, 4.5),
      extra: o.emojis.length ? 120 : 0, logo: [148, 110, 100] };
  }
  function intro(ctx, t, s, opts = {}) {
    const o = introOptions(opts), mood = MOODS[o.mood], st = introStyle(ctx, o, t, s);
    st.dur = mood.dur;
    const lay = introLayout(ctx, o, st, st.y1 - st.y0), n = pieceCount(lay.L.title);
    const stagger = Math.min(mood.stagger, 1.6 / Math.max(1, n - 1));
    const a = { ...(o.mood === 'cinematic' ? { logo: 1.2, kicker: 0.9, title: 1.1 } : { logo: 0.15, kicker: 0.35, title: 0.55 }), ...o.at, stagger };
    const titleDone = a.title + Math.max(0, n - 1) * stagger + mood.dur;
    if (a.sub == null) a.sub = titleDone + 0.15;
    if (a.by == null) a.by = a.sub + 0.6;
    const M = o.main, A = o.accent, r = rng(o.mood.length * 977 + 13);
    if (o.mood === 'polished') {
      const gr = ctx.createLinearGradient(0, 0, W, H); gr.addColorStop(0, st.ends[0]); gr.addColorStop(1, st.ends[1]);
      ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H);
      for (let i = 0; i < 8; i++) for (let j = 0; j < 9; j++) {   // a field of tiles breathing in a slow wave (decoration, never data)
        const k = P(t, (i + j) * 0.045 - 0.25, 0.7, E.out), wv = 0.5 + 0.5 * Math.sin(t * 1.6 - (i + j) * 0.45), z = (14 + 30 * wv) * k;
        if (z <= 0) continue;
        const hot = (i * 3 + j * 5) % 11 === 0, cx = 1250 + i * 76, cy = 230 + j * 72;
        ctx.save(); ctx.globalAlpha = hot ? 0.9 : 0.12 + 0.12 * wv; ctx.fillStyle = hot ? st.tile : st.ink; rr(ctx, cx - z / 2, cy - z / 2, z, z, z * 0.25); ctx.fill(); ctx.restore();
      }
      const sw = P(t, 0.2, 1.8, E.inOut);
      if (sw > 0 && sw < 1) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; const sx = lerp(-700, W + 300, sw); const lg = ctx.createLinearGradient(sx, 0, sx + 400, 0); lg.addColorStop(0, 'rgba(255,255,255,0)'); lg.addColorStop(0.5, 'rgba(255,255,255,0.10)'); lg.addColorStop(1, 'rgba(255,255,255,0)'); ctx.fillStyle = lg; ctx.beginPath(); ctx.moveTo(sx + 200, 0); ctx.lineTo(sx + 600, 0); ctx.lineTo(sx + 200, H); ctx.lineTo(sx - 200, H); ctx.closePath(); ctx.fill(); ctx.restore(); }
      introLogo(ctx, o, P(t, a.logo, 0.8), ...st.logo, st);
      introText(ctx, t, a, st, lay);
    } else if (o.mood === 'cinematic') {
      const kz = E.out(clamp(t / Math.max(6, s.dur || 10)));
      if (st.photo) {
        img(ctx, o.photo, 0, 0, W, H, { fit: 'cover', zoom: 1.18 - 0.14 * kz, panX: -0.4 + 0.5 * kz });
        const sa = photoScrim(o.photo), lg = ctx.createLinearGradient(0, 0, W, 0);
        lg.addColorStop(0, `rgba(0,0,0,${sa})`); lg.addColorStop(0.72, `rgba(0,0,0,${sa * 0.85})`); lg.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = lg; ctx.fillRect(0, 0, W, H);
      } else {
        const gr = ctx.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, st.base); gr.addColorStop(1, mixHex(st.base, BLACK, 0.6)); ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H);
        circle(ctx, 1650, 330 + 60 * (1 - kz), 150, mixHex(A, WHITE, 0.2), { alpha: 0.9 });   // right of the text (x <= 1390)
        for (let i = 0; i < 40; i++) { const x = (r() * W + t * (10 + r() * 30)) % W, y = r() * H; circle(ctx, x, y, 1.5 + r() * 3, 'rgba(255,255,255,0.35)'); }
      }
      const bg2 = ctx.createLinearGradient(0, H * 0.45, 0, H); bg2.addColorStop(0, 'rgba(0,0,0,0)'); bg2.addColorStop(1, 'rgba(0,0,0,0.5)'); ctx.fillStyle = bg2; ctx.fillRect(0, 0, W, H);
      const hb = lerp(H / 2 - 170, 92, P(t, 0.05, 1.7, E.inOut));   // letterbox opening like a curtain
      ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, hb); ctx.fillRect(0, H - hb, W, hb);
      introLogo(ctx, o, P(t, a.logo, 0.8), ...st.logo, st);
      introText(ctx, t, a, st, lay);
    } else if (o.mood === 'calm') {
      const gr = ctx.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, st.ends[0]); gr.addColorStop(1, st.ends[1]); ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H);
      const cx = 1530, cy = 500;
      circle(ctx, cx, cy, 150 * (0.85 + 0.15 * P(t, 0, 1.2)) * (1 + 0.012 * Math.sin(t * 1.4)), mixHex(M, WHITE, 0.86));
      for (let i = 0; i < 5; i++) circle(ctx, cx, cy, (170 + i * 64) * (1 + 0.015 * Math.sin(t * 0.9 - i * 0.7)), null, { stroke: mixHex(M, WHITE, 0.45 + i * 0.1), lw: 3, alpha: (0.7 - i * 0.12) * P(t, i * 0.18, 1.4) });
      // a calm pulse line through the rings, then a soft light travelling along it
      const ys = x => { const d = (x - cx) / 40; return cy + (Math.abs(d) < 3.2 ? -Math.sin(d * Math.PI / 1.6) * 70 * Math.exp(-d * d / 4) : 0); };
      const pk = P(t, 0.3, 2.2, E.inOut), x0 = 1140, x1 = W + 20;
      ctx.save(); ctx.strokeStyle = st.line; ctx.lineWidth = 6; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.beginPath();
      for (let x = x0; x <= lerp(x0, x1, pk); x += 6) x === x0 ? ctx.moveTo(x, ys(x)) : ctx.lineTo(x, ys(x)); ctx.stroke(); ctx.restore();
      if (t > 2.5) { const px = lerp(x0, x1, ((t - 2.5) * 0.18) % 1); circle(ctx, px, ys(px), 22, mixHex(A, WHITE, 0.3), { alpha: 0.35 }); circle(ctx, px, ys(px), 9, A); }
      introLogo(ctx, o, P(t, a.logo, 1.0), ...st.logo, st);
      introText(ctx, t, a, st, lay);
    } else if (o.mood === 'energetic') {
      ctx.fillStyle = st.base; ctx.fillRect(0, 0, W, H);
      for (let i = 0; i < 4; i++) {   // stripes slashing in from the right
        const k = P(t, i * 0.07, 0.5, E.out), x = 1180 + i * 190 + (1 - k) * 1300 - t * 6;
        ctx.save(); ctx.globalAlpha = [0.95, 0.55, 0.3, 0.15][i]; ctx.fillStyle = i ? mixHex(A, WHITE, 0.1 * i) : A;
        ctx.beginPath(); ctx.moveTo(x + 300, 0); ctx.lineTo(x + 420, 0); ctx.lineTo(x + 120, H); ctx.lineTo(x, H); ctx.closePath(); ctx.fill(); ctx.restore();
      }
      ctx.save(); ctx.strokeStyle = 'rgba(255,255,255,0.16)'; ctx.lineCap = 'round';
      for (let i = 0; i < 28; i++) { const y = 60 + r() * 960, len = 120 + r() * 260, sp = 900 + r() * 1100, x = ((r() * (W + 600) - t * sp) % (W + 600) + W + 600) % (W + 600) - 300; ctx.lineWidth = 2 + r() * 3; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + len, y); ctx.stroke(); }
      ctx.restore();
      let sh = 0; for (let i = 0; i < n; i++) { const tk = a.title + i * stagger + 0.25; if (t > tk) sh += 9 * Math.exp(-(t - tk) * 16); }
      ctx.save(); ctx.translate(sh * noise(1, t * 40), sh * noise(2, t * 40));
      introLogo(ctx, o, P(t, a.logo, 0.5), ...st.logo, st);
      introText(ctx, t, a, st, lay);
      ctx.restore();
    } else {   // playful
      introPlayfulBackdrop(ctx, t, o, st);
      introLogo(ctx, o, P(t, a.logo, 0.6), ...st.logo, st);
      const end = introText(ctx, t, a, st, lay);
      o.emojis.forEach((e, i) => emoji(ctx, e, st.x + 60 + i * 140, end + 60 + Math.sin(t * 2 + i) * 8, 90, { scale: pop(t, a.by + i * 0.12) }));
    }
  }
  // Paper with colourful shapes popping in and floating, kept clear of the text (right of x 1200, above y 100).
  function introPlayfulBackdrop(ctx, t, o, st) {
    bg(ctx, 'paper');
    const r = rng(8 * 977 + 13), cols = [C.coral, C.sun, C.teal, C.purple, C.leaf, C.pink, C.water];
    for (let i = 0; i < 16; i++) {
      const right = i < 12, x = right ? 1220 + r() * 600 : 620 + r() * 1200, y = right ? 160 + r() * 700 : 40 + r() * 50;
      const k = pop(t, i * 0.06 - 0.3), sz = 26 + r() * 46, rot = t * (r() - 0.5) * 0.8, fy = y + 14 * Math.sin(t * 1.3 + i), col = cols[i % cols.length];
      if (k <= 0) continue;
      ctx.save(); ctx.translate(x, fy); ctx.rotate(rot); ctx.scale(k, k); ctx.fillStyle = col; ctx.strokeStyle = col; ctx.lineWidth = 9; ctx.lineCap = 'round';
      const kind = i % 5; ctx.beginPath();
      if (kind === 0) { ctx.arc(0, 0, sz / 2, 0, 6.283); ctx.fill(); }
      else if (kind === 1) { ctx.moveTo(0, -sz / 2); ctx.lineTo(sz / 2, sz / 2); ctx.lineTo(-sz / 2, sz / 2); ctx.closePath(); ctx.fill(); }
      else if (kind === 2) { ctx.arc(0, 0, sz / 2, 0, 6.283); ctx.stroke(); }
      else if (kind === 3) { ctx.moveTo(-sz / 2, 0); ctx.lineTo(sz / 2, 0); ctx.moveTo(0, -sz / 2); ctx.lineTo(0, sz / 2); ctx.stroke(); }
      else { for (let j = 0; j <= 12; j++) { const px = -sz + j * sz / 6, py = Math.sin(j * 1.2) * sz / 5; j ? ctx.lineTo(px, py) : ctx.moveTo(px, py); } ctx.stroke(); }
      ctx.restore();
    }
  }
  function measureBadge(ctx, label, size) { ctx.save(); ctx.font = `800 ${size}px ${FONT}`; const w = ctx.measureText(label).width + size * 1.3; ctx.restore(); return w; }
  // Quiz question with a countdown ring during the hold after the narration ends.
  function quizQ(ctx, t, s, o = {}) {
    o = { n: 1, q: '', choices: null, emoji: '🤔', badge: '', numbered: false, ...o };
    paint(ctx, LOOK.dark, t + 100);
    badge(ctx, o.badge || `QUIZ · QUESTION ${o.n}`, 120, 150, { fill: C.sun, color: C.navy, scale: pop(t, 0.1), size: 32 });
    text(ctx, o.q, 120, 240, { size: 68, weight: 700, color: '#fff', maxW: 1250, alpha: P(t, 0.3, 0.6), accent: C.glow });
    if (o.choices) o.choices.forEach((c, i) => {
      const k = P(t, 0.8 + i * 0.25, 0.5); card(ctx, 120, 560 + i * 120, 1000, 96, { fill: 'rgba(255,255,255,0.1)', shadow: false, alpha: k, r: 20 });
      // a teacher's questions are numbered (they are not options to pick); a long line shrinks to fit its card
      const label = `${o.numbered ? i + 1 : String.fromCharCode(65 + i)}.  ${c}`;
      let size = 44; while (size > 30 && measure(ctx, label, { size, weight: 600 }).w > 920) size -= 2;
      text(ctx, label, 160, 580 + i * 120 + (44 - size) / 2, { size, weight: 600, color: '#fff', alpha: k });
    });
    emoji(ctx, o.emoji, 1560, 420, 220, { scale: pop(t, 0.5), rot: Math.sin(t * 2) * 0.06 });
    const holdStart = s.end, k = clamp((t - holdStart) / Math.max(0.1, s.dur - holdStart - 0.3));
    if (t > holdStart - 0.2) { const a = P(t, holdStart - 0.2, 0.4); ctx.save(); ctx.globalAlpha *= a; ring(ctx, 1560, 780, 90, 1 - k, { color: C.sun }); text(ctx, String(Math.max(1, Math.ceil((1 - k) * (s.dur - holdStart - 0.3)))), 1560, 735, { size: 80, weight: 800, color: '#fff', align: 'center' }); ctx.restore(); }
  }
  // Quiz answer: big check + answer + explanation.
  function quizA(ctx, t, s, o = {}) {
    o = { answer: '', why: '', ...o };
    paint(ctx, LOOK.dark, t + 100);
    const k = pop(t, 0.05, 0.6);
    circle(ctx, 260, 470, 120 * k, C.leaf); check(ctx, 262, 470, 130, P(t, 0.3, 0.5), '#fff');
    text(ctx, o.answer, 460, 360, { size: 96, weight: 800, color: C.sun, alpha: P(t, 0.2, 0.5), maxW: 1340 });
    text(ctx, o.why, 460, 500, { size: 50, weight: 500, color: '#fff', alpha: P(t, 0.8, 0.6), maxW: 1300, accent: C.glow });
  }
  // Recap checklist on paper.
  function recap(ctx, t, s, items, times, o = {}) {
    paint(ctx, LOOK.light, t);
    heading(ctx, o.title || 'Recap', t, { kicker: o.kicker || 'In 30 seconds' });
    const gap = o.gap || 130, ch = gap - 24, size = o.size || 44;
    items.forEach((it, i) => { const k = P(t, times[i] ?? 0, 0.5); const y = 250 + i * gap; card(ctx, 120, y, 1680, ch, { fill: '#fff', alpha: k, r: 22 }); check(ctx, 190, y + ch / 2, 60, P(t, (times[i] ?? 0) + 0.2, 0.5)); const m = measure(ctx, it, { size, maxW: 1480, weight: 600 }).h; text(ctx, it, 260, y + (ch - m) / 2 - 2, { size, weight: 600, color: C.ink, maxW: 1480, alpha: k, accent: C.main }); });
    if (o.next) text(ctx, o.next, W / 2, o.nextY || 840, { size: 40, weight: 700, color: C.note, align: 'center', alpha: P(t, o.nextAt ?? s.end - 3, 0.6) });
  }

  // ---------- overlays: chapter bug, progress bar, captions ----------
  function capLines() {
    // Sentence-level captions from narration words; each sentence shown while spoken.
    const out = [];
    for (const sc of T.scenes) {
      let cur = []; const flush = () => { if (cur.length) out.push({ s: sc.start + cur[0].s, e: sc.start + cur[cur.length - 1].e, text: cur.map(w => w.w).join(' '), words: cur.map(w => ({ ...w, s: sc.start + w.s, e: sc.start + w.e })) }); cur = []; };
      for (const w of sc.words || []) { cur.push(w); if (/[.!?]["”']?$/.test(w.w) || cur.length >= 16) flush(); }
      flush();
    }
    return out;
  }
  const CAPS = capLines();
  function captions(ctx, t, style) {
    const c = CAPS.find(c => t >= c.s - 0.05 && t <= c.e + 0.35); if (!c) return;
    const size = 38, maxW = 1500; ctx.save();
    const shown = c.text.replace(/\s+/g, ' ');
    const m = measure(ctx, shown, { size, maxW, weight: 600 });
    const bw = Math.min(maxW, m.w) + 60, bh = m.h + 28, bx = (W - bw) / 2, by = H - bh - 34;
    rr(ctx, bx, by, bw, bh, 18); ctx.fillStyle = style === 'light' ? 'rgba(11,37,69,0.82)' : 'rgba(5,15,30,0.72)'; ctx.fill();
    // highlight the current word
    const lines = wrapRich(ctx, shown, { size, maxW, weight: 600 }); let wi = 0;
    lines.forEach((L, li) => {
      let cx = W / 2 - L.w / 2; const cy = by + 14 + size * 0.82 + li * size * 1.22;
      for (const r of L.runs) {
        ctx.font = `600 ${size}px ${FONT}`;
        if (!/^\s+$/.test(r.s)) { const w = c.words[wi++]; ctx.fillStyle = w && t >= w.s && t <= w.e + 0.08 ? C.sun : '#FFFFFF'; }
        ctx.fillText(r.s, cx, cy); cx += r.w;
      }
    });
    ctx.restore();
  }
  function chrome(ctx, t, sc) {
    const k = clamp(t / T.duration);
    ctx.save(); ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.fillRect(0, 0, W, 8); ctx.fillStyle = C.main; ctx.fillRect(0, 0, W * k, 8); ctx.restore();
    if (sc && sc.opts.bug !== false && T.chapter) {
      const dark = sc.opts.dark; ctx.save(); ctx.font = `700 24px ${FONT}`; ctx.fillStyle = dark ? 'rgba(255,255,255,0.75)' : 'rgba(11,37,69,0.55)'; ctx.textAlign = 'right'; ctx.fillText(T.chapter, W - 60, 56); ctx.restore();
    }
  }

  // ---------- scene registry / render ----------
  function scene(id, draw, opts = {}) { scenes[id] = { draw, opts }; }
  function info(ts) {
    const words = ts.words || [];
    const norm = s => s.toLowerCase().replace(/[^a-z0-9₂]/g, '');
    return {
      id: ts.id, dur: ts.dur, speak: ts.lead, end: ts.lead + (ts.speech || 0), words,
      cue(word, n = 0, fallback) { const target = norm(word); let c = 0; for (const w of words) if (norm(w.w).startsWith(target) && c++ === n) return w.s; if (fallback != null) return fallback; console.warn(`cue miss: ${ts.id}/${word}#${n}`); return ts.lead; },
      after(word, n = 0) { const target = norm(word); let c = 0; for (const w of words) if (norm(w.w).startsWith(target) && c++ === n) return w.e; return ts.lead; },
      p(a, d = 0.6, ease = E.out) { return P(this.t, a, d, ease); },
    };
  }
  const INFOS = T.scenes.map(info);
  function drawScene(ctx, i, gt) {
    const ts = T.scenes[i], sc = scenes[ts.id], si = INFOS[i];
    const lt = gt - ts.start; si.t = lt;
    ctx.save();
    if (!sc) { paint(ctx, LOOK.dark, gt); text(ctx, `missing scene: ${ts.id}`, W / 2, H / 2, { align: 'center', color: '#fff' }); }
    else sc.draw(ctx, lt, si);
    ctx.restore();
  }
  function render(gt) {
    gt = clamp(gt, 0, T.duration - 1e-3);
    let i = T.scenes.findIndex(s => gt >= s.start && gt < s.start + s.dur); if (i < 0) i = T.scenes.length - 1;
    g.setTransform(1, 0, 0, 1, 0, 0); g.globalAlpha = 1; g.clearRect(0, 0, W, H);
    const ts = T.scenes[i], lt = gt - ts.start;
    if (i > 0 && lt < XFADE && !(scenes[ts.id]?.opts.cut)) {
      drawScene(g, i - 1, gt);
      og.setTransform(1, 0, 0, 1, 0, 0); og.globalAlpha = 1; og.clearRect(0, 0, W, H); drawScene(og, i, gt);
      g.save(); g.globalAlpha = E.inOut(lt / XFADE); g.drawImage(off, 0, 0); g.restore();
    } else drawScene(g, i, gt);
    const sc = scenes[ts.id];
    if (!sc?.opts.noChrome) chrome(g, gt, sc);
    if (!sc?.opts.noCaptions && window.CAPTIONS !== false) captions(g, gt, sc?.opts.dark ? 'dark' : 'light');
  }

  window.Engine = { W, H, C, E, FONT, HAND, theme, LOOKS, P, pop, clamp, lerp, rng, noise, text, measure, rr, card, circle, arrow, line, check, cross, assets, img, drawImg, clip, bg, heading, badge, tip, bullets, label, wander, molecule, membrane, ring, table, emoji, titleCard, intro, quizQ, quizA, recap, imgs, get pending() { return pending; }, waitLoads: () => pending ? new Promise(r => waiters.push(r)) : Promise.resolve() };
  window.scene = scene;
  window.FILM = { duration: T.duration };
  window.__render = render;
  window.__sfx = () => {
    // absolute-time sound cues declared via scene opts.sfx: [[localTime|'word'|['word',n], name, gainDb], ...]
    const out = [];
    T.scenes.forEach((ts, i) => { const sc = scenes[ts.id]; if (!sc?.opts.sfx) return; const si = INFOS[i]; for (const [at, name, gain] of sc.opts.sfx) { const lt = typeof at === 'number' ? at : Array.isArray(at) ? si.cue(at[0], at[1]) : si.cue(at); out.push({ t: ts.start + lt, name, gain: gain ?? -8 }); } });
    // automatic soft whoosh at each scene change
    T.scenes.forEach((ts, i) => { if (i > 0 && !scenes[ts.id]?.opts.silentIn) out.push({ t: ts.start, name: 'whoosh' + (i % 3), gain: -20 }); });
    return out;
  };
  Promise.all([`700 40px "Patrick Hand"`, `600 40px "Nunito"`, `800 40px "Nunito"`].map(f => document.fonts.load(f))).catch(() => {}).then(() => Promise.all(loads)).then(() => document.fonts.ready).then(() => {
    T.scenes.forEach(ts => { if (!scenes[ts.id]) console.error(`asset failed: no scene() for "${ts.id}" in scenes.js`); });
    window.__ready = true;
    if (!/export=1/.test(location.search)) {
      // interactive preview: play in real time with narration audio, click to scrub
      const au = new Audio('build/narration.mp3'); let t0 = null, paused = true, base = 0;
      const tick = now => { if (!paused) { const t = base + (now - t0) / 1000; render(t); if (t < T.duration) requestAnimationFrame(tick); } };
      canvas.addEventListener('click', e => { const t = e.offsetX / canvas.clientWidth * T.duration; base = t; au.currentTime = t; if (paused) { paused = false; au.play().catch(() => {}); } t0 = performance.now(); requestAnimationFrame(tick); });
      const q = new URLSearchParams(location.search); render(+(q.get('t') || 0));
    }
  });
})();
