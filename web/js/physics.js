/* ПЛЕЙНБУД · фізика руху «Гусениці» й масла: чисті функції, інтегрування за часом dt (мс). */
(function (root, make) {
  'use strict';
  const api = make();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.PBTPhysics = api;
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';
  /* фізика:початок — чисті функції руху; інтегруються за часом dt (мс), не за кадрами: однаково на 30, 60, 120 і 144 Гц.
     Сталі відкалібровано так, щоб на 60 Гц рух збігся з попередньою покадровою версією; dt обрізано до 50 мс (згорнута вкладка). */
  const PHYS = Object.freeze({ beltTau: 110, beltRatio: .55, gravity: 5.76e-4, vMax: .33, driftTau: 408, life: 4000,
    neckMs: 167, neckV0: .033, neckA: 1.8e-4, fallV0: .054, remRate: .006, dtMax: 50 });
  /** Експоненційне наближення до цілі: k = 1 − e^(−dt/τ) — інваріантне до частоти кадрів. */
  const approach = (pos, target, dt, tau) => target + (pos - target) * Math.exp(-Math.min(dt, PHYS.dtMax) / tau);
  /** Один крок краплі масла; beltV — швидкість ланцюга, px/мс. Повертає false, коли крапля прожила своє. */
  function oilAdvance(d, dtRaw, beltV, carried) {
    let dt = Math.min(dtRaw, PHYS.dtMax);
    if (!carried) d.life += dt;
    if (d.phase === 0) {                                                 // набрякає й їде з ланцюгом (¼ його ходу)
      const over = Math.max(0, d.t + dt - d.bead); dt -= over; d.t += dt;
      d.x -= beltV * dt * .25; d.r = d.rMax * (1 - Math.pow(1 - Math.min(1, d.t / d.bead), 3)); d.y = d.r * .9;
      if (d.t >= d.bead) { d.phase = 1; d.t = 0; if (over > 0) oilAdvance(d, over, beltV, true); }   // залишок кроку — у наступну фазу
    } else if (d.phase === 1) {                                          // в'язка шийка: рівноприскорено
      const over = Math.max(0, d.t + dt - PHYS.neckMs); dt -= over; d.t += dt;
      d.x -= beltV * dt * .15; d.y += (PHYS.neckV0 + PHYS.neckA * (d.t - dt / 2)) * dt;
      if (d.t >= PHYS.neckMs) { d.phase = 2; d.t = 0; d.vy = PHYS.fallV0; d.vx = -beltV * .12; if (over > 0) oilAdvance(d, over, beltV, true); }
    } else {
      d.t += dt;                                                             // вільне падіння зі стелею швидкості (в'язкий опір)
      const v1 = Math.min(d.vy + PHYS.gravity * dt, PHYS.vMax);
      d.y += (d.vy + v1) / 2 * dt; d.vy = v1;
      d.x += d.vx * PHYS.driftTau * (1 - Math.exp(-dt / PHYS.driftTau)); d.vx *= Math.exp(-dt / PHYS.driftTau);
      d.rem = Math.max(0, d.rem - PHYS.remRate * dt);
    }
    return d.life <= PHYS.life;
  }
  return Object.freeze({ PHYS, approach, oilAdvance });
});
