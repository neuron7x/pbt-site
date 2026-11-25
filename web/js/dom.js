/* ПЛЕЙНБУД · фабрика DOM: єдине місце, де код сторінки створює елементи й ставить атрибути (білий список). Без HTML-рядків. */
(function (root, make) {
  'use strict';
  const api = make();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.PBTDom = api;
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';
  /* Розмітку будуємо лише вузлами DOM: текст → Text, атрибути → setAttribute. Жодного HTML-рядка, отже жодного
     синку розбору (OWASP DOM-based XSS Prevention, правило «безпечні синки»; W3C Trusted Types: require-trusted-types-for 'script'). */
  function el(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    for (const k in attrs || {}) {
      const v = attrs[k];
      if (v == null || v === false) continue;
      if (k === 'class') n.className = v;
      else if (k === 'style') for (const p in v) n.style.setProperty(p, v[p]);
      else if (attrOk(k, v)) n.setAttribute(k, v === true ? '' : String(v));
    }
    append(n, kids);
    return n;
  }
  /* Вартовий атрибутів фабрики (fail-closed): обробники подій не ставляться ніколи; адреси — лише з дозволених схем.
     href: https:, mailto:, tel:, viber://chat, якір або відносний шлях того ж походження; src/poster/srcset: відносний шлях або
     data:image|video (однофайлова збірка). Усе інше — атрибут не ставиться (javascript:, data:text/html, //чужий-хост). */
  const URL_ATTR = { href: /^(?:https:\/\/|mailto:|tel:|viber:\/\/chat\?number=|#|(?![a-z][a-z0-9+.-]*:|\/\/)[\w./?=&%-]*$)/i,
    src: /^(?:data:(?:image|video)\/[\w.+-]+;base64,|(?![a-z][a-z0-9+.-]*:|\/\/)[\w./-]+$)/i };
  URL_ATTR.poster = URL_ATTR.src;
  URL_ATTR.srcset = /^(?:(?![a-z][a-z0-9+.-]*:|\/\/)[\w./-]+ \dx(?:, (?![a-z][a-z0-9+.-]*:|\/\/)[\w./@-]+ \dx)*)$/i;
  /* Білий список імен (fail-closed): лише атрибути, які сайт реально вживає, плюс data-* і aria-* (не виконуються).
     Невідоме ім'я не ставиться (вбудований документ, formaction, action, xlink:href, ping, data) — так само, як on*. */
  const ATTR_NAMES = new Set(['alt', 'decoding', 'height', 'href', 'id', 'loading', 'poster', 'rel', 'scope', 'src', 'srcset',
    'tabindex', 'target', 'type', 'value', 'width']);
  function attrOk(k, v) {
    const name = k.toLowerCase();
    if (!ATTR_NAMES.has(name) && !/^(?:data|aria)-[a-z][a-z0-9-]*$/.test(name)) return false;
    const rule = URL_ATTR[name];
    return !rule || rule.test(String(v));
  }
  function append(n, kids) {
    for (const k of kids) {
      if (k == null || k === false) continue;
      if (Array.isArray(k)) append(n, k);
      else n.append(typeof k === 'string' || typeof k === 'number' ? String(k) : k);
    }
    return n;
  }
  const fill = (n, ...kids) => { n.replaceChildren(); return append(n, kids); };
  return Object.freeze({ el, append, fill, attrOk });
});
