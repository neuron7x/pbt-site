'use strict';
/* Фабрика DOM сторінки (web/js/dom.js: el/attrOk/append/fill) — єдина точка, де код ставить атрибути.
   Вартовий fail-closed: обробники on* не ставляться; href/src/poster/srcset — лише дозволені схеми.
   Модуль імпортується напряму (не вирізка), виконується з мінімальним DOM. */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function node(tag) {
  return { tag, attrs: {}, kids: [], style: { props: {}, setProperty(k, v) { this.props[k] = v; } },
    setAttribute(k, v) { this.attrs[k] = v; }, set className(v) { this.attrs.class = v; },
    append(...k) { this.kids.push(...k); }, replaceChildren() { this.kids = []; } };
}
global.document = { createElement: node };                                  // мінімальний DOM для модуля
const { el, fill } = require(path.join(__dirname, '..', 'web', 'js', 'dom.js'));

test('event handler attributes are never set, whatever the case', () => {
  for (const k of ['onclick', 'onerror', 'ONLOAD', 'onMouseOver', 'onfocus']) {
    assert.equal(k in el('div', { [k]: 'alert(1)' }).attrs, false, k);
  }
});

test('attribute names are a whitelist: unknown names are never set', () => {
  for (const k of ['srcdoc', 'formaction', 'action', 'xlink:href', 'ping', 'data', 'style2', 'background', 'dynsrc', 'lowsrc']) {
    assert.equal(k in el('iframe', { [k]: 'x' }).attrs, false, k);
  }
  for (const k of ['alt', 'width', 'data-cat', 'aria-label', 'tabindex', 'rel']) assert.equal(el('a', { [k]: '1' }).attrs[k], '1', k);
  assert.equal('data-1x' in el('a', { 'data-1x': '1' }).attrs, false);               // ім'я data-* має починатися з літери
});

test('href admits only https, mailto, tel, anchors and same-origin relative paths', () => {
  const ok = ['https://t.me/plainbud', 'viber://chat?number=%2B380675550317', 'mailto:a@b.ua', 'tel:+380675550317', '#zapyt', 'js/blueprint.js', 'media/video/a.mp4', '?a=1'];
  for (const v of ok) assert.equal(el('a', { href: v }).attrs.href, v, v);
  const bad = ['javascript:alert(1)', 'JavaScript:alert(1)', ' javascript:alert(1)', 'data:text/html,<script>', 'vbscript:x',
    'http://evil.example', '//evil.example/x', 'viber://forward?text=x', 'file:///etc/passwd', 'java\tscript:alert(1)'];
  for (const v of bad) assert.equal('href' in el('a', { href: v }).attrs, false, v);
});

test('src/poster admit relative paths and base64 image/video data only', () => {
  for (const v of ['media/park/e-1.webp', 'data:image/webp;base64,AAAA', 'data:video/mp4;base64,AAAA']) {
    assert.equal(el('img', { src: v }).attrs.src, v, v);
    assert.equal(el('video', { poster: v }).attrs.poster, v, v);
  }
  for (const v of ['javascript:alert(1)', 'data:text/html;base64,PHNjcmlwdD4=', 'data:image/svg+xml,<svg onload=alert(1)>', 'https://cdn.example/x.webp', '//x/y.webp']) {
    assert.equal('src' in el('img', { src: v }).attrs, false, v);
  }
  assert.equal(el('img', { srcset: 'media/m.webp 1x, media/m@2x.webp 2x' }).attrs.srcset, 'media/m.webp 1x, media/m@2x.webp 2x');
  assert.equal('srcset' in el('img', { srcset: 'javascript:x 1x' }).attrs, false);
});

test('text is always a text node: markup in data stays inert', () => {
  const n = el('p', null, '<img src=x onerror=alert(1)>', 42, null, false, ['a', ['b']]);
  assert.deepEqual(n.kids, ['<img src=x onerror=alert(1)>', '42', 'a', 'b']);
  fill(n, 'x');
  assert.deepEqual(n.kids, ['x']);
});
