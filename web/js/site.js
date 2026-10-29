/* ПБТ · ПолтаваБудТехніка — сцени, стани, інтерактив. Без залежностей; рух — функція прогресу скролу й видимості.
   Контракт валідації заявки спільний із сервером: tests/contracts/lead_vectors.json (window.PBTv — чиста функція для тестів). */
(function () {
  'use strict';
  const D = window.PBT || {};
  const doc = document.documentElement;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const quality = () => doc.dataset.quality || 'full';
  const motion = () => quality() !== 'static' && !reduced;
  const finePointer = matchMedia('(pointer:fine)').matches;
  const fmt = n => Math.round(n).toLocaleString('uk-UA');
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const seg = (p, a, b) => clamp((p - a) / (b - a), 0, 1);
  const ease = t => (t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
  const mobileLayout = () => innerWidth < 1024;
  const phoneHuman = p => (p || '').replace(/^\+38(0\d{2})(\d{3})(\d{2})(\d{2})$/, '$1 $2 $3 $4');
  const V_BASE = D.video || 'media/video/';
  const vsrc = (name, ext) => (D.videoData && D.videoData[name + '.' + ext]) || (V_BASE + name + '.' + ext);

  /* ───── профіль за можливостями ───── */
  function profile() {
    const m = q => matchMedia(q).matches, w = innerWidth, h = innerHeight;
    const coarse = m('(pointer:coarse)') && !m('(any-pointer:fine)');
    doc.dataset.profile = (!coarse && w >= 1024 && w / h >= 1.05) ? 'wide-fine' : ((coarse && (w < 760 || h > w)) || w < 600) ? 'compact-touch' : 'medium-hybrid';
  }

  /* ───── відео: джерела підставляються лише з JS, грають лише у кадрі ───── */
  function heroHD() {
    const c = navigator.connection || {};
    if (D.videoData || c.saveData || /(^|-)2g$|^3g$/.test(c.effectiveType || '')) return false;   // однофайлова збірка несе лише 720
    return innerWidth * (devicePixelRatio || 1) >= 1600;
  }
  function attachVideo(video, name, { tall } = {}) {
    if (!video || video.dataset.ready) return;
    video.dataset.ready = '1';
    video.muted = true; video.loop = true; video.playsInline = true; video.setAttribute('muted', ''); video.preload = 'none';
    let n = tall && mobileLayout() ? name.replace('-wide', '-tall') : name;
    if (n === 'hero-wide' && !heroHD()) n = 'hero-wide-720';          // 1920 — лише коли екран його покаже й мережа витягне
    if (D.videoData || D.mp4Only || !document.createElement('video').canPlayType('video/webm; codecs="vp9"')) {
      video.src = vsrc(n, 'mp4');
    } else {
      const s1 = document.createElement('source'); s1.src = vsrc(n, 'webm'); s1.type = 'video/webm';
      const s2 = document.createElement('source'); s2.src = vsrc(n, 'mp4'); s2.type = 'video/mp4';
      video.append(s1, s2);
    }
  }
  const playing = new Set();
  const vio = 'IntersectionObserver' in window ? new IntersectionObserver(es => es.forEach(e => {
    const v = e.target.querySelector('video'); if (!v) return;
    if (e.isIntersecting && motion()) {
      if (!v.dataset.ready) attachVideo(v, v.dataset.video);
      v.preload = 'auto';
      const p = v.play(); if (p && p.catch) p.catch(() => {});
      e.target.classList.add('is-playing'); playing.add(v);
    } else { v.pause(); e.target.classList.remove('is-playing'); playing.delete(v); }
  }), { threshold: .45 }) : null;
  const watchVideo = el => { if (vio) vio.observe(el); };

  /* ───── НАВІГАЦІЯ, МЕНЮ ───── */
  const nav = $('#nav'), burger = $('.burger'), menu = $('#menu');
  let lastY = scrollY, navHidden = false;
  function openMenu(on) {
    menu.hidden = !on; burger.setAttribute('aria-expanded', String(on)); document.body.style.overflow = on ? 'hidden' : '';
    if (on) nav.classList.remove('is-hidden');
  }
  burger.addEventListener('click', () => openMenu(menu.hidden));
  $$('a', menu).forEach(a => a.addEventListener('click', () => openMenu(false)));
  addEventListener('keydown', e => { if (e.key === 'Escape' && !menu.hidden) openMenu(false); });

  /* ───── ГЕРОЙ ───── */
  const sHero = $('.s-hero'), hero = $('#hero'), hVideo = $('#heroVideo'), hCenter = $('#heroCenter'), water = $('#heroWater'), spark = $('#spark');
  $$('#heroTitle .line').forEach(line => {       /* слова — окремі спани для появи */
    line.innerHTML = line.textContent.trim().split(/\s+/).map((w, i) => `<span class="w" style="transition-delay:${.45 + i * .07}s">${esc(w)}</span>`).join(' ');
  });
  let heroTop = 0, heroTotal = 1, heroP = 0;
  function heroRender(y) {
    const p = clamp((y - heroTop) / heroTotal, 0, 1);
    if (motion()) {
      if (hVideo) hVideo.style.transform = `scale(${(1 + .14 * p).toFixed(4)}) translate3d(0,${(p * 6).toFixed(2)}%,0)`;
      const cp = seg(p, .35, .8);
      hCenter.style.opacity = (1 - cp).toFixed(3);
      hCenter.style.transform = `translate3d(0,calc(-50% - ${(cp * 90).toFixed(1)}px),0) scale(${(1 - .06 * cp).toFixed(4)})`;
      water.style.setProperty('--wl', (seg(p, .45, .985) * 1.04).toFixed(4));
      if (p >= 1 && hVideo && !hVideo.paused) hVideo.pause();
      else if (p < 1 && hVideo && hVideo.paused && hVideo.dataset.ready && !document.hidden) { const pr = hVideo.play(); if (pr && pr.catch) pr.catch(() => {}); }
    }
    return p;
  }
  /* блиски на воді — canvas, лише повна якість і лише поки герой у кадрі */
  let ctx = null, cW = 0, cH = 0, cLast = 0, dots = [];
  function sparkSize() {
    if (!spark || getComputedStyle(spark).display === 'none') { ctx = null; dots = []; return; }
    const dpr = Math.min(devicePixelRatio || 1, 1.5);
    cW = spark.clientWidth; cH = spark.clientHeight;
    spark.width = Math.round(cW * dpr); spark.height = Math.round(cH * dpr);
    ctx = spark.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    dots = Array.from({ length: mobileLayout() ? 28 : 60 }, () => ({ x: Math.random() * cW, y: Math.random() * cH, r: .6 + Math.random() * 1.8, s: .15 + Math.random() * .45, ph: Math.random() * 6.28 }));
  }
  /* цикл іскор засинає, коли герой поза кадром або вкладка прихована (раніше rAF крутився вічно: Lighthouse devtools 09.10
     — сторінка не ставала «тихою»); прокидає його sparkWake() зі скролу й visibilitychange */
  let sparkOn = false;
  const sparkWake = () => { if (!sparkOn && ctx && motion() && quality() === 'full' && heroP < 1 && !document.hidden) { sparkOn = true; requestAnimationFrame(sparkLoop); } };
  function sparkLoop(t) {
    if (!ctx || quality() !== 'full' || reduced || heroP >= 1 || document.hidden) { sparkOn = false; return; }
    requestAnimationFrame(sparkLoop);
    if (t - cLast < 33) return;
    cLast = t;
    ctx.clearRect(0, 0, cW, cH);
    const s = t / 1000;
    for (const d of dots) {
      d.y -= d.s; d.x += Math.sin(s * .6 + d.ph) * .18;
      if (d.y < -4) { d.y = cH + 4; d.x = Math.random() * cW; }
      const a = .25 + .55 * (.5 + .5 * Math.sin(s * 1.7 + d.ph));
      ctx.beginPath(); ctx.arc(d.x, d.y, d.r, 0, 6.283);
      ctx.fillStyle = `rgba(253,220,80,${a.toFixed(3)})`; ctx.fill();
    }
  }

  /* ───── ГЛИБИНОМІР, АКТИВНА СЕКЦІЯ, ПРОГРЕС ───── */
  const gauge = $('#gauge'), gFloat = $('.gauge__float'), gOut = $('.gauge__m'), gStops = $$('.gauge__stops a'), navLinks = $$('.nav__links a');
  const sections = $$('main section[id]');
  let docMax = 1, secTops = [];
  function measure() {
    heroTop = sHero.offsetTop; heroTotal = Math.max(1, sHero.offsetHeight - innerHeight);
    docMax = Math.max(1, doc.scrollHeight - innerHeight);
    secTops = sections.map(s => ({ id: s.id, top: s.offsetTop }));
    $$('.gauge__stops li').forEach((li, i) => { const s = secTops[i]; if (s) li.style.top = (clamp(s.top / docMax, 0, 1) * 100).toFixed(2) + '%'; });
    sparkSize();
  }
  function gaugeRender(y) {
    const p = clamp(y / docMax, 0, 1);
    nav.style.setProperty('--sp', p.toFixed(4));
    gFloat.style.transform = `translate3d(0,${(p * gauge.clientHeight).toFixed(1)}px,0)`;
    gOut.value = (p === 0 ? '0,0' : '−' + (p * 6).toFixed(1).replace('.', ',')) + ' м';
    gauge.classList.toggle('is-on', y > 80);
    let active = secTops[0] ? secTops[0].id : '';
    for (const s of secTops) if (s.top <= y + innerHeight * .42) active = s.id;
    gStops.forEach(a => a.classList.toggle('is-on', a.getAttribute('href').slice(1) === active));
    navLinks.forEach(a => a.classList.toggle('is-on', a.getAttribute('href') === '#' + active));
  }

  /* ───── РЕНДЕР: один контур на подію скролу ───── */
  let ticking = false;
  function render() {
    ticking = false;
    const y = scrollY;
    heroP = heroRender(y); sparkWake();
    gaugeRender(y);
    nav.classList.toggle('is-solid', y > 40);
    const dy = y - lastY;
    if (menu.hidden) {
      if (dy > 2 && y > 160 && !navHidden) { navHidden = true; nav.classList.add('is-hidden'); }
      else if ((dy < -2 || y < 160) && navHidden) { navHidden = false; nav.classList.remove('is-hidden'); }
    }
    lastY = y;
  }
  const onScroll = () => { if (!ticking) { ticking = true; requestAnimationFrame(render); } };
  addEventListener('scroll', onScroll, { passive: true });
  let rT;
  addEventListener('resize', () => { clearTimeout(rT); rT = setTimeout(() => { profile(); measure(); render(); }, 120); });

  /* ───── ПОЯВА СЕКЦІЙ, ЛІЧИЛЬНИКИ, МАРШРУТИ ───── */
  const rio = 'IntersectionObserver' in window ? new IntersectionObserver(es => es.forEach(e => {
    if (!e.isIntersecting) return;
    e.target.classList.add('is-in'); rio.unobserve(e.target);
    $$('[data-count]', e.target).forEach(countUp);
    if (e.target.dataset.count !== undefined) countUp(e.target);
  }), { threshold: 0, rootMargin: '0px 0px 20% 0px' }) : null;   // заздалегідь: виміряно «примару» 0.8 с на кожен блок (tests/test_site.py)
  function reveal(root) {
    $$('.rv', root || document).forEach(el => { if (!rio || !motion()) el.classList.add('is-in'); else rio.observe(el); });
    $$('[data-count]', root || document).forEach(el => { if (el.closest('.rv')) return; if (!rio || !motion()) countUp(el); else rio.observe(el); });   /* лічильники поза .rv (герой) */
  }
  function countUp(el) {
    if (el.dataset.done) return; el.dataset.done = '1';
    const to = parseFloat(el.dataset.count), suf = el.dataset.suffix || '', dur = 1400, t0 = performance.now();
    if (!motion()) { el.textContent = fmt(to) + suf; return; }
    const step = t => { const k = ease(clamp((t - t0) / dur, 0, 1)); el.textContent = fmt(to * k) + suf; if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }

  /* ───── ПАРК ───── */
  const catName = id => (D.cats.find(c => c.id === id) || {}).name || '';
  function renderPark() {
    const grid = $('#park'), chips = $('#chips');
    const counts = {};
    D.fleet.forEach(u => counts[u.cat] = (counts[u.cat] || 0) + 1);
    chips.innerHTML = [`<button class="chip" type="button" data-cat="all" aria-pressed="true">Уся техніка <span class="num">${D.fleet.length}</span></button>`]
      .concat(D.cats.map(c => `<button class="chip" type="button" data-cat="${c.id}" aria-pressed="false">${esc(c.name)} <span class="num">${counts[c.id] || 0}</span></button>`)).join('');
    grid.innerHTML = D.fleet.map((u, i) => `
      <article class="unit rv rv--scale" style="--d:${(i % 8) * 60}ms" data-cat="${u.cat}" data-id="${u.id}">
        <figure><img src="${u.img}" alt="${esc(u.name)}" width="800" height="600" loading="lazy" decoding="async"><span class="unit__cat">${esc(catName(u.cat))}</span></figure>
        <div class="unit__body"><h3>${esc(u.name)}</h3>
          <dl class="unit__specs">${u.specs.map(s => `<div><dt>${esc(s.k)}</dt><dd>${esc(s.v)}</dd></div>`).join('')}</dl></div>
        <div class="unit__foot"><p class="unit__price${u.price ? '' : ' is-neg'}">${u.price ? `${fmt(u.price)} <small>грн/${esc(u.unit)}</small>` : 'договірна'}</p>
          <button class="btn btn--sm" type="button" data-req="rent" data-subject="${esc(u.name)}">У заявку</button></div>
      </article>`).join('');
    const reveal1 = b => { if (chips.scrollWidth > chips.clientWidth + 1) b.scrollIntoView({ inline: 'center', block: 'nearest', behavior: motion() ? 'smooth' : 'auto' }); };
    chips.addEventListener('focusin', e => { const b = e.target.closest('.chip'); if (b) reveal1(b); });   // Tab не лишає фокус за краєм (аудит a5951a5: 107 px поза контейнером на 390)
    chips.addEventListener('click', e => {
      const b = e.target.closest('.chip'); if (!b) return;
      reveal1(b);
      $$('.chip', chips).forEach(c => c.setAttribute('aria-pressed', String(c === b)));
      const cat = b.dataset.cat;
      $$('.unit', grid).forEach((u, i) => { u.hidden = !(cat === 'all' || u.dataset.cat === cat); if (!u.hidden) { u.classList.remove('is-in'); u.style.setProperty('--d', `${(i % 8) * 50}ms`); requestAnimationFrame(() => requestAnimationFrame(() => u.classList.add('is-in'))); } });
      measure();
    });
    if (finePointer && motion()) grid.addEventListener('pointermove', e => {         /* нахил картки за вказівником */
      const u = e.target.closest('.unit'); if (!u) return;
      const r = u.getBoundingClientRect(), x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
      u.style.setProperty('--ry', `${(x * 7).toFixed(2)}deg`); u.style.setProperty('--rx', `${(-y * 7).toFixed(2)}deg`);
    });
    grid.addEventListener('pointerleave', e => { $$('.unit', grid).forEach(u => { u.style.removeProperty('--rx'); u.style.removeProperty('--ry'); }); }, true);
    grid.addEventListener('pointerout', e => { const u = e.target.closest('.unit'); if (u && !u.contains(e.relatedTarget)) { u.style.removeProperty('--rx'); u.style.removeProperty('--ry'); } });
  }

  /* ───── РОБОТИ: відео на картках ───── */
  function renderJobs() {
    $$('#jobs .job').forEach((job, i) => {
      job.classList.add('rv'); job.style.setProperty('--d', `${i * 90}ms`);
      const v = $('video', job); if (v) watchVideo(job);
    });
  }

  /* ───── КАЛЬКУЛЯТОР ЗМІНИ ───── */
  const weightOf = u => { const s = (u.specs.find(x => /Вага|Вантажопідйомність/.test(x.k)) || {}).v || ''; const m = s.match(/(\d+(?:[.,]\d+)?)\s*т/); return m ? parseFloat(m[1].replace(',', '.')) : null; };
  const trailerFor = u => { const w = weightOf(u); return D.trailers.find(t => (w == null ? 22 : w) <= t.maxT) || D.trailers[D.trailers.length - 1]; };
  let totalShown = 0, totalAnim = 0;
  function tweenTotal(el, to) {
    const from = totalShown, t0 = performance.now(), id = ++totalAnim;
    if (!motion()) { totalShown = to; el.innerHTML = `${fmt(to)} <small>грн</small>`; return; }
    const step = t => { if (id !== totalAnim) return; const k = ease(clamp((t - t0) / 520, 0, 1)); totalShown = from + (to - from) * k; el.innerHTML = `${fmt(totalShown)} <small>грн</small>`; if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }
  function renderCalc() {
    const sel = $('#cMachine'), hr = $('#cHours'), hrN = $('#cHoursN'), km = $('#cKm'), kmN = $('#cKmN');
    const priced = D.fleet.filter(u => u.price && u.unit === 'год');
    sel.innerHTML = priced.map(u => `<option value="${u.id}">${esc(u.name)} — ${fmt(u.price)} грн/год</option>`).join('');
    const fill = r => r.style.setProperty('--p', `${((r.value - r.min) / (r.max - r.min) * 100).toFixed(1)}%`);
    const sync = (a, b) => a.addEventListener('input', () => { b.value = a.value; fill(hr); fill(km); calc(); });
    sync(hr, hrN); sync(hrN, hr); sync(km, kmN); sync(kmN, km);
    sel.addEventListener('change', calc);
    function calc() {
      const u = priced.find(x => x.id === sel.value) || priced[0];
      const hours = clamp(parseInt(hrN.value, 10) || 0, 1, 5000), kmv = clamp(parseInt(kmN.value, 10) || 0, 0, 3000);
      const crane = u.cat === 'crane', tr = trailerFor(u);
      const rent = hours * u.price, deliv = crane ? 0 : kmv * tr.rate, total = rent + deliv;
      tweenTotal($('#cTotal'), total);
      $('#cLines').innerHTML = `<div><span>Оренда: ${hours} год × ${fmt(u.price)} грн</span><b>${fmt(rent)} грн</b></div>` +
        (crane ? `<div><span>Подача автокрана</span><b>уточнюється</b></div>` : `<div><span>Подача тралом ${esc(tr.name.replace(/^Трал\s*/, ''))}: ${kmv} км × ${tr.rate} грн</span><b>${fmt(deliv)} грн</b></div>`) +
        `<div><span>Разом, орієнтовно</span><b>${fmt(total)} грн</b></div>`;
      km.disabled = kmN.disabled = crane;
      $('#cOrder').dataset.subject = `${u.name} — ${hours} год${crane ? '' : `, подача ${kmv} км`}`;
      $('#cOut').dataset.total = String(total);
    }
    fill(hr); fill(km); calc();
    window.PBTcalc = (id, hours, kmv) => { const u = priced.find(x => x.id === id); if (!u) return null; const crane = u.cat === 'crane'; return hours * u.price + (crane ? 0 : kmv * trailerFor(u).rate); };
  }

  /* ───── МАТЕРІАЛИ, ДОКАЗ, ГЕОГРАФІЯ ───── */
  const x2 = src => /^media\/.+\.webp$/.test(src) ? ` srcset="${src} 1x, ${src.replace(/\.webp$/, '@2x.webp')} 2x"` : '';   // data:URI однофайлової збірки — без srcset
  function renderMats() {
    $('#mats').innerHTML = `<div class="tiles">${D.materials.map((m, i) => `
      <article class="tile rv" style="--d:${(i % 4) * 80}ms"><figure><img src="${m.img}"${x2(m.img)} alt="${esc(m.name)}" width="639" height="396" loading="lazy" decoding="async"><span class="tile__group">${esc(m.group)}</span></figure>
        <div class="tile__body"><h4>${esc(m.name)}</h4><p class="tile__price">${fmt(m.price)} <small>грн/${esc(m.unit)}</small></p><p class="tile__doc">${esc(m.doc)}</p></div></article>`).join('')}</div>`;
  }
  function renderProof() {
    $('#reel').innerHTML = D.proof.map((p, i) => `<a class="rv" style="--d:${(i % 3) * 90}ms" href="${p.url}" target="_blank" rel="noopener" aria-label="${esc(p.t)}: ${esc(p.s)} — відкрити відео">
      <figure><img src="${p.poster}" alt="" width="640" height="360" loading="lazy" decoding="async"><video data-video="${p.video}" poster="${p.poster}" aria-hidden="true" tabindex="-1"></video>
      <i aria-hidden="true"></i><figcaption><b>${esc(p.t)}</b><span>${esc(p.s)}</span></figcaption></figure></a>`).join('');
    $$('#reel a').forEach(watchVideo);
    const logos = D.partners.map((p, i) => `<li><img src="${p}" alt="Логотип партнера ${i + 1}" width="196" height="196" loading="lazy" decoding="async"></li>`).join('');
    $('#partners').innerHTML = logos + logos;      /* подвоєння — для нескінченної стрічки */
  }
  function renderGeo() {
    const home = 'Полтавська', svg = $('#geoMap svg');
    const list = $('#geoList');
    list.innerHTML = D.regions.map((r, i) => `<li class="rv ${r === home ? 'home' : ''}" style="--d:${i * 50}ms"><b>${esc(r)} область</b><span>${r === home ? 'база · Полтава' : 'виїзд'}</span></li>`).join('');
    if (!svg) return;
    $$('.obl', svg).forEach(p => { if (p.dataset.ua === home) p.classList.add('home'); });
    /* маршрути з Полтави до кожної області — криві по центрах контурів, малюються при появі секції */
    const center = p => { const b = p.getBBox(); return [b.x + b.width / 2, b.y + b.height / 2]; };
    const homeP = $$('.obl', svg).find(p => p.dataset.ua === home); if (!homeP) return;
    /* спершу всі читання геометрії, потім записи: getBBox/getTotalLength між appendChild змушували перераховувати розкладку
       на кожній ітерації (Lighthouse 09.10: renderGeo 344 мс при CPU ×4). Довжину кривої Безьє — аналітично, без DOM. */
    const build = () => {
    const [hx, hy] = center(homeP);
    const served = $$('.obl.served', svg).filter(p => p.dataset.ua && p.dataset.ua !== home && p.dataset.name !== 'Kyiv');
    const ends = served.map(center);
    const qlen = (x0, y0, x1, y1, x2, y2) => { let L = 0, px = x0, py = y0; for (let k = 1; k <= 24; k++) { const t = k / 24, u = 1 - t, x = u * u * x0 + 2 * u * t * x1 + t * t * x2, y = u * u * y0 + 2 * u * t * y1 + t * t * y2; L += Math.hypot(x - px, y - py); px = x; py = y; } return L; };
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g'); g.setAttribute('class', 'routes');
    ends.forEach(([x, y], i) => {
      const mx = (hx + x) / 2, my = (hy + y) / 2 - Math.abs(x - hx) * .18 - 14;
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', `M${hx.toFixed(1)},${hy.toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${x.toFixed(1)},${y.toFixed(1)}`);
      path.setAttribute('class', 'route');
      path.style.setProperty('--len', qlen(hx, hy, mx, my, x, y).toFixed(1)); path.style.setProperty('--d', `${.2 + i * .12}s`);
      g.appendChild(path);
    });
    const ring = document.createElementNS('http://www.w3.org/2000/svg', 'circle'); ring.setAttribute('class', 'beacon-ring'); ring.setAttribute('cx', hx); ring.setAttribute('cy', hy); ring.setAttribute('r', 9);
    const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle'); dot.setAttribute('class', 'beacon'); dot.setAttribute('cx', hx); dot.setAttribute('cy', hy); dot.setAttribute('r', 6);
    g.append(ring, dot); svg.appendChild(g);
    };
    build();   // на старті, не ліниво: getBBox посеред скролу давав ривок і «примар» (A/B 09.10, p95 951 → 387 мс)
    $('#geoMap').classList.add('rv');
    const hov = $('#geoHover');
    svg.addEventListener('pointerover', e => { const p = e.target.closest('.obl'); if (!p) return; hov.textContent = p.dataset.ua ? `${p.dataset.ua} область — ${p.dataset.ua === home ? 'база' : 'працюємо'}` : `${p.dataset.name} — за запитом`; });
    svg.addEventListener('pointerout', () => { hov.textContent = ''; });
  }

  /* ───── КОНФІГУРАЦІЯ БІЗНЕСУ: /api/config → канали, підвал (fallback — вбудовані дані) ───── */
  function applyBusiness(b) {
    const c = b.contacts || {};
    const tel = p => p ? `tel:${p}` : '#zapyt';
    $$('[data-phone]').forEach(a => { a.textContent = phoneHuman(c.phone) || 'Телефон уточнюється'; if (a.tagName === 'A') a.href = tel(c.phone); });
    $$('[data-phone2]').forEach(a => { a.textContent = phoneHuman(c.phone2) || ''; if (a.tagName === 'A') a.href = tel(c.phone2); });
    $$('[data-address]').forEach(e => e.textContent = b.address || 'Адреса уточнюється');
    $$('[data-legal]').forEach(e => e.textContent = b.legalName || 'ТОВ «ПолтаваБудТехніка»');
    $$('[data-edrpou]').forEach(e => e.textContent = b.edrpou ? `ЄДРПОУ ${b.edrpou}` : '');
    const h = b.hours || {};
    $$('[data-hours]').forEach(e => e.textContent = h['mo-fr'] ? `Пн–Пт ${h['mo-fr']} · Сб ${h.sa || '—'} · Нд ${h.su || '—'}` : 'Години роботи уточнюються');
    const ch = [];
    if (c.phone) ch.push({ k: 'Телефон', v: phoneHuman(c.phone), href: `tel:${c.phone}` });
    if (c.phone2) ch.push({ k: 'Телефон', v: phoneHuman(c.phone2), href: `tel:${c.phone2}` });
    if (c.viber) ch.push({ k: 'Viber', v: phoneHuman(c.viber), href: `viber://chat?number=${encodeURIComponent(c.viber)}` });
    if (c.telegram) ch.push({ k: 'Telegram', v: c.telegram, href: `https://t.me/${c.telegram.replace('@', '')}` });
    if (c.email) ch.push({ k: 'Email', v: c.email, href: `mailto:${c.email}` });
    $('#channels').innerHTML = ch.map(x => `<a href="${x.href}"><b>${esc(x.v)}</b><span>${x.k}</span></a>`).join('') || '<div><b>Канали зв’язку</b><span>уточнюються</span></div>';
    const soc = [['tiktok', 'TikTok'], ['instagram', 'Instagram'], ['facebook', 'Facebook'], ['youtube', 'YouTube']].filter(([k]) => c[k]);
    $$('[data-social]').forEach(ul => ul.innerHTML = soc.map(([k, n]) => `<li><a href="${c[k]}" target="_blank" rel="noopener">${n}</a></li>`).join(''));
  }
  function loadBusiness() {
    const fb = () => applyBusiness(D.business || {});
    if (window.PBT_BUNDLE || location.protocol === 'file:') return fb();
    fetch('/api/config', { cache: 'no-store' }).then(r => r.ok ? r.json() : Promise.reject()).then(j => applyBusiness(Object.keys(j).length ? j : D.business)).catch(fb);
  }

  /* ───── ВАЛІДАЦІЯ ЗАЯВКИ: той самий контракт, що й сервер ───── */
  const V = {
    contact(method, s) {
      s = (s || '').trim(); if (!s) return null;
      if (method === 'telegram' && s.startsWith('@')) return /^@[A-Za-z0-9_]{5,32}$/.test(s) ? s : null;
      let d = s.replace(/[\s()\-]/g, '');
      if (/^0\d{9}$/.test(d)) d = '+38' + d;
      if (/^380\d{9}$/.test(d)) d = '+' + d;
      if (/^\+3800\d{9}$/.test(d)) d = '+380' + d.slice(5);
      if (d.startsWith('+380') && !/^\+380\d{9}$/.test(d)) return null;
      return /^\+\d{10,15}$/.test(d) ? d : null;
    },
    int(v, lo, hi) { v = String(v == null ? '' : v).replace(/\s/g, ''); if (v === '') return ''; if (!/^\d+$/.test(v)) return null; const n = parseInt(v, 10); return (n >= lo && n <= hi) ? n : null; },
    date(v) {
      v = (v || '').trim(); if (!v) return '';
      const m = v.match(/^(\d{4})-(\d{2})-(\d{2})$/); if (!m) return null;
      const d = new Date(+m[1], +m[2] - 1, +m[3]);
      if (d.getFullYear() !== +m[1] || d.getMonth() !== +m[2] - 1 || d.getDate() !== +m[3]) return null;
      const today = new Date(); today.setHours(0, 0, 0, 0);
      return d >= today ? v : null;
    }
  };
  window.PBTv = (field, value, type, method) => {
    if (field === 'contact') return V.contact(method || 'phone', value) !== null;
    if (field === 'hours') return V.int(value, 1, 5000) !== null;
    if (field === 'km') return V.int(value, 0, 3000) !== null;
    if (field === 'date') return V.date(value) !== null;
    if (field === 'subject') return !(['rent', 'material', 'transport'].includes(type) && (value || '').trim().length < 2);
    return true;
  };

  /* ───── ЗАЯВКА ───── */
  const MSG = { subject: { rent: 'Вкажіть, яка техніка потрібна.', material: 'Вкажіть матеріал і фракцію.', transport: 'Вкажіть, що й куди перевезти.' },
    hours: 'Ціле число від 1 до 5000.', km: 'Ціле число від 0 до 3000.', date: 'Дата — не раніше за сьогоднішню.', contact: 'Перевірте контакт: 0XX XXX XX XX або @нік у Telegram.', comment: 'Опишіть завдання кількома словами.' };
  const form = $('#lead'), done = $('#done'), fallback = $('#fallback'), msg = $('#formMsg');
  let idemKey = null, idemHash = '';
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join(''));
  function setErr(name, text) { const f = form.querySelector(`[data-field="${name}"]`); if (!f) return; f.classList.toggle('is-err', !!text); const e = $('.err', f); if (e) e.textContent = text || ''; }
  function payload() {
    const fd = new FormData(form), g = k => (fd.get(k) || '').toString();
    return { type: g('type'), subject: g('subject').trim(), hours: g('hours').trim(), km: g('km').trim(), place: g('place').trim(), date: g('date').trim(),
      name: g('name').trim(), method: g('method'), contact: g('contact').trim(), comment: g('comment').trim(), website: g('website') };
  }
  function validate(p) {
    const err = {};
    if (['rent', 'material', 'transport'].includes(p.type) && p.subject.length < 2) err.subject = MSG.subject[p.type];
    if (p.type === 'other' && p.comment.length < 5 && p.subject.length < 2) err.comment = MSG.comment;
    if (V.int(p.hours, 1, 5000) === null) err.hours = MSG.hours;
    if (V.int(p.km, 0, 3000) === null) err.km = MSG.km;
    if (V.date(p.date) === null) err.date = MSG.date;
    if (!V.contact(p.method, p.contact)) err.contact = MSG.contact;
    return err;
  }
  const typeLabel = { rent: 'Оренда техніки', material: 'Сипучі матеріали', transport: 'Перевезення', other: 'Інше' };
  function humanText(p) {
    return [`Заявка · ${typeLabel[p.type] || p.type}`, p.subject && `Що: ${p.subject}`, p.hours && `Обсяг: ${p.hours}`, p.km && `Подача: ${p.km} км`, p.place && `Об’єкт: ${p.place}`,
      p.date && `Дата: ${p.date}`, p.name && `Ім’я: ${p.name}`, `Зв’язок: ${p.method} ${p.contact}`, p.comment && `Коментар: ${p.comment}`].filter(Boolean).join('\n');
  }
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const p = payload(); const err = validate(p);
    ['subject', 'hours', 'km', 'date', 'contact', 'comment'].forEach(k => setErr(k, err[k]));
    msg.classList.remove('is-on');
    if (Object.keys(err).length) { const first = form.querySelector('.is-err input, .is-err textarea'); if (first) first.focus(); return; }
    const h = JSON.stringify(p);
    if (h !== idemHash) { idemHash = h; idemKey = uuid(); }
    const btn = $('#send'); btn.disabled = true; btn.textContent = 'Надсилаю…';
    try {
      if (window.PBT_BUNDLE) throw new Error('bundle');
      const r = await fetch('/api/lead', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idemKey }, body: h });
      const j = await r.json().catch(() => ({}));
      if (r.status === 201 && j.ok) {
        form.hidden = true; done.classList.add('is-on'); $('#ref').textContent = j.ref; done.focus();
      } else if (r.status === 422 && j.fields) {
        Object.entries(j.fields).forEach(([k, v]) => setErr(k, v));
        msg.textContent = 'Перевірте позначені поля.'; msg.classList.add('is-on');
      } else if (r.status === 429) { msg.textContent = j.message || 'Забагато запитів. Спробуйте через 10 хвилин або зателефонуйте.'; msg.classList.add('is-on'); }
      else { msg.textContent = 'Сервер не прийняв заявку. Спробуйте ще раз або зателефонуйте — номери поруч.'; msg.classList.add('is-on'); }
    } catch (_) {
      form.hidden = true; fallback.classList.add('is-on'); $('#fbText').textContent = humanText(p);
    } finally { btn.disabled = false; btn.textContent = 'Надіслати заявку'; }
  });
  $('#fbCopy').addEventListener('click', async () => {
    const t = $('#fbText').textContent; const b = $('#fbCopy');
    try { await navigator.clipboard.writeText(t); b.textContent = 'Скопійовано'; } catch (_) { const r = document.createRange(); r.selectNodeContents($('#fbText')); const s = getSelection(); s.removeAllRanges(); s.addRange(r); b.textContent = 'Виділено — скопіюй'; }
    setTimeout(() => b.textContent = 'Скопіювати текст', 2500);
  });
  $('#again').addEventListener('click', () => { done.classList.remove('is-on'); form.hidden = false; form.reset(); idemHash = ''; $('#subject').focus(); });

  document.addEventListener('click', e => {
    const b = e.target.closest('[data-req]'); if (!b) return;
    const t = b.dataset.req, s = b.dataset.subject;
    const radio = form.querySelector(`input[name="type"][value="${t}"]`); if (radio) radio.checked = true;
    if (s) $('#subject').value = s;
    if (b.tagName === 'BUTTON') { e.preventDefault(); document.getElementById('zapyt').scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' }); }
    setTimeout(() => $('#subject').focus({ preventScroll: true }), 700);
  });

  /* ───── курсорне світло ───── */
  const glow = $('#glow');
  if (glow && finePointer && motion() && getComputedStyle(glow).display !== 'none') {
    let gx = 0, gy = 0, tx = 0, ty = 0, on = false;
    addEventListener('pointermove', e => { tx = e.clientX; ty = e.clientY; if (!on) { on = true; glow.classList.add('is-on'); } }, { passive: true });
    let run = false;                                   // цикл живе, лише поки світло доганяє курсор
    const loop = () => { gx += (tx - gx) * .12; gy += (ty - gy) * .12; glow.style.transform = `translate3d(${gx.toFixed(1)}px,${gy.toFixed(1)}px,0)`;
      if (Math.abs(tx - gx) + Math.abs(ty - gy) > .5) requestAnimationFrame(loop); else run = false; };
    addEventListener('pointermove', () => { if (!run) { run = true; requestAnimationFrame(loop); } }, { passive: true });
  }

  /* ───── МАСШТАБ: кіно-сцена з ілюстративної зйомки (window.PBT_CINE ← config/stock.json) ───── */
  const C_BASE = D.cine || 'media/cine/';
  const cposter = id => (D.cinePosters && D.cinePosters[id]) || C_BASE + id + '-w.webp';   /* бандл: постери як data:URI, відео немає */
  function renderCine() {
    const sec = $('#masshtab'), list = $('#cine'), rail = $('#cineRail'), C = window.PBT_CINE;
    if (!sec || !list || !C || !C.chapters) return;
    const chs = C.chapters, total = String(chs.length).padStart(2, '0');
    list.innerHTML = chs.map((c, i) => `<li class="cine__ch" id="cine-${esc(c.id)}" data-i="${i}">
      <figure><img src="${cposter(c.id)}" alt="${esc(c.word)}: ${esc(c.line)}" width="1920" height="1080" loading="lazy" decoding="async"></figure>
      <p class="cine__n num">${String(i + 1).padStart(2, '0')} / ${total}</p>
      <h3 class="cine__w">${esc(c.word)}</h3>
      <p class="cine__l">${esc(c.line)}</p>
    </li>`).join('');
    /* атрибуція CC BY / BY-SA — одним списком у підвалі, не поверх кадрів (ліцензія дозволяє «будь-яким розумним способом») */
    const cr = $('#cineCredits');
    if (cr) cr.innerHTML = `<details class="credits"><summary>Джерела ілюстративних кадрів «Масштабу»</summary><ul>${chs.map(c =>
      `<li><a href="${esc(c.credit.page)}" target="_blank" rel="noopener">«${esc(c.credit.title)}»</a>, ${esc(c.credit.author)} · <a href="${esc(c.credit.license_url)}" target="_blank" rel="noopener">${esc(c.credit.license)}</a> · Wikimedia Commons; кадровано, виконано колірну корекцію</li>`).join('')}</ul></details>`;
    if (!motion() || D.cinePosters || !('IntersectionObserver' in window)) return;   /* однофайловий бандл: лише постери */
    sec.classList.add('is-pinned');
    rail.innerHTML = chs.map(c => `<a href="#cine-${esc(c.id)}"><span>${esc(c.word)}</span></a>`).join('');
    const layers = $$('.cine__v', sec), items = $$('.cine__ch', list), dots = $$('a', rail);
    let cur = -1, front = 0, inView = false;
    const prof = () => (mobileLayout() && innerHeight > innerWidth ? 'm' : 'w');
    function load(v, id) {
      const n = id + '-' + prof();
      if (v.dataset.clip === n) return;
      v.dataset.clip = n; v.removeAttribute('src'); v.innerHTML = '';
      v.poster = C_BASE + n + '.webp';
      if (!D.mp4Only && document.createElement('video').canPlayType('video/webm; codecs="vp9"')) {
        const a = document.createElement('source'); a.src = C_BASE + n + '.webm'; a.type = 'video/webm'; v.append(a);
      }
      const b = document.createElement('source'); b.src = C_BASE + n + '.mp4'; b.type = 'video/mp4'; v.append(b);
      v.load();
    }
    function show(i) {
      if (i === cur) return;
      cur = i;
      items.forEach((el, k) => el.classList.toggle('is-cur', k === i));
      dots.forEach((el, k) => el.classList.toggle('is-on', k === i));
      const next = layers[1 - front], prev = layers[front];
      load(next, chs[i].id);
      next.classList.add('is-on'); prev.classList.remove('is-on');
      if (inView) { const pr = next.play(); if (pr && pr.catch) pr.catch(() => {}); }
      setTimeout(() => { if (!prev.classList.contains('is-on')) prev.pause(); }, 1200);
      front = 1 - front;
      const after = chs[i + 1]; if (after) setTimeout(() => { const spare = layers[1 - front]; if (!spare.classList.contains('is-on')) { load(spare, after.id); spare.preload = 'auto'; } }, 1400);
      sec.dataset.cur = chs[i].id;
    }
    const cio = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) show(+e.target.dataset.i); }), { rootMargin: '-45% 0px -45% 0px' });
    items.forEach(el => cio.observe(el));
    new IntersectionObserver(es => es.forEach(e => {
      inView = e.isIntersecting;
      if (inView) { if (cur < 0) show(0); const v = layers[front]; const pr = v.play(); if (pr && pr.catch) pr.catch(() => {}); playing.add(v); }   /* front — видимий шар */
      else layers.forEach(x => { x.pause(); playing.delete(x); });
    }), { threshold: 0 }).observe(sec);
  }

  /* ───── СТАРТ ───── */
  function start() {
    profile();
    renderPark(); renderJobs(); renderCalc(); renderMats(); renderProof(); renderCine(); renderGeo(); loadBusiness();
    reveal();
    measure(); render();
    /* відео героя — після load і першого простою: до того кадр тримає постер, а 3–5 МБ не конкурують зі шрифтами й скриптами */
    const afterLoad = fn => { const idle = () => ('requestIdleCallback' in window ? requestIdleCallback(fn, { timeout: 800 }) : setTimeout(fn, 1));
      document.readyState === 'complete' ? idle() : addEventListener('load', idle, { once: true }); };
    /* анімація логотипа: один раз, після load. VP9 з альфою — Chrome/Edge/Firefox/Android; Safari альфу VP9 не показує
       (замість прозорості — чорне тло), тому там і в однофайловій збірці лишається статичний кадр. Перший кадр анімації = статичний. */
    const logo = $('.logo-hero'), lv = $('#logoAnim');
    const ua = navigator.userAgent, appleWebKit = /AppleWebKit/.test(ua) && !/Chrome|Chromium|Edg|CriOS|FxiOS|Android/.test(ua);
    if (logo && lv && motion() && !D.videoData && !appleWebKit && lv.canPlayType('video/webm; codecs="vp9"')) afterLoad(() => {
      lv.src = 'media/logo/pbt-logo.webm';
      lv.addEventListener('playing', () => logo.classList.add('is-anim'), { once: true });
      lv.addEventListener('ended', () => logo.classList.remove('is-anim'), { once: true });   // останній кадр = статичний
      const pr = lv.play(); if (pr && pr.catch) pr.catch(() => {});
    });
    if (motion() && hVideo) afterLoad(() => {
      attachVideo(hVideo, 'hero-wide', { tall: true }); hVideo.preload = 'auto';
      /* WebKit (Safari) відхиляє ранні play() з NotAllowedError навіть для muted-відео (виміряно 08.10: відмови до ~1.46 с,
         play() о 1.5 с проходить). Точну умову не встановлено ⇒ повтор із наростаючою паузою, до 8 спроб, лише поки герой у кадрі. */
      let tries = 0;
      const go = () => {
        if (!hVideo.paused || scrollY >= innerHeight || document.hidden) return;
        const pr = hVideo.play();
        if (pr && pr.catch) pr.catch(() => { if (++tries < 8) setTimeout(go, 200 * tries); });
      };
      go();
      hVideo.addEventListener('canplay', go, { once: true });
    });
    requestAnimationFrame(() => hero.classList.add('is-lit'));
    sparkWake();
    document.addEventListener('visibilitychange', () => { if (document.hidden) { if (hVideo) hVideo.pause(); playing.forEach(v => v.pause()); } else if (motion()) { sparkWake(); if (hVideo && heroP < 1) hVideo.play().catch(() => {}); playing.forEach(v => v.play().catch(() => {})); } });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { measure(); render(); });
    addEventListener('load', () => { measure(); render(); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
