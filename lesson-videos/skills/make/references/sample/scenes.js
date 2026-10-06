// Sample chapter: The Water Cycle. Shows the idioms: cue-synced reveals, heading, tip, quiz, recap.
const { W, H, C, E, P, pop, text, card, arrow, bg, heading, tip, bullets, emoji, titleCard, quizQ, quizA, recap, wander, circle } = Engine;

scene('hook', (g, t, s) => titleCard(g, t, s, { kicker: 'Science review', title: 'The *Water Cycle*', sub: 'where every raindrop has been', emojis: ['☀️', '☁️', '🌧️', '🌊'] }), { bug: false, sfx: [[1.2, 'sparkle0', -12]] });

scene('evaporation', (g, t, s) => {
  bg(g, 'paper');
  heading(g, 'Step 1: *Evaporation*', t, { kicker: 'Liquid → gas' });
  const sun = s.cue('sun'), vap = s.cue('vapor'), rem = s.cue('Remember');
  emoji(g, '☀️', 1560, 300, 200, { scale: pop(t, sun), rot: t * 0.1 });
  g.save(); g.fillStyle = C.water; g.fillRect(120, 600, 1680, 150); g.restore();
  text(g, 'ocean / lake (liquid)', 160, 640, { size: 40, weight: 700, color: '#fff' });
  const k = P(t, vap, 1.2);
  for (let i = 0; i < 26; i++) {
    const [x] = wander(i, t, { x: 180, y: 300, w: 1300, h: 280 }, 3);
    circle(g, x, 600 - ((t * 60 + i * 37) % 300), 10, 'rgba(79,195,247,0.55)', { alpha: k });
  }
  text(g, 'water *vapor* (invisible gas)', 180, 230, { size: 48, weight: 800, color: C.navy, alpha: k, accent: C.teal });
  tip(g, 'Evaporation = *liquid → gas*', t, rem);
}, { sfx: [['sun', 'pop0', -14], ['vapor', 'zip0', -14]] });

scene('condensation', (g, t, s) => {
  bg(g, 'sand');
  heading(g, 'Step 2: *Condensation*', t, { kicker: 'Gas → droplets' });
  const cold = s.cue('cold'), drop = s.cue('droplets'), cloud = s.cue('cloud'), trap = s.cue('trap');
  card(g, 120, 220, 760, 120, { fill: '#fff', alpha: P(t, cold) });
  text(g, 'cold air up high 🥶', 160, 250, { size: 50, weight: 700, color: C.sea, alpha: P(t, cold) });
  for (let i = 0; i < 40; i++) {
    const [x, y] = wander(i, t, { x: 1000, y: 260, w: 700, h: 260 }, 7);
    circle(g, x, y, 7, C.water, { alpha: P(t, drop + i * 0.03, 0.4) });
  }
  emoji(g, '☁️', 1350, 640, 300, { scale: pop(t, cloud) });
  tip(g, 'Clouds are *liquid droplets*, not gas!', t, trap, { label: 'TRAP!' });
}, { sfx: [['cloud', 'pop2', -12], ['trap', 'thump0', -14]] });

scene('precipitation', (g, t, s) => {
  bg(g, 'paper');
  heading(g, 'Step 3: *Precipitation*', t, { kicker: 'Droplets fall' });
  const fall = s.cue('fall'), forms = [['🌧️', 'rain'], ['❄️', 'snow'], ['🌨️', 'sleet'], ['🧊', 'hail']];
  forms.forEach(([e, word], i) => {
    const at = s.cue(word);
    card(g, 140 + i * 420, 260, 360, 300, { fill: '#fff', alpha: P(t, at) });
    emoji(g, e, 320 + i * 420, 370, 130, { scale: pop(t, at) });
    text(g, word, 320 + i * 420, 470, { size: 50, weight: 800, color: C.navy, align: 'center', alpha: P(t, at) });
  });
  const again = s.cue('again');
  arrow(g, 1500, 820, 420, 820, { color: C.teal, w: 10, prog: P(t, again, 1.2), bend: -0.25 });
  text(g, 'and the cycle starts again', 960, 650, { size: 44, weight: 700, color: C.teal, align: 'center', alpha: P(t, again) });
}, { sfx: [['rain', 'pop0', -14], ['snow', 'pop1', -14], ['sleet', 'pop2', -14], ['hail', 'pop3', -14], ['again', 'zip1', -14]] });

scene('q1', (g, t, s) => quizQ(g, t, s, { n: 1, q: 'A puddle *disappears* on a sunny afternoon. Which step?', choices: ['Evaporation', 'Condensation', 'Precipitation'], emoji: '☀️' }), { dark: true, sfx: [[0.1, 'pluck2', -10]] });
scene('a1', (g, t, s) => quizA(g, t, s, { answer: 'Evaporation', why: 'The sun turned the *liquid* into *water vapor*.' }), { dark: true, sfx: [[0.1, 'sparkle1', -12]] });

scene('outro', (g, t, s) => recap(g, t, s, [
  '*Evaporation:* liquid → gas (the sun heats water)',
  '*Condensation:* gas → droplets (cold air, clouds)',
  '*Precipitation:* droplets fall (rain, snow, sleet, hail)',
], [s.cue('evaporation'), s.cue('condensation'), s.cue('precipitation')], { title: 'The water cycle in 30 seconds', kicker: 'Recap' }));
