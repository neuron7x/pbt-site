/* ПЛЕЙНБУД · креслення техніки. Чисте SVG через DOM API (без innerHTML), без залежностей.
   Контур — умовний для класу машини; числа на кресленні беруться ЛИШЕ з характеристик каталогу
   (маса, стріла, вантажопідйомність, довжина, відвал). Невідоме не малюється розміром. */
(function (root, make) {
  'use strict';
  const api = make();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.PBTBlueprint = api;
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const W = 400, H = 240, G = 196;                       // полотно і лінія ґрунту

  /* ── примітиви: рядки path ── */
  const f = n => Math.round(n * 10) / 10;
  const poly = pts => 'M' + pts.map(p => f(p[0]) + ',' + f(p[1])).join(' L') + ' Z';
  const line = (x1, y1, x2, y2) => `M${f(x1)},${f(y1)} L${f(x2)},${f(y2)}`;
  const circ = (cx, cy, r) => `M${f(cx - r)},${f(cy)} a${f(r)},${f(r)} 0 1,0 ${f(2 * r)},0 a${f(r)},${f(r)} 0 1,0 ${f(-2 * r)},0`;
  const rr = (x, y, w, h, r) => `M${f(x + r)},${f(y)} H${f(x + w - r)} Q${f(x + w)},${f(y)} ${f(x + w)},${f(y + r)} V${f(y + h - r)} Q${f(x + w)},${f(y + h)} ${f(x + w - r)},${f(y + h)} H${f(x + r)} Q${f(x)},${f(y + h)} ${f(x)},${f(y + h - r)} V${f(y + r)} Q${f(x)},${f(y)} ${f(x + r)},${f(y)} Z`;
  /* смуга змінної товщини між двома точками — стріла, рукоять, важіль */
  function bar(a, b, w0, w1) {
    const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1, nx = -dy / L, ny = dx / L;
    return poly([[a[0] + nx * w0 / 2, a[1] + ny * w0 / 2], [b[0] + nx * w1 / 2, b[1] + ny * w1 / 2],
      [b[0] - nx * w1 / 2, b[1] - ny * w1 / 2], [a[0] - nx * w0 / 2, a[1] - ny * w0 / 2]]);
  }
  function track(d, x, y, w, h) {
    const r = h / 2;
    d.main.push(rr(x, y, w, h, r));
    d.thin.push(rr(x + 5, y + 5, w - 10, h - 10, r - 5));
    d.thin.push(circ(x + r, y + r, r - 7), circ(x + w - r, y + r, r - 7));
    const n = Math.max(2, Math.floor((w - 2 * h) / 26));
    for (let i = 0; i <= n; i++) d.thin.push(circ(x + h + (w - 2 * h) * i / n, y + h - 9, 5));
    for (let i = 0; i < Math.floor(w / 12); i++) d.hidden.push(line(x + r + i * 12, y + h, x + r + i * 12 + 4, y + h));
  }
  function wheel(d, cx, cy, r) {
    d.main.push(circ(cx, cy, r));
    d.thin.push(circ(cx, cy, r * .62), circ(cx, cy, r * .2));
    d.centre.push(line(cx - r - 5, cy, cx + r + 5, cy), line(cx, cy - r - 5, cx, cy + r + 5));
  }
  function ground(d, x0 = 14, x1 = W - 14) {
    d.ground.push(line(x0, G, x1, G));
    for (let x = x0 + 6; x < x1; x += 11) d.ground.push(line(x, G + 1, x - 7, G + 8));
  }
  const dims = (d, o) => { d.dims.push(o); };

  /* ── класи машин ── */
  function excavator(d, o) {
    const long = !!o.long, x0 = long ? 34 : 58;
    track(d, x0, 164, 188, 32);
    d.thin.push(rr(x0 + 52, 154, 90, 10, 2));                                    // поворотне коло
    d.main.push(poly([[x0 + 8, 154], [x0 + 8, 116], [x0 + 26, 104], [x0 + 112, 104], [x0 + 112, 154]]));   // корпус і противага
    d.main.push(poly([[x0 + 112, 154], [x0 + 112, 70], [x0 + 146, 70], [x0 + 156, 104], [x0 + 156, 154]]));  // кабіна
    d.thin.push(poly([[x0 + 118, 76], [x0 + 142, 76], [x0 + 150, 102], [x0 + 118, 102]]));
    d.main.push(poly([[x0 + 156, 154], [x0 + 156, 116], [x0 + 176, 120], [x0 + 182, 154]]));                // п'ята стріли
    for (let i = 0; i < 5; i++) d.thin.push(line(x0 + 40 + i * 9, 112, x0 + 40 + i * 9, 128));
    d.main.push(line(x0 + 38, 104, x0 + 38, 90));                                // вихлоп
    const P = [x0 + 170, 126], K = long ? [x0 + 268, 22] : [x0 + 242, 46], S = long ? [x0 + 350, 150] : [x0 + 296, 124];
    d.main.push(bar(P, K, 15, 11), bar(K, S, 10, 7));
    d.thin.push(line(x0 + 166, 146, P[0] + (K[0] - P[0]) * .5 + 6, P[1] + (K[1] - P[1]) * .5 + 6));   // гідроциліндр стріли
    d.thin.push(line(P[0] + (K[0] - P[0]) * .7, P[1] + (K[1] - P[1]) * .7 - 9, K[0] + 6, K[1] - 10));
    const [sx, sy] = S;
    d.main.push(poly([[sx, sy], [sx + 18, sy + 14], [sx + 15, sy + 38], [sx - 4, sy + 46], [sx - 16, sy + 36], [sx - 7, sy + 18]]));
    for (let i = 0; i < 3; i++) d.thin.push(line(sx - 4 + i * 6, sy + 46 - i * 3, sx - 8 + i * 6, sy + 52 - i * 3));
    d.centre.push(circ(P[0], P[1], 3), circ(K[0], K[1], 3));
    ground(d);
    if (o.boom) dims(d, { kind: 'along', a: P, b: K, label: `Стріла ${o.boom}`, off: -16 });
    return { pivot: P };
  }
  function amphibian(d, o) {
    const x0 = 30;
    d.main.push(`M${x0 + 10},158 H${x0 + 250} L${x0 + 276},180 Q${x0 + 280},194 ${x0 + 262},194 H${x0 + 22} Q${x0},194 ${x0},178 Z`);   // понтон
    for (let x = x0 + 16; x < x0 + 262; x += 13) d.thin.push(line(x, 182, x, 194));
    d.thin.push(line(x0 + 6, 172, x0 + 268, 172));
    d.water.push('M0,186 ' + Array.from({ length: 21 }, (_, i) => `Q${i * 20 + 5},${i % 2 ? 190 : 182} ${i * 20 + 10},186 T${i * 20 + 20},186`).join(' '));
    d.thin.push(rr(x0 + 70, 150, 90, 8, 2));
    d.main.push(poly([[x0 + 26, 150], [x0 + 26, 112], [x0 + 44, 100], [x0 + 146, 100], [x0 + 146, 150]]));
    d.main.push(poly([[x0 + 146, 150], [x0 + 146, 68], [x0 + 184, 68], [x0 + 196, 104], [x0 + 196, 150]]));
    d.thin.push(poly([[x0 + 152, 74], [x0 + 180, 74], [x0 + 189, 102], [x0 + 152, 102]]));
    const P = [x0 + 178, 124], K = [x0 + 276, 26], S = [x0 + 350, 168];
    d.main.push(bar(P, K, 15, 11), bar(K, S, 10, 7));
    d.thin.push(line(x0 + 168, 108, P[0] + (K[0] - P[0]) * .55, P[1] + (K[1] - P[1]) * .55 + 8));
    const [sx, sy] = S;
    d.hidden.push(poly([[sx, sy], [sx + 16, sy + 10], [sx + 12, sy + 26], [sx - 6, sy + 30], [sx - 14, sy + 20]]));   // ківш під водою — прихована лінія
    d.centre.push(circ(P[0], P[1], 3), circ(K[0], K[1], 3));
    if (o.boom) dims(d, { kind: 'along', a: P, b: K, label: `Стріла ${o.boom}`, off: -16 });
    return { pivot: P };
  }
  function dozer(d) {
    track(d, 78, 164, 206, 32);
    d.main.push(poly([[92, 164], [92, 128], [290, 128], [296, 164]]));           // рама
    d.main.push(poly([[176, 128], [176, 108], [278, 112], [288, 128]]));          // капот
    for (let i = 0; i < 6; i++) d.thin.push(line(196 + i * 12, 112, 196 + i * 12, 126));
    d.main.push(poly([[104, 128], [104, 64], [164, 64], [170, 128]]));            // кабіна з ROPS
    d.thin.push(poly([[112, 72], [156, 72], [161, 112], [112, 112]]));
    d.main.push('M318,98 Q340,146 320,196 L334,196 Q356,146 332,98 Z');           // відвал
    d.thin.push(line(250, 178, 320, 170), line(262, 130, 322, 112));             // штовхач і циліндр
    d.main.push(poly([[92, 138], [58, 144], [56, 152], [92, 150]]));               // рихлитель: балка
    d.main.push(poly([[56, 146], [66, 146], [62, 196], [54, 196]]));                // стояк до ґрунту
    d.hidden.push(poly([[54, 196], [62, 196], [58, 210], [48, 214]]));             // зуб у ґрунті — прихована лінія
    ground(d);
  }
  function crane(d, o) {
    d.main.push(rr(18, 146, 348, 20, 3));                                        // шасі
    d.main.push(poly([[300, 146], [300, 96], [344, 96], [366, 124], [366, 146]]));   // кабіна
    d.thin.push(poly([[306, 102], [340, 102], [356, 124], [306, 124]]));
    [54, 96, 170, 212, 324].forEach(x => wheel(d, x, 178, 17));
    d.main.push(rr(92, 124, 76, 22, 3));                                          // поворотна платформа
    d.main.push(rr(150, 100, 30, 24, 3)); d.thin.push(rr(155, 105, 20, 12, 1));   // кабіна оператора
    d.thin.push(line(36, 166, 26, 194), line(250, 166, 262, 194));                // аутригери
    d.main.push(rr(14, 194, 26, 4, 1), rr(250, 194, 26, 4, 1));
    ground(d);
    const P = [112, 122];
    return { pivot: P, boomLen: 205, angle: o.angle == null ? 38 : o.angle };
  }
  function loader(d, o) {
    wheel(d, 112, 170, 26); wheel(d, 262, 170, 26);
    d.main.push(poly([[64, 168], [64, 118], [150, 118], [170, 146], [170, 168]]));   // задня піврама
    d.main.push(poly([[146, 118], [146, 60], [196, 60], [204, 118]]));                // кабіна
    d.thin.push(poly([[153, 67], [190, 67], [196, 112], [153, 112]]));
    for (let i = 0; i < 5; i++) d.thin.push(line(76 + i * 12, 124, 76 + i * 12, 140));
    d.main.push(rr(176, 136, 116, 26, 3));                                        // передня піврама
    d.centre.push(circ(174, 150, 5));                                             // шарнір зламу
    if (o.drum) {                                                                  // мульчер
      d.main.push(bar([206, 120], [316, 150], 12, 10), circ(334, 170, 24));
      for (let i = 0; i < 10; i++) { const a = i * Math.PI / 5; d.thin.push(line(334 + Math.cos(a) * 24, 170 + Math.sin(a) * 24, 334 + Math.cos(a) * 31, 170 + Math.sin(a) * 31)); }
      d.thin.push(circ(334, 170, 8));
    } else {
      d.main.push(bar([206, 118], [316, 152], 13, 11));
      d.main.push('M318,124 L346,122 Q366,158 354,192 L306,194 L304,186 Q336,178 318,124 Z');
      d.thin.push('M322,132 Q338,170 312,186');
      d.thin.push(line(212, 140, 298, 128));
    }
    ground(d);
  }
  function grader(d, o) {
    wheel(d, 74, 176, 20); wheel(d, 122, 176, 20); wheel(d, 346, 176, 20);
    d.main.push(poly([[44, 160], [44, 118], [150, 118], [156, 160]]));             // моторний відсік
    d.main.push(poly([[150, 132], [150, 66], [196, 66], [204, 132]]));             // кабіна
    d.thin.push(poly([[157, 73], [190, 73], [197, 126], [157, 126]]));
    d.main.push(bar([196, 120], [346, 150], 14, 10));                              // хребтова рама
    d.thin.push(circ(258, 160, 18), line(232, 136, 258, 160), line(286, 142, 258, 160));
    d.main.push('M224,194 Q258,176 292,194 L292,198 Q258,182 224,198 Z');           // відвал
    ground(d);
    if (o.blade) dims(d, { kind: 'note', at: [258, 196], to: [300, 222], label: `Відвал ${o.blade}` });
  }
  function roller(d) {
    wheel(d, 110, 168, 28);
    d.main.push(circ(300, 162, 34)); d.thin.push(circ(300, 162, 26)); d.centre.push(line(260, 162, 340, 162), line(300, 122, 300, 202));
    d.main.push(poly([[66, 166], [66, 120], [210, 120], [222, 150], [258, 150], [258, 132], [300, 128], [300, 140], [262, 166]]));
    d.main.push(poly([[150, 120], [150, 62], [204, 62], [210, 120]]));
    d.thin.push(poly([[157, 69], [198, 69], [203, 114], [157, 114]]));
    d.thin.push(line(258, 132, 300, 128));
    ground(d);
  }
  function paver(d) {
    track(d, 92, 166, 190, 30);
    d.main.push(poly([[80, 166], [80, 124], [300, 124], [300, 166]]));
    d.main.push(poly([[300, 124], [354, 116], [362, 170], [300, 166]]));            // бункер
    d.thin.push(line(304, 130, 354, 124));
    d.main.push(rr(30, 166, 64, 18, 2));                                            // вигладжувальна плита
    d.thin.push(line(30, 184, 14, 192));
    d.main.push(poly([[110, 124], [110, 76], [212, 76], [212, 124]])); d.thin.push(line(104, 76, 218, 76), line(118, 82, 118, 124), line(204, 82, 204, 124));
    ground(d);
  }
  function crusher(d) {
    track(d, 112, 166, 178, 30);
    d.main.push(rr(86, 122, 220, 44, 3));
    d.main.push(poly([[214, 122], [194, 64], [344, 64], [306, 122]]));               // бункер
    d.thin.push(line(206, 98, 320, 98));
    d.main.push(poly([[160, 122], [168, 84], [196, 84], [196, 122]]));             // щокова камера
    d.main.push(bar([90, 150], [18, 92], 10, 8));                                  // стрічка продукту
    for (let i = 1; i < 6; i++) d.thin.push(circ(90 - i * 12, 150 - i * 9.7, 2.5));
    d.thin.push(rr(100, 130, 50, 26, 2));
    ground(d);
  }
  function truck(d, o) {                                                           // тягач, трал, самоскид, напівпричіп
    const kind = o.kind;
    d.main.push(poly([[312, 160], [312, 92], [352, 92], [372, 124], [372, 160]]));
    d.thin.push(poly([[318, 98], [348, 98], [362, 124], [318, 124]]));
    wheel(d, 350, 178, 16);
    if (kind === 'dump') {
      d.main.push(rr(40, 150, 280, 14, 3));
      [80, 116, 280].forEach(x => wheel(d, x, 178, 16));
      d.main.push(poly([[44, 150], [32, 92], [298, 92], [300, 150]]));
      d.thin.push(line(46, 104, 296, 104), line(60, 150, 50, 92));
    } else {
      d.main.push(rr(236, 150, 136, 14, 3));
      [256, 288].forEach(x => wheel(d, x, 178, 16));
      d.main.push(rr(236, 140, 44, 10, 2));                                         // сідло
      if (kind === 'semi') {
        d.main.push(rr(26, 132, 236, 14, 2));
        d.thin.push(line(26, 146, 26, 160), line(248, 146, 258, 150));
        [54, 86, 118].forEach(x => wheel(d, x, 178, 14));
        if (o.length) dims(d, { kind: 'h', x1: 26, x2: 262, y: 116, label: `Довжина ${o.length}` });
      } else {
        d.main.push(poly([[226, 168], [238, 132], [282, 132], [282, 144], [246, 144], [236, 178], [30, 178], [30, 168]]));   // гусак і низька платформа
        d.thin.push(line(30, 172, 228, 172));
        [52, 82, 112].forEach(x => wheel(d, x, 184, 12));
        if (o.length) dims(d, { kind: 'h', x1: 30, x2: 230, y: 150, label: `Платформа ${o.length}` });
      }
    }
    ground(d);
  }

  /* ── вибір класу за каталогом ── */
  const spec = (u, re) => { const s = (u.specs || []).find(x => re.test(x.k)); return s ? s.v : null; };
  function kind(u) {
    const n = u.name || '';
    switch (u.cat) {
      case 'exc': return 'excavator';
      case 'amph': return /амфіб/i.test(n) ? 'amphibian' : 'longreach';
      case 'bull': return 'dozer';
      case 'crane': return 'crane';
      case 'load': return 'loader';
      case 'road': return /грейдер/i.test(n) ? 'grader' : /коток|котки/i.test(n) ? 'roller' : /асфальт/i.test(n) ? 'paver' : 'loader';
      case 'crush': return /мульчер/i.test(n) ? 'mulcher' : 'crusher';
      case 'trans': return /самоскид/i.test(n) ? 'dump' : /напівпричеп/i.test(n) ? 'semi' : 'lowboy';
      default: return null;
    }
  }
  const CLASS = { excavator: 'Гусеничний екскаватор', longreach: 'Екскаватор із довгою стрілою', amphibian: 'Екскаватор-амфібія',
    dozer: 'Бульдозер', crane: 'Автокран', loader: 'Колісний навантажувач', mulcher: 'Мульчер', grader: 'Автогрейдер',
    roller: 'Каток', paver: 'Асфальтоукладач', crusher: 'Мобільна дробарка', lowboy: 'Тягач із тралом', semi: 'Тягач із напівпричепом', dump: 'Самоскид' };

  /* ── складання SVG ── */
  function el(name, attrs, parent) {
    const n = document.createElementNS(NS, name);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  const meters = v => { const m = String(v || '').match(/^(\d+(?:[.,]\d+)?)\s*м$/); return m ? Number(m[1].replace(',', '.')) : null; };

  function geometry(u, opt) {
    const k = kind(u); if (!k) return null;
    const d = { main: [], thin: [], hidden: [], centre: [], ground: [], water: [], dims: [] };
    const o = { boom: spec(u, /стріл/i), length: spec(u, /^Довжина$/i), blade: spec(u, /відвал/i), angle: opt && opt.angle };
    let extra = null;
    if (k === 'excavator') extra = excavator(d, o);
    else if (k === 'longreach') extra = excavator(d, Object.assign(o, { long: true }));
    else if (k === 'amphibian') extra = amphibian(d, o);
    else if (k === 'dozer') dozer(d);
    else if (k === 'crane') extra = crane(d, o);
    else if (k === 'loader') loader(d, o);
    else if (k === 'mulcher') loader(d, { drum: true });
    else if (k === 'grader') grader(d, o);
    else if (k === 'roller') roller(d);
    else if (k === 'paver') paver(d);
    else if (k === 'crusher') crusher(d);
    else truck(d, { kind: k, length: o.length });
    return { kind: k, cls: CLASS[k], d, extra, o };
  }

  function dimension(g, dm) {
    const grp = el('g', { class: 'bp-dim' }, g);
    if (dm.kind === 'h') {
      el('path', { d: `${line(dm.x1, dm.y, dm.x2, dm.y)} ${line(dm.x1, dm.y - 6, dm.x1, dm.y + 14)} ${line(dm.x2, dm.y - 6, dm.x2, dm.y + 14)}`, pathLength: 1 }, grp);
      el('path', { class: 'bp-arrow', d: `${poly([[dm.x1, dm.y], [dm.x1 + 8, dm.y - 3], [dm.x1 + 8, dm.y + 3]])} ${poly([[dm.x2, dm.y], [dm.x2 - 8, dm.y - 3], [dm.x2 - 8, dm.y + 3]])}` }, grp);
      el('text', { x: (dm.x1 + dm.x2) / 2, y: dm.y - 5, 'text-anchor': 'middle' }, grp).textContent = dm.label;
    } else if (dm.kind === 'along') {
      const [ax, ay] = dm.a, [bx, by] = dm.b, L = Math.hypot(bx - ax, by - ay), nx = -(by - ay) / L * dm.off, ny = (bx - ax) / L * dm.off;
      const A = [ax + nx, ay + ny], B = [bx + nx, by + ny];
      el('path', { d: `${line(A[0], A[1], B[0], B[1])} ${line(ax, ay, A[0] + nx * .3, A[1] + ny * .3)} ${line(bx, by, B[0] + nx * .3, B[1] + ny * .3)}`, pathLength: 1 }, grp);
      const ang = Math.atan2(by - ay, bx - ax) * 180 / Math.PI, mx = (A[0] + B[0]) / 2 + nx * .5, my = (A[1] + B[1]) / 2 + ny * .5;
      el('text', { x: f(mx), y: f(my), 'text-anchor': 'middle', transform: `rotate(${f(ang)} ${f(mx)} ${f(my)})` }, grp).textContent = dm.label;
    } else if (dm.kind === 'note') {
      el('path', { d: `${line(dm.at[0], dm.at[1], dm.to[0], dm.to[1])} ${line(dm.to[0], dm.to[1], dm.to[0] + 70, dm.to[1])}`, pathLength: 1 }, grp);
      el('text', { x: dm.to[0] + 4, y: dm.to[1] - 4 }, grp).textContent = dm.label;
    }
  }

  /* Стріла крана: окремий шар, кут — параметр. Повертає функцію перерахунку для інтерактиву. */
  function craneBoom(g, P, len, boomM) {
    const grp = el('g', { class: 'bp-boom' }, g);
    const secs = [[0, len * .46, 18], [len * .42, len * .76, 14], [len * .72, len, 10]];
    const paths = secs.map((s, i) => el('path', { class: i ? 'bp-thin' : 'bp-main', pathLength: 1 }, grp));
    const outline = el('path', { class: 'bp-main', pathLength: 1 }, grp);
    const rope = el('path', { class: 'bp-thin bp-rope' }, grp);
    const hook = el('path', { class: 'bp-main' }, grp);
    const cyl = el('path', { class: 'bp-thin', pathLength: 1 }, grp);
    const r = el('g', { class: 'bp-dim bp-live' }, g), rl = el('path', {}, r), rt = el('text', { 'text-anchor': 'middle' }, r);
    const hgt = el('g', { class: 'bp-dim bp-live' }, g), hl = el('path', {}, hgt), ht = el('text', { 'text-anchor': 'end' }, hgt);
    function set(angle) {
      const a = angle * Math.PI / 180, ux = Math.cos(a), uy = -Math.sin(a), T = [P[0] + ux * len, P[1] + uy * len];
      secs.forEach((s, i) => paths[i].setAttribute('d', bar([P[0] + ux * s[0], P[1] + uy * s[0]], [P[0] + ux * s[1], P[1] + uy * s[1]], s[2], s[2] - 2)));
      outline.setAttribute('d', bar(P, T, 18, 8));
      const hy = Math.min(G - 18, T[1] + 46);
      rope.setAttribute('d', line(T[0], T[1], T[0], hy));
      hook.setAttribute('d', `M${f(T[0] - 5)},${f(hy)} H${f(T[0] + 5)} V${f(hy + 6)} Q${f(T[0] + 5)},${f(hy + 14)} ${f(T[0])},${f(hy + 14)} Q${f(T[0] - 6)},${f(hy + 14)} ${f(T[0] - 6)},${f(hy + 8)}`);
      cyl.setAttribute('d', line(P[0] + 26, P[1] + 4, P[0] + ux * len * .3, P[1] + uy * len * .3 + 4));
      const yR = G + 30;
      rl.setAttribute('d', `${line(P[0], yR, T[0], yR)} ${line(P[0], G + 4, P[0], yR + 4)} ${line(T[0], hy + 16, T[0], yR + 4)}`);
      rt.setAttribute('x', f((P[0] + T[0]) / 2)); rt.setAttribute('y', yR - 4);
      hl.setAttribute('d', `${line(P[0] - 22, P[1], P[0] - 22, T[1])} ${line(P[0] - 26, P[1], P[0] - 6, P[1])} ${line(P[0] - 26, T[1], T[0] - 10, T[1])}`);
      ht.setAttribute('x', f(P[0] - 26)); ht.setAttribute('y', f((P[1] + T[1]) / 2));
      const m = reach(boomM, angle);
      rt.textContent = m ? `виліт ${m.r.toLocaleString('uk-UA')} м` : 'виліт';
      ht.textContent = m ? `${m.h.toLocaleString('uk-UA')} м` : '';
      return m;
    }
    return set;
  }

  /* Геометрія вильоту від осі повороту: r = L·cos θ, h = L·sin θ. Без висоти опори й прогину стріли. */
  function reach(boomM, angle) {
    if (!(boomM > 0) || !(angle >= 0 && angle <= 90)) return null;
    const a = angle * Math.PI / 180, r1 = x => Math.round(x * 10) / 10;
    return { r: r1(boomM * Math.cos(a)), h: r1(boomM * Math.sin(a)) };
  }

  function draw(u, opt) {
    const geo = geometry(u, opt); if (!geo) return null;
    const svg = el('svg', { viewBox: geo.kind === 'crane' ? `0 -88 ${W} ${H + 124}` : `0 0 ${W} ${H}`, class: `bp bp--${geo.kind}`, role: 'img', 'aria-label': `Креслення: ${geo.cls}` });
    /* суцільні лінії «прокреслюються» (pathLength = 1); штрихові й осьові — лише проявляються, бо pathLength масштабує їхній штрих */
    const layer = (cls, list, ink) => { const g = el('g', { class: cls }, svg); list.forEach((dd, i) => el('path', ink ? { d: dd, pathLength: 1, style: `--i:${i}` } : { d: dd }, g)); return g; };
    layer('bp-ground', geo.d.ground, false); layer('bp-water', geo.d.water, false);
    layer('bp-centre', geo.d.centre, false); layer('bp-hidden', geo.d.hidden, false);
    layer('bp-thin', geo.d.thin, true); layer('bp-main', geo.d.main, true);
    const dg = el('g', { class: 'bp-dims' }, svg);
    geo.d.dims.forEach(dm => dimension(dg, dm));
    let setAngle = null;
    if (geo.kind === 'crane') setAngle = craneBoom(svg, geo.extra.pivot, geo.extra.boomLen, meters(geo.o.boom));
    if (setAngle) setAngle(geo.extra.angle);
    return { svg, kind: geo.kind, cls: geo.cls, setAngle, boom: meters(geo.o.boom) };
  }

  return Object.freeze({ draw, kind, reach, meters, CLASS });
});
