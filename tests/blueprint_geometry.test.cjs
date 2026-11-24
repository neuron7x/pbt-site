'use strict';
/* Чиста геометрія креслень (web/js/blueprint.js) без браузера: детерміновані property-тести на сіяному генераторі.
   Інваріанти:
   (1) виліт від п'яти стріли — проєкції довжини: |√(r² + h²) − L| ≤ похибка округлення до 0,1 м;
   (2) r спадає, h зростає з кутом на [0°, 90°];
   (3) поза областю визначення — null, а не число (fail-closed);
   (4) метри розбираються лише у формі «N м» / «N,N м»; тонни, порожнє, сміття — null;
   (5) кожна одиниця каталогу має клас креслення, класи — зі скінченного словника. */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');

const BP = require(path.join(__dirname, '..', 'web', 'js', 'blueprint.js'));

let seed = 0x5eed2411;
const rand = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) | 0) >>> 0) / 4294967296;

test('reach: Pythagorean closure within rounding, 5000 seeded cases', () => {
  for (let i = 0; i < 5000; i++) {
    const L = Math.round((1 + rand() * 99) * 10) / 10, a = Math.round(rand() * 900) / 10;
    const m = BP.reach(L, a);
    assert.ok(m, `${L} ${a}`);
    assert.ok(Math.abs(Math.hypot(m.r, m.h) - L) <= 0.0708 + 1e-9, `${L} @ ${a}°: r=${m.r} h=${m.h}`);   // ≤ √2 · 0,05
    assert.ok(m.r >= 0 && m.h >= 0 && m.r <= L && m.h <= L);
  }
});

test('reach: radius non-increasing and height non-decreasing in angle', () => {
  for (let i = 0; i < 400; i++) {
    const L = 5 + rand() * 80;
    let prev = BP.reach(L, 0);
    for (let a = 1; a <= 90; a++) {
      const m = BP.reach(L, a);
      assert.ok(m.r <= prev.r && m.h >= prev.h, `${L} ${a}`);
      prev = m;
    }
  }
  assert.deepEqual(BP.reach(42, 0), { r: 42, h: 0 });
  assert.deepEqual(BP.reach(42, 90), { r: 0, h: 42 });
});

test('reach: outside the domain is null, never a number', () => {
  for (const [L, a] of [[0, 30], [-1, 30], [NaN, 30], [null, 30], [undefined, 30], [42, -0.1], [42, 90.1], [42, NaN], [Infinity, 10], [42, Infinity], ['42', 30]]) {
    assert.equal(BP.reach(L, a), null, `${L} ${a}`);
  }
});

test('meters: only «N м» parses; tonnes, litres and junk are null', () => {
  const ok = { '22 м': 22, '16,5 м': 16.5, '70 м': 70, '4 м': 4 };
  for (const [s, v] of Object.entries(ok)) assert.equal(BP.meters(s), v, s);
  for (const s of ['22 т', '11 л', '', ' м', '5', 'м 5', '5 мм', '1e3 м', '-5 м', null, undefined]) assert.equal(BP.meters(s), null, String(s));
});

test('every catalogue unit maps to one of the fixed drawing classes', () => {
  const src = fs.readFileSync(path.join(__dirname, '..', 'web', 'js', 'data.js'), 'utf8');
  const D = JSON.parse(src.slice(src.indexOf('{'), src.lastIndexOf('}') + 1));
  const classes = new Set(Object.keys(BP.CLASS));
  assert.equal(D.fleet.length, 32);
  for (const u of D.fleet) assert.ok(classes.has(BP.kind(u)), `${u.id} → ${BP.kind(u)}`);
  assert.equal(BP.kind({ cat: 'unknown', name: 'x' }), null);
});
