/* ПЛЕЙНБУД · єдиний планувальник кадрів (А3-core, крок 2). Усі декоративні цикли сторінки просять кадр тут, а не в
   requestAnimationFrame напряму: скільки б циклів не жило водночас, браузер отримує ОДИН запит кадру. Це та сама
   семантика, що й у requestAnimationFrame — тому перенесення циклів сюди не міняє поведінки, — і єдине місце, де далі
   з'являться спільні правила (видимість вкладки, пауза за фокусом форми, бюджет циклів).
   Чистий модуль: кадр і скасування — ін'єктовані (у браузері — справжні, у тесті — керований годинник). */
(function (root, make) {
  'use strict';
  const api = make();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.PBTClock = api;
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';
  /**
   * @param {{ raf: (cb: (t: number) => void) => number, caf: (id: number) => void }} env
   * @returns {{ request: (fn: (t: number) => void) => number, cancel: (id: number) => void, pending: () => number }}
   */
  function createClock(env) {
    /** @type {Map<number, (t: number) => void>} */
    let queue = new Map();
    let next = 0, handle = 0, armed = false;
    function frame(t) {
      armed = false;
      const batch = queue;                            // запит із середини кадру потрапляє в наступний, як у браузері
      queue = new Map();
      let failed = false, error;
      for (const fn of batch.values()) {
        try { fn(t); } catch (e) { if (!failed) { failed = true; error = e; } }   // збій одного циклу не гасить решту
      }
      if (failed) throw error;                        // але й не ковтається: перша помилка доходить до консолі
    }
    return {
      /** Поставити fn на наступний кадр. Повертає ненульовий номер для cancel. */
      request(fn) {
        const id = ++next;
        queue.set(id, fn);
        if (!armed) { armed = true; handle = env.raf(frame); }
        return id;
      },
      /** Зняти запит. Невідомий, уже виконаний чи нульовий номер — без дії. */
      cancel(id) {
        if (!queue.delete(id)) return;
        if (!queue.size && armed) { armed = false; env.caf(handle); }   // нікого не лишилось — кадр браузеру не потрібен
      },
      pending() { return queue.size; },
    };
  }
  return { createClock };
});
