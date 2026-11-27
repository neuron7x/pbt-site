'use strict';
/* Єдиний планувальник кадрів (web/js/clock.js). Інваріант кроку А3-core: планувальник поводиться як requestAnimationFrame,
   але просить у браузера один кадр на всі цикли. Перевірка — проти моделі на керованому годиннику. */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

/* Модуль беремо так, щоб його відсутність була збоєм твердження в кожному тесті, а не збоєм запуску файла:
   на базі без планувальника тест мусить бути саме червоним (tools/red_on_base.py), а не «не запущеним». */
let createClock = null;
try { ({ createClock } = require(path.join(__dirname, '..', 'web', 'js', 'clock.js'))); }
catch (e) { if (e.code !== 'MODULE_NOT_FOUND') throw e; }
const need = () => assert.equal(typeof createClock, 'function', 'web/js/clock.js відсутній: єдиного планувальника кадрів немає');

/** керований «браузер»: лічить запити кадру, видає кадр за командою */
function host() {
  const h = { asked: 0, cancelled: 0, live: new Map(), next: 0,
    raf(cb) { h.asked++; const id = ++h.next; h.live.set(id, cb); return id; },
    caf(id) { if (h.live.delete(id)) h.cancelled++; },
    tick(t) { const run = [...h.live.values()]; h.live.clear(); for (const cb of run) cb(t); return run.length; } };
  return h;
}

test('багато запитів за кадр — один запит кадру в браузера; порядок і спільна мітка часу', () => {
  need();
  const h = host(), clock = createClock(h), seen = [];
  for (const name of ['belt', 'oil', 'spark', 'glow']) clock.request(t => seen.push([name, t]));
  assert.equal(h.asked, 1);
  assert.equal(clock.pending(), 4);
  assert.equal(h.tick(1000), 1);
  assert.deepEqual(seen, [['belt', 1000], ['oil', 1000], ['spark', 1000], ['glow', 1000]]);
  assert.equal(clock.pending(), 0);
  assert.equal(h.tick(1016), 0);                      // ніхто не просив — кадрів більше немає
});

test('запит із середини кадру виконується в наступному кадрі, не в цьому', () => {
  need();
  const h = host(), clock = createClock(h), seen = [];
  const loop = t => { seen.push(t); if (seen.length < 3) clock.request(loop); };
  clock.request(loop);
  h.tick(10); assert.deepEqual(seen, [10]);
  h.tick(26); h.tick(42); h.tick(58);
  assert.deepEqual(seen, [10, 26, 42]);
  assert.equal(h.asked, 3);                           // рівно по одному запиту на кадр, у якому хтось живий
});

test('номери ненульові й різні; cancel знімає лише свій запит', () => {
  need();
  const h = host(), clock = createClock(h), seen = [];
  const a = clock.request(() => seen.push('a')), b = clock.request(() => seen.push('b')), c = clock.request(() => seen.push('c'));
  assert.ok(a && b && c);
  assert.equal(new Set([a, b, c]).size, 3);
  clock.cancel(b); clock.cancel(b); clock.cancel(0); clock.cancel(9999);
  h.tick(5);
  assert.deepEqual(seen, ['a', 'c']);
  assert.equal(h.cancelled, 0);                       // кадр ще потрібен решті — у браузера його не скасовано
});

test('знято останній запит — кадр у браузера скасовано, і новий запит просить його знову', () => {
  need();
  const h = host(), clock = createClock(h);
  let ran = 0;
  const id = clock.request(() => ran++);
  clock.cancel(id);
  assert.equal(h.cancelled, 1);
  assert.equal(h.tick(5), 0);
  clock.request(() => ran++);
  assert.equal(h.asked, 2);
  h.tick(21);
  assert.equal(ran, 1);
});

test('виняток в одному циклі не гасить решту і не ковтається', () => {
  need();
  const h = host(), clock = createClock(h), seen = [];
  clock.request(() => seen.push('before'));
  clock.request(() => { throw new Error('boom'); });
  clock.request(() => { throw new Error('second'); });
  clock.request(() => seen.push('after'));
  assert.throws(() => h.tick(7), /boom/);             // назовні йде перша помилка
  assert.deepEqual(seen, ['before', 'after']);
  clock.request(() => seen.push('alive'));            // планувальник після збою працює
  h.tick(23);
  assert.deepEqual(seen, ['before', 'after', 'alive']);
});

test('властивість: випадкові цикли на планувальнику дають ту саму послідовність, що й на «сирому» rAF', () => {
  need();
  let seed = 20261127;
  const rnd = () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32;
  for (let round = 0; round < 200; round++) {
    const plan = Array.from({ length: 1 + Math.floor(rnd() * 5) }, (_, i) => ({ name: i, frames: 1 + Math.floor(rnd() * 6), stopAt: rnd() < .3 ? Math.floor(rnd() * 4) : -1 }));
    const run = (request, cancel, tick) => {
      const log = [], ids = new Map();
      for (const p of plan) {
        let left = p.frames;
        const loop = t => { log.push(`${p.name}@${t}`); if (--left > 0) ids.set(p.name, request(loop)); };
        ids.set(p.name, request(loop));
      }
      for (let f = 0; f < 8; f++) {
        for (const p of plan) if (p.stopAt === f) cancel(ids.get(p.name));
        tick(f * 16);
      }
      return log;
    };
    const raw = host(), viaRaw = run(cb => raw.raf(cb), id => raw.caf(id), t => raw.tick(t));
    const h = host(), clock = createClock(h), viaClock = run(fn => clock.request(fn), id => clock.cancel(id), t => h.tick(t));
    assert.deepEqual(viaClock, viaRaw, `раунд ${round}`);
    assert.ok(h.asked <= 8);                          // не більше одного запиту кадру на кадр
  }
});
