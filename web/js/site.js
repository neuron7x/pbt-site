/* ПЛЕЙНБУД — сцени, стани, інтерактив. Без залежностей; рух — функція прогресу скролу й видимості.
   Контракт валідації заявки спільний із сервером: tests/contracts/lead_vectors.json (window.PBTv — чиста функція для тестів). */
(function () {
  'use strict';
  const D = window.PBT || {};
  const doc = document.documentElement;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const reduceQuery = matchMedia('(prefers-reduced-motion: reduce)');
  let reduced = reduceQuery.matches, manualPaused = false;
  const MOTION_KEY = 'pbt-motion-paused';
  try { manualPaused = localStorage.getItem(MOTION_KEY) === '1'; } catch (_) { /* приватне сховище */ }
  // Завантажений профіль static — обмеження якості; зміна системної переваги його не скасовує.
  const quality = () => doc.dataset.quality || 'full';
  const motion = () => quality() !== 'static' && !reduced && !manualPaused;
  // CPU-constrained/Save-Data/reduced-motion devices stay poster-first.
  // Browser tests explicitly emulate the full and constrained profiles.
  const videoCapable = () => quality() === 'full' && !reduced;
  const videoAllowed = () => videoCapable() && !manualPaused && !document.hidden;
  const mediaSync = new Set();
  const motionToggle = $('#motionToggle');
  function syncMotion() {
    const paused = !motion();
    doc.dataset.motion = paused ? 'paused' : 'running';
    if (motionToggle) {
      motionToggle.hidden = false;
      motionToggle.disabled = quality() === 'static' || reduced;
      motionToggle.setAttribute('aria-pressed', String(paused));
      const label = motionToggle.disabled ? 'Анімації вимкнено' : paused ? 'Відновити анімації' : 'Призупинити анімації';
      motionToggle.textContent = label;
      motionToggle.setAttribute('aria-label', label);
    }
    if (!videoAllowed()) $$('video').forEach(video => video.pause());
    mediaSync.forEach(sync => sync());
    if (paused) {
      $$('.unit').forEach(unit => { unit.style.removeProperty('--rx'); unit.style.removeProperty('--ry'); });
      $('#glow')?.classList.remove('is-on');
    }
    reveal(); render();
  }
  motionToggle?.addEventListener('click', () => {
    if (quality() === 'static' || reduced) return;
    manualPaused = !manualPaused;
    try { localStorage.setItem(MOTION_KEY, manualPaused ? '1' : '0'); } catch (_) { /* приватне сховище */ }
    syncMotion();
  });
  reduceQuery.addEventListener('change', event => { reduced = event.matches; syncMotion(); });
  // Відкладений play() не повинен обійти паузу або системне обмеження руху.
  document.addEventListener('play', event => {
    if (event.target.tagName === 'VIDEO' && !videoAllowed()) event.target.pause();
  }, true);
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
    if (D.videoData || D.heroSD || c.saveData || /(^|-)2g$|^3g$/.test(c.effectiveType || '')) return false;   // однофайлова збірка несе лише 720
    return innerWidth * (devicePixelRatio || 1) >= 1600;
  }
  function attachVideo(video, name, { tall } = {}) {
    if (!video) return false;
    if (video.dataset.ready) return true;
    let n = tall && mobileLayout() ? name.replace('-wide', '-tall') : name;
    if (n === 'hero-wide' && !heroHD()) n = 'hero-wide-720';          // 1920 — лише коли екран його покаже й мережа витягне
    // Budget-omitted standalone clips keep their posters without requesting absent files.
    if (D.videoData && !D.videoData[n + '.mp4']) return false;
    video.muted = true; video.loop = true; video.playsInline = true; video.setAttribute('muted', ''); video.preload = 'none';
    if (D.videoData || D.mp4Only || !document.createElement('video').canPlayType('video/webm; codecs="vp9"')) {
      video.src = vsrc(n, 'mp4');
    } else {
      const s1 = document.createElement('source'); s1.src = vsrc(n, 'webm'); s1.type = 'video/webm';
      const s2 = document.createElement('source'); s2.src = vsrc(n, 'mp4'); s2.type = 'video/mp4';
      video.append(s1, s2);
    }
    video.dataset.ready = '1';
    return true;
  }
  const playing = new Set(), visibleCards = new Set();
  function syncCardVideo(card) {
    const v = $('video', card); if (!v) return;
    if (visibleCards.has(card) && videoAllowed() && attachVideo(v, v.dataset.video)) {
      v.preload = 'auto';
      const p = v.play(); if (p && p.catch) p.catch(() => {});
      card.classList.add('is-playing'); playing.add(v);
    } else { v.pause(); card.classList.remove('is-playing'); playing.delete(v); }
  }
  mediaSync.add(() => visibleCards.forEach(syncCardVideo));
  const vio = 'IntersectionObserver' in window ? new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) visibleCards.add(e.target); else visibleCards.delete(e.target);
    syncCardVideo(e.target);
  }), { threshold: .45 }) : null;
  const watchVideo = el => { if (vio) vio.observe(el); };

  /* ───── НАВІГАЦІЯ, МЕНЮ ───── */
  const nav = $('#nav'), burger = $('.burger'), menu = $('#menu'), menuClose = $('#menuClose');
  const menuBackdrop = [nav, $('#main'), $('.foot'), $('#gauge'), motionToggle, $('.skip')].filter(Boolean);
  const menuInertBefore = new Map();
  let lastY = scrollY, navHidden = false, returnFocus = null;
  const themeButtons = Array.from(document.querySelectorAll('[data-theme-choice]'));
  const THEME_KEY = 'pbt-theme';
  function applyTheme(value, persist) {
    const next = value === 'precision' ? 'precision' : 'sky';
    if (doc.dataset.theme !== next) {
      doc.dataset.theme = next;
      nav.classList.remove('is-hidden');
      navHidden = false;
    }
    themeButtons.forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.themeChoice === next));
    });
    const meta = $('meta[name="theme-color"]');
    if (meta) meta.content = next === 'precision' ? '#101820' : '#0D6AE0';
    const face = $('#themeFontPreload');
    if (face) face.href = 'fonts/' + (next === 'precision' ? 'IBMPlexSans-600-cyrillic.woff2' : 'Tektur-var-cyrillic.woff2');
    if (persist) {
      try { localStorage.setItem(THEME_KEY, next); } catch (_) { /* приватний режим / заблоковане сховище */ }
    }
    // Обидві теми спільно використовують DOM і медіа. Після зміни стилю
    // перераховуємо геометрію й не підтримуємо прихований Canvas-цикл.
    requestAnimationFrame(() => { measure(); render(); sparkWake(); });
  }
  themeButtons.forEach(button => button.addEventListener('click', () => applyTheme(button.dataset.themeChoice, true)));
  // Інші вкладки застосують спільний вибір під час наступного завантаження:
  // миттєва перебудова активної сторінки спричиняє непередбачений CLS.

  function openMenu(on, restoreFocus = true) {
    if (on === !menu.hidden) return;
    if (on) returnFocus = document.activeElement;
    menu.hidden = !on;
    burger.setAttribute('aria-expanded', String(on));
    document.body.style.overflow = on ? 'hidden' : '';
    if (on) nav.classList.remove('is-hidden');
    /* Модальний навігаційний шар: фон неактивний для Tab і скринридерів. */
    menuBackdrop.forEach(el => {
      if (on) { menuInertBefore.set(el, el.inert); el.inert = true; }
      else el.inert = menuInertBefore.get(el) || false;
    });
    if (!on) menuInertBefore.clear();
    if (on) menuClose.focus();
    else if (restoreFocus) (returnFocus && returnFocus.isConnected ? returnFocus : burger).focus({ preventScroll: true });
  }
  burger.addEventListener('click', () => openMenu(true));
  menuClose.addEventListener('click', () => openMenu(false));
  Array.from(menu.querySelectorAll('a')).forEach(a => a.addEventListener('click', () => {
    const hash = a.getAttribute('href');
    openMenu(false, false);
    if (hash && hash.startsWith('#') && hash.length > 1 && !a.hasAttribute('data-req')) {
      const target = document.getElementById(hash.slice(1));
      if (target) requestAnimationFrame(() => {
        target.setAttribute('tabindex', '-1');
        target.focus({ preventScroll: true });
      });
    }
  }));
  addEventListener('keydown', e => {
    if (menu.hidden) return;
    if (e.key === 'Escape') { e.preventDefault(); openMenu(false); return; }
    if (e.key !== 'Tab') return;
    const focusable = Array.from(menu.querySelectorAll('button:not([disabled]), a[href]')).filter(el => el.getClientRects().length);
    if (!focusable.length) { e.preventDefault(); return; }
    if (e.shiftKey && document.activeElement === focusable[0]) {
      e.preventDefault(); focusable[focusable.length - 1].focus();
    } else if (!e.shiftKey && document.activeElement === focusable[focusable.length - 1]) {
      e.preventDefault(); focusable[0].focus();
    }
  });

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
      else if (p < 1 && hVideo && hVideo.paused && hVideo.dataset.ready && videoAllowed()) { const pr = hVideo.play(); if (pr && pr.catch) pr.catch(() => {}); }
    } else {
      // Пауза посеред прокручування не залишає заголовок прозорим при поверненні нагору.
      hCenter.style.removeProperty('opacity'); hCenter.style.removeProperty('transform');
      if (hVideo) hVideo.style.removeProperty('transform');
      water.style.removeProperty('--wl');
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
    ctx = spark.getContext('2d');
    if (!ctx) { dots = []; return; }   // Decorative canvas may be unavailable; page initialization continues.
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    dots = Array.from({ length: mobileLayout() ? 28 : 60 }, () => ({ x: Math.random() * cW, y: Math.random() * cH, r: .6 + Math.random() * 1.8, s: .15 + Math.random() * .45, ph: Math.random() * 6.28 }));
  }
  /* цикл іскор засинає, коли герой поза кадром або вкладка прихована (раніше rAF крутився вічно: Lighthouse devtools 09.10
     — сторінка не ставала «тихою»); прокидає його sparkWake() зі скролу й visibilitychange */
  let sparkOn = false;
  const sparkWake = () => { if (!sparkOn && ctx && motion() && quality() === 'full' && heroP < 1 && !document.hidden) { sparkOn = true; requestAnimationFrame(sparkLoop); } };
  function sparkLoop(t) {
    if (!ctx || getComputedStyle(spark).display === 'none' || quality() !== 'full' || !motion() || heroP >= 1 || document.hidden) { sparkOn = false; return; }
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
  addEventListener('resize', () => { clearTimeout(rT); rT = setTimeout(() => { if (!mobileLayout() && !menu.hidden) openMenu(false, false); profile(); measure(); render(); }, 120); });

  /* ───── ПОЯВА СЕКЦІЙ, ЛІЧИЛЬНИКИ, МАРШРУТИ ───── */
  const rio = 'IntersectionObserver' in window ? new IntersectionObserver(es => es.forEach(e => {
    if (!e.isIntersecting) return;
    e.target.classList.add('is-in'); rio.unobserve(e.target);
    $$('[data-count]', e.target).forEach(countUp);
    if (e.target.dataset.count !== undefined) countUp(e.target);
  }), { threshold: 0, rootMargin: '20% 0px 20% 0px' }) : null;   // симетрична зона появи: стрибок до центру високої сітки не пропускає заголовок
  function reveal(root) {
    $$('.rv', root || document).forEach(el => { if (!rio || !motion()) el.classList.add('is-in'); else rio.observe(el); });
    $$('[data-count]', root || document).forEach(el => { if (el.closest('.rv')) return; if (!rio || !motion()) countUp(el); else rio.observe(el); });   /* лічильники поза .rv (герой) */
  }
  function countUp(el) {
    if (el.dataset.done) return; el.dataset.done = '1';
    const to = parseFloat(el.dataset.count), suf = el.dataset.suffix || '', dur = 1400, t0 = performance.now();
    if (!motion()) { el.textContent = fmt(to) + suf; return; }
    const step = t => { const k = motion() ? ease(clamp((t - t0) / dur, 0, 1)) : 1; el.textContent = fmt(to * k) + suf; if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }

  /* ───── ПАРК ───── */
  const catName = id => (D.cats.find(c => c.id === id) || {}).name || '';
  const unitPurpose = u => /мульчер/i.test(u.name) ? 'Мульчування порослі.' :
    /дробарк/i.test(u.name) ? 'Дроблення бетону й каменю.' :
      (D.cats.find(c => c.id === u.cat) || {}).lead || 'Підберемо комплектацію під ваше завдання.';
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
          ${u.specs.length ? `<dl class="unit__specs">${u.specs.map(s => `<div><dt>${esc(s.k)}</dt><dd>${esc(s.v)}</dd></div>`).join('')}</dl>` : `<p class="unit__purpose">${esc(unitPurpose(u))}</p>`}</div>
        <div class="unit__foot"><p class="unit__price${u.price ? '' : ' is-neg'}">${u.price ? `${fmt(u.price)} <small>грн/${esc(u.unit)}</small>` : 'договірна'}</p>
          <button class="btn btn--sm" type="button" data-req="${u.cat === 'trans' ? 'transport' : 'rent'}" data-subject="${esc(u.name)}">У заявку</button></div>
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
    if (finePointer) grid.addEventListener('pointermove', e => {         /* нахил картки за вказівником */
      if (!motion() || doc.dataset.theme === 'precision') return;
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
  // Єдина чиста модель: UI читає результат, але не обчислює тариф.
  const quoteModel = window.PBTQuote;
  if (!quoteModel || typeof quoteModel.quote !== 'function')
    throw new Error('Відсутнє ядро кошторису PBTQuote');

  let totalShown = 0, totalAnim = 0;
  function tweenTotal(el, to) {
    const from = totalShown, t0 = performance.now(), id = ++totalAnim;
    if (!motion()) { totalShown = to; el.innerHTML = `${fmt(to)} <small>грн</small>`; return; }
    const step = t => { if (id !== totalAnim) return; const k = motion() ? ease(clamp((t - t0) / 520, 0, 1)) : 1; totalShown = from + (to - from) * k; el.innerHTML = `${fmt(totalShown)} <small>грн</small>`; if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }
  function renderCalc() {
    const sel = $('#cMachine'), hr = $('#cHours'), hrN = $('#cHoursN'), km = $('#cKm'), kmN = $('#cKmN');
    // Hashed CSP forbids inline handlers; keyboard Enter must not submit this form.
    $('#calcForm').addEventListener('submit', event => event.preventDefault());
    const priced = D.fleet.filter(u => u.price && u.unit === 'год');
    sel.innerHTML = priced.map(u => `<option value="${u.id}">${esc(u.name)} — ${fmt(u.price)} грн/год</option>`).join('');
    sel.disabled = !priced.length;
    const fill = r => r.style.setProperty('--p', `${((r.value - r.min) / (r.max - r.min) * 100).toFixed(1)}%`);
    const sync = (a, b) => a.addEventListener('input', () => { b.value = a.value; fill(hr); fill(km); calc(); });
    sync(hr, hrN); sync(hrN, hr); sync(km, kmN); sync(kmN, km);
    sel.addEventListener('change', calc);
    function calc() {
      const u = priced.find(x => x.id === sel.value) || priced[0];
      $('#cMachineSummary').textContent = sel.selectedOptions[0]?.textContent || '';
      const crane = u?.cat === 'crane';
      km.disabled = kmN.disabled = crane;
      const hours = hrN.valueAsNumber, kmv = crane ? 0 : kmN.valueAsNumber;
      const hoursValid = Number.isInteger(hours) && hours >= 1 && hours <= 5000;
      const kmValid = Number.isInteger(kmv) && kmv >= 0 && kmv <= 3000;
      if (!hoursValid || !kmValid) {
        totalAnim += 1; totalShown = 0;
        $('#cTotal').textContent = '—';
        $('#cLines').textContent = !hoursValid ? 'Вкажіть ціле число годин від 1 до 5000.' : 'Вкажіть цілу відстань від 0 до 3000 км.';
        $('#cOut').dataset.total = ''; $('#cOut').dataset.estimate = 'invalid';
        $('#cOrder').disabled = true;
        return;
      }
      const estimate = quoteModel.quote(u, D.trailers, hours, kmv);
      if (!estimate) {
        // Невалідна модель скасовує tween і стирає ПОПЕРЕДНЮ суму.
        // Інакше стара цифра лишалась видимою при коректному fail-closed.
        totalAnim += 1;
        totalShown = 0;
        $('#cTotal').textContent = '—';
        $('#cLines').textContent = 'Розрахунок тимчасово недоступний. Уточніть вартість подачі.';
        $('#cOut').dataset.total = '';
        $('#cOut').dataset.estimate = 'invalid';
        $('#cOrder').disabled = true;
        return;
      }
      $('#cOrder').disabled = false;
      const needsTrailer = !crane && kmv > 0;
      const tr = estimate.trailer, transportKnown = estimate.status === 'complete';
      const rent = estimate.rental, deliv = estimate.delivery, total = estimate.displayed;
      tweenTotal($('#cTotal'), total);
      const deliveryLine = crane
        ? '<div><span>Подача автокрана</span><b>уточнюється</b></div>'
        : !needsTrailer
          ? '<div><span>Подача тралом</span><b>не заявлена</b></div>'
          : tr
            ? `<div><span>Подача тралом ${esc(tr.name.replace(/^Трал\s*/, ''))}: ${kmv} км × ${tr.rate} грн</span><b>${fmt(deliv)} грн</b></div>`
            : '<div><span>Подача тралом: маса невідома або поза діапазоном</span><b>уточнюється</b></div>';
      $('#cLines').innerHTML = `<div><span>Оренда: ${hours} год × ${fmt(u.price)} грн</span><b>${fmt(rent)} грн</b></div>` +
        deliveryLine +
        `<div><span>${transportKnown ? 'Разом, орієнтовно' : 'Оренда без подачі'}</span><b>${fmt(total)} грн</b></div>`;
      $('#cOrder').dataset.subject = `${u.name} — ${hours} год${crane ? '' : `, подача ${kmv} км${transportKnown ? '' : ' (ціну уточнити)'}`}`;
      $('#cOrder').dataset.calcHours = String(hours);
      $('#cOrder').dataset.calcKm = crane ? '' : String(kmv);
      $('#cOut').dataset.total = transportKnown ? String(total) : '';
      $('#cOut').dataset.estimate = transportKnown ? 'with-delivery' : 'rent-only';
    }
    fill(hr); fill(km); calc(); $('#calcUnavailable').hidden = true;
    window.PBTcalc = (id, hours, kmv) => {
      const u = priced.find(x => x.id === id);
      return quoteModel.legacyTotal(u, D.trailers, hours, kmv);
    };
  }

  /* ───── МАТЕРІАЛИ, ДОКАЗ, ГЕОГРАФІЯ ───── */
  const x2 = src => /^media\/.+\.webp$/.test(src) ? ` srcset="${src} 1x, ${src.replace(/\.webp$/, '@2x.webp')} 2x"` : '';   // data:URI однофайлової збірки — без srcset
  function renderMats() {
    $('#mats').innerHTML = `<div class="tiles">${D.materials.map((m, i) => `
      <article class="tile rv" style="--d:${(i % 4) * 80}ms"><figure><img src="${m.img}"${x2(m.img)} alt="${esc(m.name)}" width="639" height="396" loading="lazy" decoding="async"><span class="tile__group">${esc(m.group)}</span></figure>
        <div class="tile__body"><h4>${esc(m.name)}</h4><p class="tile__price">${fmt(m.price)} <small>грн/${esc(m.unit)}</small></p><p class="tile__doc">У вихідному каталозі: ${esc(m.doc)}</p><button class="btn btn--sm tile__order" type="button" data-req="material" data-subject="${esc(m.name)}">У заявку</button></div></article>`).join('')}</div>`;
  }
  function renderProof() {
    const standalone = window.PBT_BUNDLE && !D.mp4Only;
    $('#reel').innerHTML = D.proof.map((p, i) => {
      const tag = standalone ? 'article' : 'a';
      const link = standalone ? '' : ` href="${esc(proofUrl(p.url) || '#roboty')}" target="_blank" rel="noopener"`;
      return `<${tag} class="proof-card rv" style="--d:${(i % 3) * 90}ms"${link} aria-label="${esc(p.t)}: ${esc(p.s)}${standalone ? '' : ' — відкрити відео'}">
        <figure><img src="${p.poster}" alt="" width="640" height="360" loading="lazy" decoding="async"><video data-video="${p.video}" poster="${p.poster}" aria-hidden="true" tabindex="-1"></video>
        ${standalone ? '' : '<i aria-hidden="true"></i>'}<figcaption><b>${esc(p.t)}</b><span>${esc(p.s)}</span></figcaption></figure></${tag}>`;
    }).join('');
    $$('#reel .proof-card').forEach(watchVideo);
    const logos = duplicate => D.partners.map((p, i) => `<li${duplicate ? ' aria-hidden="true"' : ''}><img src="${p}" alt="${duplicate ? '' : `Логотип в ілюстративній добірці ${i + 1}`}" width="196" height="196" loading="lazy" decoding="async"></li>`).join('');
    $('#partners').innerHTML = logos(false) + logos(true);      /* декоративний повтор не дублює доступний список */
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
    svg.addEventListener('pointerover', e => { const p = e.target.closest('.obl'); if (!p) return; hov.textContent = p.dataset.ua ? `${p.dataset.ua} область — ${p.dataset.ua === home ? 'база запитів' : 'у переліку регіонів'}` : `${p.dataset.name} — за запитом`; });
    svg.addEventListener('pointerout', () => { hov.textContent = ''; });
  }

  /* External links from configuration: https only, parsed by the platform, not by a prefix check. */
  function httpsUrl(value) {
    try { const u = new URL(String(value)); return u.protocol === 'https:' && !/["'<>\s]/.test(String(value)) ? u.href : null; } catch (_) { return null; }
  }

  function proofUrl(value) {
    // Rebranded cards open the existing local clips; source attribution stays in provenance.
    const text = String(value || '');
    return /^media\/video\/[a-z0-9-]+\.mp4$/.test(text) ? text : httpsUrl(text);
  }

  /* ───── КОНФІГУРАЦІЯ БІЗНЕСУ: /api/config → канали, підвал (fallback — вбудовані дані) ───── */
  function applyBusiness(b) {
    const c = b.contacts || {};
    const tel = p => p ? `tel:${String(p).replace(/[^+\d]/g, '')}` : '#zapyt';
    $$('[data-phone]').forEach(a => { a.textContent = phoneHuman(c.phone) || 'Телефон уточнюється'; if (a.tagName === 'A') a.href = tel(c.phone); });
    $$('[data-phone2]').forEach(a => {
      const present = !!c.phone2, row = a.closest('[data-phone2-row]') || a;
      row.hidden = !present; a.textContent = phoneHuman(c.phone2) || '';
      if (a.tagName === 'A') { if (present) a.href = tel(c.phone2); else a.removeAttribute('href'); }
    });
    const email = typeof c.email === 'string' && /^[^\s@"<>]+@[^\s@"<>]+$/.test(c.email) ? c.email : '';
    $$('[data-email]').forEach(a => {
      a.hidden = !email; a.textContent = email;
      if (a.tagName === 'A') { if (email) a.href = `mailto:${email}`; else a.removeAttribute('href'); }
    });
    $$('[data-brand]').forEach(e => e.textContent = b.brand?.nameUk || 'ПЛЕЙНБУД');
    const requisites = { director: b.director, 'bank-name': b.bank?.name, 'bank-iban': b.bank?.iban };
    Object.entries(requisites).forEach(([key, value]) => {
      $$(`[data-${key}]`).forEach(e => { e.textContent = value || ''; });
      $$(`[data-${key}-row]`).forEach(e => { e.hidden = !value; });
    });
    $$('[data-address]').forEach(e => e.textContent = b.address || 'Адреса уточнюється');
    $$('[data-legal]').forEach(e => e.textContent = b.legalName || 'ТОВ «ПЛЕЙНБУД»');
    $$('[data-edrpou]').forEach(e => e.textContent = b.edrpou ? `ЄДРПОУ ${b.edrpou}` : '');
    const h = b.hours || {};
    $$('[data-hours]').forEach(e => e.textContent = h['mo-fr'] ? `Пн–Пт ${h['mo-fr']} · Сб ${h.sa || '—'} · Нд ${h.su || '—'}` : 'Графік роботи уточнюється');
    const ch = [];
    if (c.phone) ch.push({ k: 'Телефон', v: phoneHuman(c.phone), href: tel(c.phone) });
    if (c.phone2) ch.push({ k: 'Телефон', v: phoneHuman(c.phone2), href: tel(c.phone2) });
    if (c.viber) ch.push({ k: 'Viber', v: phoneHuman(c.viber), href: `viber://chat?number=${encodeURIComponent(c.viber)}` });
    if (c.telegram) ch.push({ k: 'Telegram', v: c.telegram, href: `https://t.me/${encodeURIComponent(String(c.telegram).replace('@', ''))}` });
    if (email) ch.push({ k: 'Email', v: email, href: `mailto:${email}` });
    $('#channels').innerHTML = ch.map(x => `<a href="${esc(x.href)}"><b>${esc(x.v)}</b><span>${x.k}</span></a>`).join('') || '<div><b>Канали зв’язку</b><span>уточнюються</span></div>';
    const soc = [['tiktok', 'TikTok'], ['instagram', 'Instagram'], ['facebook', 'Facebook'], ['youtube', 'YouTube']].filter(([k]) => httpsUrl(c[k]));
    $$('[data-social]').forEach(ul => { ul.hidden = !soc.length; ul.innerHTML = soc.map(([k, n]) => `<li><a href="${esc(httpsUrl(c[k]))}" target="_blank" rel="noopener">${n}</a></li>`).join(''); });
  }
  function loadBusiness() {
    const fb = () => applyBusiness(D.business || {});
    fb();
    if (window.PBT_BUNDLE || location.protocol === 'file:') return;
    fetch('/api/config', { cache: 'no-store' }).then(r => r.ok ? r.json() : Promise.reject()).then(j => applyBusiness(Object.keys(j).length ? j : D.business)).catch(fb);
  }

  /* ───── ВАЛІДАЦІЯ ЗАЯВКИ: той самий контракт, що й сервер ───── */
  const kyivToday = () => {
    const opts = { year: 'numeric', month: '2-digit', day: '2-digit', calendar: 'iso8601', numberingSystem: 'latn' };
    // Locale fallback can reorder date fields; compare only explicitly assembled ISO dates.
    const iso = formatter => {
      const parts = Object.fromEntries(formatter.formatToParts(new Date()).map(part => [part.type, part.value]));
      return `${parts.year}-${parts.month}-${parts.day}`;
    };
    // Browsers with tzdata older than 2022b know only the old zone name; a RangeError here would silently block the form.
    for (const timeZone of ['Europe/Kyiv', 'Europe/Kiev']) {
      try { return iso(new Intl.DateTimeFormat('en-CA', { ...opts, timeZone })); } catch (_) { /* next name */ }
    }
    return iso(new Intl.DateTimeFormat('en-CA', opts));
  };
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
      const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
      if (d.getUTCFullYear() !== +m[1] || d.getUTCMonth() !== +m[2] - 1 || d.getUTCDate() !== +m[3]) return null;
      return v >= kyivToday() ? v : null;   // ISO dates order lexicographically; same civil date as the server.
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
  const method = $('#method'), contact = $('#contact');
  // Значення калькулятора належать лише вибраній зміні. Ручний ввід має пріоритет.
  const calcValues = new Map();
  const hoursByType = new Map();
  const subjectsByType = new Map();
  let currentRequestType = form.querySelector('input[name="type"]:checked')?.value || 'rent';
  ['subject', 'hours', 'km'].forEach(name => $(`#${name}`).addEventListener('input', () => calcValues.delete(name)));
  function releaseCalcValues() {
    calcValues.forEach((saved, name) => {
      const field = $(`#${name}`);
      if (field.value === saved.automatic) field.value = saved.previous;
    });
    calcValues.clear();
  }
  function fillCalcValue(name, value) {
    const field = $(`#${name}`), saved = calcValues.get(name);
    const previous = saved && field.value === saved.automatic ? saved.previous : field.value;
    field.value = value;
    calcValues.set(name, { previous, automatic: value });
  }
  function switchRequestType(next) {
    if (!next || next === currentRequestType) return;
    releaseCalcValues();
    hoursByType.set(currentRequestType, $('#hours').value);
    subjectsByType.set(currentRequestType, $('#subject').value);
    $('#hours').value = hoursByType.get(next) || '';
    $('#subject').value = subjectsByType.get(next) || '';
    currentRequestType = next;
    setErr('hours', ''); setErr('subject', '');
  }
  function syncContactMode() {
    const telegram = method.value === 'telegram';
    contact.inputMode = telegram ? 'text' : 'tel';
    contact.autocomplete = telegram ? 'off' : 'tel';
    contact.placeholder = telegram ? '@username або номер телефону' : '067 000 00 00';
  }
  method.addEventListener('change', syncContactMode);
  form.addEventListener('change', e => { if (e.target.name === 'type') switchRequestType(e.target.value); });
  form.addEventListener('reset', () => {
    calcValues.clear(); hoursByType.clear(); subjectsByType.clear();
    queueMicrotask(() => {
      currentRequestType = form.querySelector('input[name="type"]:checked')?.value || 'rent';
      syncContactMode();
    });
  });
  syncContactMode();
  let idemKey = null, idemHash = '';
  /* A reload loses in-memory state, so a lost response would mint a second lead. Only an opaque key,
     a keyed digest of the request and an expiry are kept: no field value, per tab, for 30 minutes. */
  const PENDING = 'pbt.pendingLead', PENDING_TTL_MS = 30 * 60 * 1000;
  const pendingRead = () => {
    try { const r = JSON.parse(sessionStorage.getItem(PENDING)); return r && typeof r.k === 'string' && typeof r.d === 'string' && r.x > Date.now() ? r : null; } catch (_) { return null; }
  };
  const pendingWrite = r => { try { sessionStorage.setItem(PENDING, JSON.stringify(r)); } catch (_) { /* blocked storage: in-memory idempotency only */ } };
  const pendingClear = () => { try { sessionStorage.removeItem(PENDING); } catch (_) { /* nothing was stored */ } };
  async function leadDigest(key, body) {
    try {
      const raw = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`${key}\n${body}`));
      return Array.from(new Uint8Array(raw), b => b.toString(16).padStart(2, '0')).join('');
    } catch (_) { return null; }   // crypto.subtle needs a secure context; plain HTTP degrades to in-memory.
  }
  async function bindIdempotencyKey(body) {
    if (body !== idemHash) {
      const prior = pendingRead();
      const same = prior && await leadDigest(prior.k, body) === prior.d;
      idemKey = same ? prior.k : uuid();
      idemHash = body;
    }
    const d = await leadDigest(idemKey, body);
    if (d) pendingWrite({ k: idemKey, d, x: Date.now() + PENDING_TTL_MS });
  }
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join(''));
  function setErr(name, text) {
    const group = form.querySelector(`[data-field="${name}"]`);
    if (!group) return;
    const active = !!text, field = $('input, select, textarea', group), error = $('.err', group);
    group.classList.toggle('is-err', active);
    if (error) { error.id = `error-${name}`; error.textContent = text || ''; }
    if (!field) return;
    if (active) field.setAttribute('aria-invalid', 'true');
    else field.removeAttribute('aria-invalid');
    if (error) {
      const ids = (field.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean).filter(id => id !== error.id);
      if (active) ids.push(error.id);
      if (ids.length) field.setAttribute('aria-describedby', ids.join(' '));
      else field.removeAttribute('aria-describedby');
    }
  }
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
    if ($('#send').disabled) return;
    const p = payload(); const err = validate(p);
    ['subject', 'hours', 'km', 'date', 'contact', 'comment'].forEach(k => setErr(k, err[k]));
    msg.classList.remove('is-on');
    if (Object.keys(err).length) { const first = form.querySelector('.is-err input, .is-err textarea'); if (first) first.focus(); return; }
    const h = JSON.stringify(p);
    const btn = $('#send'); btn.disabled = true; btn.textContent = 'Надсилаю…';
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 15000);
    try {
      await bindIdempotencyKey(h);
      if (window.PBT_BUNDLE) throw new Error('bundle');
      const r = await fetch('/api/lead', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idemKey }, body: h, signal: controller.signal });
      const j = await r.json().catch(error => { if (controller.signal.aborted) throw error; return {}; });
      if (r.status === 201) {
        // An HTTP status alone cannot confirm the durable lead receipt or clear safe retry state.
        if (!j || j.ok !== true || typeof j.ref !== 'string' || !/^PBT-[0-9]{6,}$/.test(j.ref) || !/[1-9]/.test(j.ref)) throw new Error('invalid_lead_receipt');
        pendingClear();
        form.hidden = true; done.classList.add('is-on'); $('#ref').textContent = `№ ${j.ref.slice(4)}`; done.focus();
      } else if (r.status === 422 && j.fields) {
        pendingClear();   // Definitively not committed.
        Object.entries(j.fields).forEach(([k, v]) => setErr(k, v));
        msg.textContent = 'Перевірте позначені поля.'; msg.classList.add('is-on');
        const first = form.querySelector('.is-err input, .is-err select, .is-err textarea');
        if (first) first.focus();
      } else if (r.status === 429) { msg.textContent = j.message || 'Забагато запитів. Спробуйте через 10 хвилин або зателефонуйте.'; msg.classList.add('is-on'); }
      else { msg.textContent = 'Сервер не прийняв заявку. Спробуйте ще раз або зателефонуйте — номери поруч.'; msg.classList.add('is-on'); }
    } catch (_) {
      form.hidden = true; fallback.classList.add('is-on'); $('#fbText').textContent = humanText(p);
      fallback.focus();
    } finally { clearTimeout(deadline); btn.disabled = false; btn.textContent = 'Надіслати заявку'; }
  });
  $('#send').disabled = false;
  $('#formUnavailable').hidden = true;
  $('#fbCopy').addEventListener('click', async () => {
    const t = $('#fbText').textContent; const b = $('#fbCopy');
    try { await navigator.clipboard.writeText(t); b.textContent = 'Скопійовано'; } catch (_) { const r = document.createRange(); r.selectNodeContents($('#fbText')); const s = getSelection(); s.removeAllRanges(); s.addRange(r); b.textContent = 'Виділено — скопіюй'; }
    setTimeout(() => b.textContent = 'Скопіювати текст', 2500);
  });
  $('#again').addEventListener('click', () => { done.classList.remove('is-on'); form.hidden = false; form.reset(); idemHash = ''; pendingClear(); $('#subject').focus(); });
  $('#fbRetry')?.addEventListener('click', () => {
    fallback.classList.remove('is-on'); form.hidden = false;
    msg.textContent = 'Підтвердження не отримано. Можна повторити надсилання: незмінена заявка не дублюється.';
    msg.classList.add('is-on'); $('#send').focus();
  });

  document.addEventListener('click', e => {
    const b = e.target.closest('[data-req]'); if (!b) return;
    e.preventDefault();
    const t = b.dataset.req, s = b.dataset.subject;
    // Після підтвердженого успіху CTA означає новий намір; після обриву — безпечний повтор.
    if (done.classList.contains('is-on')) { idemHash = ''; idemKey = null; pendingClear(); }
    done.classList.remove('is-on'); fallback.classList.remove('is-on'); form.hidden = false;
    if (b.id !== 'cOrder') releaseCalcValues();
    switchRequestType(t);
    const radio = form.querySelector(`input[name="type"][value="${t}"]`); if (radio) radio.checked = true;
    if (s) {
      if (b.id === 'cOrder') fillCalcValue('subject', s);
      else $('#subject').value = s;
      setErr('subject', '');
    }
    if (b.id === 'cOrder') {
      fillCalcValue('hours', b.dataset.calcHours || '');
      fillCalcValue('km', b.dataset.calcKm || '');
      setErr('hours', ''); setErr('km', '');
    }
    if (b.tagName === 'A' && b.getAttribute('href') === '#zapyt' && location.hash !== '#zapyt' && /^(https?:|file:)$/.test(location.protocol)) {
      history.pushState(history.state, '', '#zapyt');
    }
    const subject = $('#subject');
    subject.focus({ preventScroll: true });
    // На вузькому екрані контакти й пояснення перед формою можуть займати кілька екранів.
    subject.scrollIntoView({ behavior: motion() ? 'smooth' : 'auto', block: 'center' });
  });

  /* ───── курсорне світло ───── */
  const glow = $('#glow');
  if (glow && finePointer && getComputedStyle(glow).display !== 'none') {
    let gx = 0, gy = 0, tx = 0, ty = 0, on = false;
    addEventListener('pointermove', e => { if (!motion()) return; tx = e.clientX; ty = e.clientY; if (!on || !glow.classList.contains('is-on')) { on = true; glow.classList.add('is-on'); } }, { passive: true });
    let run = false;                                   // цикл живе, лише поки світло доганяє курсор
    const loop = () => { if (!motion()) { run = false; on = false; return; } gx += (tx - gx) * .12; gy += (ty - gy) * .12; glow.style.transform = `translate3d(${gx.toFixed(1)}px,${gy.toFixed(1)}px,0)`;
      if (Math.abs(tx - gx) + Math.abs(ty - gy) > .5) requestAnimationFrame(loop); else run = false; };
    addEventListener('pointermove', () => { if (motion() && !run) { run = true; requestAnimationFrame(loop); } }, { passive: true });
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
    if (!videoCapable() || D.cinePosters || !('IntersectionObserver' in window)) return;   /* однофайловий бандл: лише постери */
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
      next.poster = C_BASE + chs[i].id + '-' + prof() + '.webp';
      if (videoAllowed()) load(next, chs[i].id);
      else {
        // Новий розділ у паузі показує власний постер, а не кадр попереднього кліпу.
        next.removeAttribute('src'); next.innerHTML = ''; delete next.dataset.clip; next.load();
      }
      next.classList.add('is-on'); prev.classList.remove('is-on');
      if (inView && videoAllowed()) { const pr = next.play(); if (pr && pr.catch) pr.catch(() => {}); }
      setTimeout(() => { if (!prev.classList.contains('is-on')) prev.pause(); }, 1200);
      front = 1 - front;
      const after = chs[i + 1]; if (after) setTimeout(() => { const spare = layers[1 - front]; if (videoAllowed() && !spare.classList.contains('is-on')) { load(spare, after.id); spare.preload = 'auto'; } }, 1400);
      sec.dataset.cur = chs[i].id;
    }
    function syncCine() {
      if (inView && videoAllowed()) {
        if (cur < 0) show(0);
        const v = layers[front]; load(v, chs[cur].id);
        const pr = v.play(); if (pr && pr.catch) pr.catch(() => {});
        playing.add(v);
      } else layers.forEach(v => { v.pause(); playing.delete(v); });
    }
    mediaSync.add(syncCine);
    const cio = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) show(+e.target.dataset.i); }), { rootMargin: '-45% 0px -45% 0px' });
    items.forEach(el => cio.observe(el));
    new IntersectionObserver(es => es.forEach(e => {
      inView = e.isIntersecting;
      syncCine();
    }), { threshold: 0 }).observe(sec);
  }

  /* ───── СТАРТ ───── */
  function start() {
    profile();
    applyTheme(doc.dataset.theme, false);
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
    if (logo && lv && videoCapable() && !D.videoData && !appleWebKit && lv.canPlayType('video/webm; codecs="vp9"')) afterLoad(() => {
      lv.addEventListener('playing', () => logo.classList.add('is-anim'), { once: true });
      lv.addEventListener('ended', () => logo.classList.remove('is-anim'), { once: true });   // останній кадр = статичний
      const syncLogo = () => {
        if (!videoAllowed() || heroP >= 1) { lv.pause(); return; }
        if (lv.ended) return;
        if (!lv.getAttribute('src')) lv.src = 'media/logo/plainbud-logo.webm';
        const pr = lv.play(); if (pr && pr.catch) pr.catch(() => {});
      };
      mediaSync.add(syncLogo); syncLogo();
    });
    if (videoCapable() && hVideo) afterLoad(() => {
      /* WebKit (Safari) відхиляє ранні play() з NotAllowedError навіть для muted-відео (виміряно 08.10: відмови до ~1.46 с,
         play() о 1.5 с проходить). Точну умову не встановлено ⇒ повтор із наростаючою паузою, до 8 спроб, лише поки герой у кадрі. */
      let tries = 0;
      const go = () => {
        if (!videoAllowed() || scrollY >= innerHeight) { hVideo.pause(); return; }
        if (!hVideo.paused) return;
        if (!attachVideo(hVideo, 'hero-wide', { tall: true })) return;
        hVideo.preload = 'auto';
        const pr = hVideo.play();
        if (pr && pr.catch) pr.catch(() => { if (++tries < 8) setTimeout(go, 200 * tries); });
      };
      mediaSync.add(go); go();
      hVideo.addEventListener('canplay', go, { once: true });
    });
    requestAnimationFrame(() => hero.classList.add('is-lit'));
    sparkWake();
    syncMotion();
    // Якість може змінитися незалежно від системного налаштування руху.
    new MutationObserver(syncMotion).observe(doc, {attributes: true, attributeFilter: ['data-quality']});
    document.addEventListener('visibilitychange', () => { if (document.hidden) $$('video').forEach(v => v.pause()); else syncMotion(); });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { measure(); render(); });
    addEventListener('load', () => { measure(); render(); });
    doc.classList.add('reveal-ready');
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
