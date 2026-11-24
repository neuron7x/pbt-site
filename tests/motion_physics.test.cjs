'use strict';
/* Фізика руху «Гусениці» й масла (web/js/site.js, блок «фізика:початок … фізика:кінець») — інваріантна до частоти кадрів.
   Аудит 24.11 (п.46): покадрові сталі давали τ 221 мс @30 Гц і 55 мс @120 Гц, гравітацію ×4 між 60 і 120 Гц.
   Інваріант: та сама подія, промодельована з кроком 1/30, 1/60, 1/120, 1/144 с, дає ту саму траєкторію (≤ 2 % шляху). */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, '..', 'web', 'js', 'site.js'), 'utf8');
const a = src.indexOf('/* фізика:початок'), b = src.indexOf('/* фізика:кінець */');
assert.ok(a > 0 && b > a, 'physics block not found');
const ctx = {};
vm.runInNewContext(src.slice(a, b) + '\nthis.PHYS = PHYS; this.approach = approach; this.oilAdvance = oilAdvance;', ctx);
const { PHYS, approach, oilAdvance } = ctx;

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
