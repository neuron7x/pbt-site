/* ПБТ · чисте ядро кошторису. Без DOM, мережі, часу й побічних ефектів.
   Інваріант: невідома вартість доставки НІКОЛИ не стає нулем. */
(function (root, make) {
  'use strict';
  const api = make();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.PBTQuote = api;
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';
  const validInt = (n, lo, hi) => Number.isSafeInteger(n) && n >= lo && n <= hi;

  function massTonnes(specs) {
    if (!Array.isArray(specs)) return null;
    const masses = specs.filter(s => s && typeof s.k === 'string' && /^(?:Маса|Вага)(?:\s|$)/i.test(s.k));
    if (masses.length !== 1) return null; // Дублікат або конфлікт метаданих: fail-closed.
    const found = String(masses[0].v == null ? '' : masses[0].v).trim()
      .match(/^(\d+(?:[.,]\d+)?)\s*т$/i);
    if (!found) return null;
    const mass = Number(found[1].replace(',', '.'));
    return Number.isFinite(mass) && mass > 0 ? mass : null;
  }

  function selectTrailer(specs, trailers) {
    const mass = massTonnes(specs);
    if (mass === null) return Object.freeze({ reason: 'mass-unknown', trailer: null });
    if (!Array.isArray(trailers) || !trailers.length)
      return Object.freeze({ reason: 'tariff-invalid', trailer: null });
    // O(T) часу, O(1) пам'яті. Перевіряємо ВСІ ставки: погані дані
    // не можна ігнорувати лише тому, що інший трал уже підходить.
    let best = null;
    for (const t of trailers) {
      if (!t || typeof t.name !== 'string' || !t.name.trim() ||
          !Number.isFinite(t.maxT) || t.maxT <= 0 ||
          !validInt(t.rate, 1, Number.MAX_SAFE_INTEGER))
        return Object.freeze({ reason: 'tariff-invalid', trailer: null });
      if (mass > t.maxT) continue;
      if (!best || t.maxT < best.maxT ||
          (t.maxT === best.maxT && (t.rate < best.rate ||
           (t.rate === best.rate && t.name < best.name)))) best = t;
    }
    if (!best) return Object.freeze({ reason: 'capacity-exceeded', trailer: null });
    return Object.freeze({ reason: null, trailer: Object.freeze({
      name: best.name, maxT: best.maxT, rate: best.rate,
    }) });
  }

  function quote(unit, trailers, hours, km) {
    if (!unit || unit.unit !== 'год' || !validInt(unit.price, 1, Number.MAX_SAFE_INTEGER) ||
        !validInt(hours, 1, 5000) || !validInt(km, 0, 3000)) return null;
    const rental = unit.price * hours;
    if (!Number.isSafeInteger(rental)) return null;

    const result = (status, reason, delivery, trailer) => {
      const total = status === 'complete' ? rental + delivery : null;
      if (total !== null && !Number.isSafeInteger(total)) return null;
      return Object.freeze({
        status, reason, rental, delivery, total,
        displayed: rental + (delivery === null ? 0 : delivery), trailer,
      });
    };
    if (unit.cat === 'crane') return result('rent-only', 'crane-arrival', null, null);
    if (km === 0) return result('complete', 'no-delivery', 0, null);
    const chosen = selectTrailer(unit.specs, trailers);
    if (chosen.trailer === null) return result('rent-only', chosen.reason, null, null);
    const delivery = km * chosen.trailer.rate;
    if (!Number.isSafeInteger(delivery)) return null;
    return result('complete', null, delivery, chosen.trailer);
  }

  // Сумісність попереднього числового API. Для кранів це *лише оренда*.
  function legacyTotal(unit, trailers, hours, km) {
    const q = quote(unit, trailers, hours, km);
    return q === null ? null : q.status === 'complete' ? q.total :
      unit.cat === 'crane' ? q.rental : null;
  }

  return Object.freeze({ massTonnes, selectTrailer, quote, legacyTotal });
});
