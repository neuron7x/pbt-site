'use strict';
/* Фізика руху «Гусениці» й масла (web/js/physics.js) — інваріантна до частоти кадрів.
   Аудит 24.11 (п.46): покадрові сталі давали τ 221 мс @30 Гц і 55 мс @120 Гц, гравітацію ×4 між 60 і 120 Гц.
   Інваріант: та сама подія, промодельована з кроком 1/30, 1/60, 1/120, 1/144 с, дає ту саму траєкторію (≤ 2 % шляху). */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { PHYS, approach, oilAdvance } = require(path.join(__dirname, '..', 'web', 'js', 'physics.js'));

const HZ = [30, 60, 120, 144];
const drop = () => ({ x: 100, y: 0, r: 0, rMax: 3.4, phase: 0, t: 0, bead: 400, vy: 0, vx: 0, rem: 1, life: 0 });

/** стан краплі в моменти T (мс) при кроці dt; ланцюг рухається зі сталою швидкістю 0,3 px/мс */
function sample(hz, times) {
  const d = drop(), dt = 1000 / hz, out = [];
  let t = 0, alive = true;
  for (const T of times) {
    while (alive && t + dt <= T + 1e-9) { alive = oilAdvance(d, dt, 0.3); t += dt; }
    if (alive && T - t > 1e-9) { alive = oilAdvance(d, T - t, 0.3); t = T; }
    out.push({ x: d.x, y: d.y, alive });
  }
  return out;
}

test('oil drop trajectory is the same at 30, 60, 120 and 144 Hz (≤ 2 % of path)', () => {
  const times = [200, 450, 600, 800, 1000, 1200];
  const ref = sample(240, times);                                          // дрібний крок як еталон
  const span = Math.max(...ref.map(p => p.y)) || 1;
  for (const hz of HZ) {
    const got = sample(hz, times);
    got.forEach((p, i) => {
      assert.ok(Math.abs(p.y - ref[i].y) <= 0.02 * span + 0.05, `${hz} Hz @${times[i]} ms: y ${p.y.toFixed(2)} vs ${ref[i].y.toFixed(2)}`);
      assert.ok(Math.abs(p.x - ref[i].x) <= 0.02 * Math.abs(ref[i].x - 100) + 0.5, `${hz} Hz @${times[i]} ms: x ${p.x.toFixed(2)} vs ${ref[i].x.toFixed(2)}`);
    });
  }
});

test('belt easing reaches the same point in the same wall time at any refresh rate', () => {
  for (const hz of HZ) {
    let pos = 0; const dt = 1000 / hz;
    const n = Math.floor(300 / dt + 1e-9);
    for (let i = 0; i < n; i++) pos = approach(pos, 1000, dt, PHYS.beltTau);
    pos = approach(pos, 1000, 300 - n * dt, PHYS.beltTau);                 // залишок кроку: рівно 300 мс настінного часу
    const exact = 1000 * (1 - Math.exp(-300 / PHYS.beltTau));
    assert.ok(Math.abs(pos - exact) < 0.5, `${hz} Hz: ${pos.toFixed(2)} vs ${exact.toFixed(2)}`);
  }
});

test('a stalled tab (dt = 2 s) cannot teleport a drop: step is clamped to dtMax', () => {
  const d1 = drop(), d2 = drop();
  oilAdvance(d1, 2000, 0); oilAdvance(d2, PHYS.dtMax, 0);
  assert.deepEqual({ x: d1.x, y: d1.y, t: d1.t }, { x: d2.x, y: d2.y, t: d2.t });
});

test('falling speed is capped (viscous drag), life is bounded in wall time', () => {
  const d = drop();
  let alive = true, t = 0;
  while (alive && t < 10000) { alive = oilAdvance(d, 1000 / 60, 0); t += 1000 / 60; }
  assert.ok(d.vy <= PHYS.vMax + 1e-12);
  assert.ok(Math.abs(t - PHYS.life) <= 1000 / 60 + 1e-9, `life ${t}`);
});

/* ── аліасинг текстури траків (аудит п.47) ──
   Стрічка їде 0,55 × прокрутки, крок траків 16 px. Без насичення: > 873 px/с @60 Гц візерунок за кадр зсувається
   більше ніж на пів кроку — ланцюг стоїть або їде назад. Інваріант: за будь-якої швидкості прокрутки 0…10 000 px/с
   і частоти 30/60/120/144 Гц видимий крок за кадр < p/4 і того ж знака; де справжній крок ≥ p/2 — різкий шар
   переважно змазаний (smear ≥ 0,75). */
const { texStep } = require(path.join(__dirname, '..', 'web', 'js', 'physics.js'));
const lcg = seed => () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32;

test('texture step per frame stays below p/4, never reverses, smears where it would alias (0…10 000 px/s)', () => {
  const q = PHYS.pitch / 4, rnd = lcg(47);
  const speeds = [0, 1, 50, 300, 873, 1745, 3000, 8000, 10000];
  for (let i = 0; i < 400; i++) speeds.push(rnd() * 10000);
  for (const hz of [...HZ, 240]) for (const v of speeds) for (const dir of [1, -1]) {
    const raw = dir * v * PHYS.beltRatio / hz;                             // справжній зсув стрічки за кадр, px
    const { step, smear } = texStep(raw);
    assert.ok(Math.abs(step) < q, `${hz} Hz, ${v.toFixed(0)} px/s: |step| ${Math.abs(step).toFixed(2)} ≥ p/4`);
    if (raw !== 0) assert.equal(Math.sign(step), Math.sign(raw), `${hz} Hz, ${v} px/s: reversed`);
    if (Math.abs(raw) >= PHYS.pitch / 2) assert.ok(smear >= .75, `${hz} Hz, ${v.toFixed(0)} px/s: raw ${raw.toFixed(1)} px, smear ${smear}`);
    assert.ok(smear >= 0 && smear <= PHYS.smearMax);
  }
});

test('slow scroll is untouched: texture follows the belt within 2 %, no smear', () => {
  for (const raw of [.05, .3, .8, 1, 1.4]) {                              // до ≈ 150 px/с прокрутки @60 Гц
    const { step, smear } = texStep(raw);
    assert.ok(Math.abs(step - raw) <= .02 * raw + 1e-12, `${raw}: ${step}`);
    assert.equal(smear, 0);
  }
  assert.deepEqual(texStep(0), { step: 0, smear: 0 });
});

test('smear rises monotonically with speed (no flicker band)', () => {
  let last = -1;
  for (let raw = 0; raw <= 40; raw += .05) { const { smear } = texStep(raw); assert.ok(smear >= last - 1e-12, `${raw}`); last = smear; }
});
