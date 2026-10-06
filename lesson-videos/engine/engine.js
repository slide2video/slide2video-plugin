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
    o = { size: 48, color: C.ink, align: 'left', lh: 1.22, alpha: 1, accent: C.coral, ...o };
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
  function bg(ctx, kind, t = 0) {
    if (kind === 'paper') { ctx.fillStyle = C.paper; ctx.fillRect(0, 0, W, H); dotsGrid(ctx, 'rgba(19,49,92,0.07)'); return; }
    if (kind === 'sand') { ctx.fillStyle = C.sand; ctx.fillRect(0, 0, W, H); return; }
    if (kind === 'lab') { const gr = ctx.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, '#F3F7FA'); gr.addColorStop(1, '#DCE7EE'); ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H); dotsGrid(ctx, 'rgba(19,49,92,0.06)'); return; }
    // ocean / deep: gradient + light rays + drifting particles
    const gr = ctx.createLinearGradient(0, 0, 0, H);
    if (kind === 'deep') { gr.addColorStop(0, '#0E3A5C'); gr.addColorStop(1, '#061325'); }
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
  function dotsGrid(ctx, color) { ctx.save(); ctx.fillStyle = color; for (let x = 40; x < W; x += 48) for (let y = 40; y < H; y += 48) { ctx.beginPath(); ctx.arc(x, y, 2, 0, 6.283); ctx.fill(); } ctx.restore(); }

  // ---------- teaching widgets ----------
  // Title + optional kicker at the top of a content scene (consistent position).
  function heading(ctx, str, t, o = {}) {
    o = { color: C.navy, kicker: null, kickColor: C.teal, at: 0, x: 120, y: 92, size: 72, ...o };
    const k = P(t, o.at, 0.7);
    if (o.kicker) text(ctx, o.kicker.toUpperCase(), o.x, o.y - 50, { size: 30, weight: 700, color: o.kickColor, alpha: k });
    text(ctx, str, o.x + (1 - k) * -40, o.y, { size: o.size, weight: 700, color: o.color, alpha: k, maxW: o.maxW || 1680, accent: o.accent || C.coral });
  }
  function badge(ctx, label, x, y, o = {}) {
    o = { fill: C.coral, color: '#fff', size: 30, alpha: 1, scale: 1, ...o }; if (o.alpha <= 0 || o.scale <= 0) return;
    ctx.save(); ctx.globalAlpha *= o.alpha; ctx.translate(x, y); ctx.scale(o.scale, o.scale);
    ctx.font = `800 ${o.size}px ${FONT}`; const w = ctx.measureText(label).width + o.size * 1.3, h = o.size * 1.7;
    rr(ctx, 0, -h / 2, w, h, h / 2); ctx.fillStyle = o.fill; ctx.fill();
    ctx.fillStyle = o.color; ctx.textBaseline = 'middle'; ctx.fillText(label, o.size * 0.65, 2); ctx.restore();
    return w;
  }
  // "TEST TIP" banner card that pops in at time `at`.
  function tip(ctx, str, t, at, o = {}) {
    // Sits with its bottom edge at o.bottom (default 900, clear of the captions) unless o.y is given.
    o = { x: 120, y: null, bottom: 900, w: 1680, label: 'TEST TIP', fill: '#FFF4E0', edge: C.coral, size: 40, ...o };
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
    o = { size: 46, gap: 26, color: C.ink, dot: C.teal, maxW: 1500, ...o }; let cy = y;
    items.forEach((it, i) => {
      const k = P(t, times[i] ?? 0, 0.5); const h = measure(ctx, it, { size: o.size, maxW: o.maxW }).h;
      if (k > 0) { circle(ctx, x + 14 + (1 - k) * -30, cy + o.size * 0.55, 11 * k, o.dot); text(ctx, it, x + 50 + (1 - k) * -30, cy, { size: o.size, color: o.color, maxW: o.maxW, alpha: k, weight: o.weight || 500, accent: o.accent || C.coral }); }
      cy += h + o.gap;
    });
    return cy;
  }
  // Leader-line label: dot at (px,py), text at (tx,ty).
  function label(ctx, str, px, py, tx, ty, k, o = {}) {
    o = { color: C.ink, line: C.coral, size: 36, align: tx < px ? 'right' : 'left', ...o }; if (k <= 0) return;
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
    o = { rowH: 86, size: 36, head: C.navy, headColor: '#fff', fill: '#fff', alt: '#F1F6F9', k: 1, rowTimes: null, t: 0, ...o };
    let cy = y; const totalW = colW.reduce((a, b) => a + b, 0);
    rows.forEach((row, ri) => {
      const k = o.rowTimes ? P(o.t, o.rowTimes[ri] ?? 0, 0.5) : clamp(o.k * rows.length - ri);
      if (k > 0) {
        ctx.save(); ctx.globalAlpha *= k;
        ctx.fillStyle = ri === 0 ? o.head : (ri % 2 ? o.fill : o.alt); ctx.fillRect(x, cy, totalW, o.rowH);
        let cx = x; row.forEach((cell, ci) => { text(ctx, String(cell), cx + 22, cy + (o.rowH - o.size * 1.15) / 2, { size: o.size, weight: ri === 0 || ci === 0 ? 700 : 500, color: ri === 0 ? o.headColor : (o.colColors?.[ci] || C.ink), maxW: colW[ci] - 30, accent: C.coral }); cx += colW[ci]; });
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
    o = { kicker: '', title: '', sub: '', emojis: [], bg: 'ocean', ...o };
    bg(ctx, o.bg, t + (s.start || 0));
    const k1 = P(t, 0.1, 0.8), k2 = P(t, 0.4, 0.8), k3 = P(t, 0.9, 0.8);
    if (o.kicker) badge(ctx, o.kicker.toUpperCase(), W / 2 - measureBadge(ctx, o.kicker.toUpperCase(), 30) / 2, 330, { fill: C.coral, alpha: k1, size: 30 });
    text(ctx, o.title, W / 2, 400 + (1 - k2) * 40, { size: 104, weight: 800, color: '#fff', align: 'center', maxW: 1600, alpha: k2, shadow: true, accent: C.aqua, lh: 1.08 });
    if (o.sub) text(ctx, o.sub, W / 2, 640 + (1 - k3) * 30, { size: 46, weight: 500, color: C.foam, align: 'center', maxW: 1400, alpha: k3 });
    o.emojis.forEach((e, i) => emoji(ctx, e, W / 2 + (i - (o.emojis.length - 1) / 2) * 150, 800 + Math.sin(t * 2 + i) * 10, 96, { scale: pop(t, 1.2 + i * 0.15) }));
  }
  function measureBadge(ctx, label, size) { ctx.save(); ctx.font = `800 ${size}px ${FONT}`; const w = ctx.measureText(label).width + size * 1.3; ctx.restore(); return w; }
  // Quiz question with a countdown ring during the hold after the narration ends.
  function quizQ(ctx, t, s, o = {}) {
    o = { n: 1, q: '', choices: null, emoji: '🤔', ...o };
    bg(ctx, 'deep', t + 100);
    badge(ctx, `QUIZ · QUESTION ${o.n}`, 120, 150, { fill: C.sun, color: C.navy, scale: pop(t, 0.1), size: 32 });
    text(ctx, o.q, 120, 240, { size: 68, weight: 700, color: '#fff', maxW: 1250, alpha: P(t, 0.3, 0.6), accent: C.aqua });
    if (o.choices) o.choices.forEach((c, i) => { const k = P(t, 0.8 + i * 0.25, 0.5); card(ctx, 120, 560 + i * 120, 1000, 96, { fill: 'rgba(255,255,255,0.1)', shadow: false, alpha: k, r: 20 }); text(ctx, `${String.fromCharCode(65 + i)}.  ${c}`, 160, 580 + i * 120, { size: 44, weight: 600, color: '#fff', alpha: k }); });
    emoji(ctx, o.emoji, 1560, 420, 220, { scale: pop(t, 0.5), rot: Math.sin(t * 2) * 0.06 });
    const holdStart = s.end, k = clamp((t - holdStart) / Math.max(0.1, s.dur - holdStart - 0.3));
    if (t > holdStart - 0.2) { const a = P(t, holdStart - 0.2, 0.4); ctx.save(); ctx.globalAlpha *= a; ring(ctx, 1560, 780, 90, 1 - k, { color: C.sun }); text(ctx, String(Math.max(1, Math.ceil((1 - k) * (s.dur - holdStart - 0.3)))), 1560, 735, { size: 80, weight: 800, color: '#fff', align: 'center' }); ctx.restore(); }
  }
  // Quiz answer: big check + answer + explanation.
  function quizA(ctx, t, s, o = {}) {
    o = { answer: '', why: '', ...o };
    bg(ctx, 'deep', t + 100);
    const k = pop(t, 0.05, 0.6);
    circle(ctx, 260, 470, 120 * k, C.leaf); check(ctx, 262, 470, 130, P(t, 0.3, 0.5), '#fff');
    text(ctx, o.answer, 460, 360, { size: 96, weight: 800, color: C.sun, alpha: P(t, 0.2, 0.5), maxW: 1340 });
    text(ctx, o.why, 460, 500, { size: 50, weight: 500, color: '#fff', alpha: P(t, 0.8, 0.6), maxW: 1300, accent: C.aqua });
  }
  // Recap checklist on paper.
  function recap(ctx, t, s, items, times, o = {}) {
    bg(ctx, 'paper');
    heading(ctx, o.title || 'Recap', t, { kicker: o.kicker || 'In 30 seconds' });
    const gap = o.gap || 130, ch = gap - 24, size = o.size || 44;
    items.forEach((it, i) => { const k = P(t, times[i] ?? 0, 0.5); const y = 250 + i * gap; card(ctx, 120, y, 1680, ch, { fill: '#fff', alpha: k, r: 22 }); check(ctx, 190, y + ch / 2, 60, P(t, (times[i] ?? 0) + 0.2, 0.5)); const m = measure(ctx, it, { size, maxW: 1480, weight: 600 }).h; text(ctx, it, 260, y + (ch - m) / 2 - 2, { size, weight: 600, color: C.ink, maxW: 1480, alpha: k, accent: C.teal }); });
    if (o.next) text(ctx, o.next, W / 2, o.nextY || 840, { size: 40, weight: 700, color: C.sea, align: 'center', alpha: P(t, o.nextAt ?? s.end - 3, 0.6) });
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
    ctx.save(); ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.fillRect(0, 0, W, 8); ctx.fillStyle = C.teal; ctx.fillRect(0, 0, W * k, 8); ctx.restore();
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
    if (!sc) { bg(ctx, 'deep', gt); text(ctx, `missing scene: ${ts.id}`, W / 2, H / 2, { align: 'center', color: '#fff' }); }
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

  window.Engine = { W, H, C, E, FONT, HAND, P, pop, clamp, lerp, rng, noise, text, measure, rr, card, circle, arrow, line, check, cross, assets, img, drawImg, clip, bg, heading, badge, tip, bullets, label, wander, molecule, membrane, ring, table, emoji, titleCard, quizQ, quizA, recap, imgs, get pending() { return pending; }, waitLoads: () => pending ? new Promise(r => waiters.push(r)) : Promise.resolve() };
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
