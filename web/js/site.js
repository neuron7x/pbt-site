/* ПЛЕЙНБУД — сцени, стани, інтерактив. Без залежностей; рух — функція прогресу скролу й видимості.
   Контракт валідації заявки спільний із сервером: tests/contracts/lead_vectors.json (window.PBTv — чиста функція для тестів). */
(function () {
  'use strict';
  const D = window.PBT || {};
  const doc = document.documentElement;
  /** Запити до статичної розмітки: незнайдений вузол — дефект розмітки, який ловлять браузерні тести.
   * @param {string} s @param {ParentNode} [r] @returns {any} */
  const $ = (s, r) => (r || document).querySelector(s);
  /** @param {string} s @param {ParentNode} [r] @returns {any[]} */
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const reduceQuery = matchMedia('(prefers-reduced-motion: reduce)');
  let reduced = reduceQuery.matches, manualPaused = false;
  const MOTION_KEY = 'pbt-motion-paused';
  try { manualPaused = localStorage.getItem(MOTION_KEY) === '1'; } catch { /* приватне сховище */ }
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
    try { localStorage.setItem(MOTION_KEY, manualPaused ? '1' : '0'); } catch { /* приватне сховище */ }
    syncMotion();
  });
  reduceQuery.addEventListener('change', event => { reduced = event.matches; syncMotion(); });
  // Відкладений play() не повинен обійти паузу або системне обмеження руху.
  document.addEventListener('play', event => {
    const media = /** @type {HTMLElement} */ (event.target);
    if (media instanceof HTMLVideoElement && !videoAllowed()) media.pause();
  }, true);
  const finePointer = matchMedia('(pointer:fine)').matches;
  const fmt = n => Math.round(n).toLocaleString('uk-UA');
  const { el, fill, attrOk } = window.PBTDom;          // web/js/dom.js
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
  /** @param {HTMLVideoElement} video @param {string} name @param {{ tall?: boolean }} [opt] */
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
      if (!v.poster && v.dataset.poster && attrOk('poster', v.dataset.poster)) v.poster = v.dataset.poster;
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
  const watchVideo = node => { if (vio) vio.observe(node); };

  /* ───── НАВІГАЦІЯ, МЕНЮ ───── */
  const nav = $('#nav'), burger = $('.burger'), menu = $('#menu'), menuClose = $('#menuClose');
  const menuBackdrop = [nav, $('#main'), $('.foot'), $('#gauge'), motionToggle, $('#dock'), $('.skip')].filter(Boolean);
  const menuInertBefore = new Map();
  let lastY = scrollY, navHidden = false, returnFocus = null;
  const themeButtons = $$('[data-theme-choice]');
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
    if (meta) meta.content = next === 'precision' ? '#101820' : '#040A16';
    const face = $('#themeFontPreload');
    if (face) face.href = 'fonts/' + (next === 'precision' ? 'IBMPlexSans-600-cyrillic.woff2' : 'Tektur-var-cyrillic.woff2');
    if (persist) {
      try { localStorage.setItem(THEME_KEY, next); } catch { /* приватний режим / заблоковане сховище */ }
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
    menuBackdrop.forEach(node => {
      if (on) { menuInertBefore.set(node, node.inert); node.inert = true; }
      else node.inert = menuInertBefore.get(node) || false;
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
    const focusable = Array.from(menu.querySelectorAll('button:not([disabled]), a[href]')).filter(node => node.getClientRects().length);
    if (!focusable.length) { e.preventDefault(); return; }
    if (e.shiftKey && document.activeElement === focusable[0]) {
      e.preventDefault(); focusable[focusable.length - 1].focus();
    } else if (!e.shiftKey && document.activeElement === focusable[focusable.length - 1]) {
      e.preventDefault(); focusable[0].focus();
    }
  });

  /* ───── ГЕРОЙ ───── */
  const sHero = $('.s-hero'), hero = $('#hero'), hVideo = $('#heroVideo'), hCenter = $('#heroCenter'), water = $('#heroWater'), spark = $('#spark');
  /* слова заголовка розмічено в HTML: перезапис DOM після JS створював новий кандидат LCP (simulate: render delay 4,7 с) */
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

  /* ───── СПОКІЙ ПЕРИФЕРІЇ (аудит п.50): декоративний цикл поза в'юпортом — на паузі (CSS [data-off]) ───── */
  if ('IntersectionObserver' in window) {
    const loopIO = new IntersectionObserver(es => es.forEach(e => e.target.toggleAttribute('data-off', !e.isIntersecting)));
    $$('.hero, .marquee, .wave, #geoMap').forEach(n => loopIO.observe(n));
  }

  /* ───── ГЛИБИНОМІР, АКТИВНА СЕКЦІЯ, ПРОГРЕС ───── */
  const gauge = $('#gauge'), gFloat = $('.gauge__float'), gOut = $('.gauge__m'), gStops = $$('.gauge__stops a'), navLinks = $$('.nav__links a');
  const sections = $$('main section[id]');
  let docMax = 1, secTops = [];
  function measure() {
    heroTop = sHero.offsetTop; heroTotal = Math.max(1, sHero.offsetHeight - innerHeight);
    docMax = Math.max(1, doc.scrollHeight - innerHeight);
    secTops = sections.map(s => ({ id: s.id, top: s.offsetTop }));
    /* зупинки глибиноміра — за id секції, не за індексом: секцій 9 (з «Масштабом»), зупинок 8 (аудит п.14) */
    $$('.gauge__stops li').forEach(li => { const id = li.firstElementChild.getAttribute('href').slice(1), s = secTops.find(x => x.id === id); if (s) li.style.top = (clamp(s.top / docMax, 0, 1) * 100).toFixed(2) + '%'; });
    trackStations();
    doc.style.setProperty('--nav-h', nav.offsetHeight + 'px');
    sparkSize();
  }
  /* ───── ГУСЕНИЦЯ: прогрес сторінки як гусеничний ланцюг; траки й зірочка котяться за скролом з інерцією ───── */
  const track = $('#track'), trackStops = $('#trackStops');
  const { PHYS, approach, texStep, oilAdvance } = window.PBTPhysics;   // web/js/physics.js
  /* beltPos — «маса» ланцюга, що наздоганяє сторінку; beltTx — фаза видимої текстури: росте насиченим кроком (п.47),
     тож траки й зуби зірочки (9 зубів × 16 px = 144 px/оберт) завжди котяться вперед, а на кидку змазуються */
  let beltPos = 0, beltRaf = 0, beltTx = 0, beltV = 0, beltT = 0, beltSmear = 0;
  function beltStep(now) {
    const target = scrollY, dt = beltT ? now - beltT : 16.7; beltT = now;
    const prev = beltPos;
    beltPos = !motion() || Math.abs(target - beltPos) < .5 ? target : approach(beltPos, target, dt, PHYS.beltTau);
    const { step, smear } = texStep((beltPos - prev) * PHYS.beltRatio);
    let sm = motion() ? smear : 0;
    beltTx = (beltTx + step) % 144;                                     // 144 = НСК кроку траків і оберту зірочки
    beltV = dt > 0 ? step / Math.min(dt, PHYS.dtMax) : 0;               // краплі їдуть з видимим ланцюгом, не зі справжнім
    track.style.setProperty('--tx', `${(-(beltTx % PHYS.pitch)).toFixed(2)}px`);
    track.style.setProperty('--rot', `${(beltTx / 144 * 360 % 360).toFixed(1)}deg`);   // зуби входять у проміжки траків
    if (beltPos === target) { beltRaf = 0; beltV = 0; beltT = 0; sm = 0; }   // ланцюг став — краплі більше не їдуть, змаз зник
    else beltRaf = requestAnimationFrame(beltStep);
    if (sm !== beltSmear && (sm === 0 || Math.abs(sm - beltSmear) > .005)) { beltSmear = sm; track.style.setProperty('--smear', sm.toFixed(3)); }
  }
  function trackRender(p) {
    if (!track) return;
    track.style.setProperty('--tp', p.toFixed(4));
    if (!beltRaf) beltRaf = requestAnimationFrame(beltStep);
    oilFeed(p);
  }
  /* масло: крапля набрякає під ланцюгом і їде разом із ним, тягне в'язку шийку, відривається й падає;
     чорне тіло, дзеркальний відблиск, райдужна плівка по краю. Лише поки ланцюг котиться; rAF спить без крапель. */
  const oil = $('#trackOil'), oilCtx = oil && oil.getContext ? oil.getContext('2d') : null, drops = [];
  let oilRaf = 0, oilLastY = scrollY, oilW = 0, oilH = 0, oilDpr = 1, oilAcc = 0;
  function oilSize() {
    if (!oilCtx) return;
    oilDpr = Math.min(2, devicePixelRatio || 1); oilW = oil.clientWidth; oilH = oil.clientHeight;
    oil.width = Math.round(oilW * oilDpr); oil.height = Math.round(oilH * oilDpr);
  }
  function oilFeed(p) {
    if (!oilCtx || !motion() || doc.dataset.theme === 'precision') { oilLastY = scrollY; return; }   // без примусового перерахунку стилів на кадр
    if (oil.clientWidth !== oilW) oilSize();                              // перший раз і після зміни ширини
    const v = scrollY - oilLastY; oilLastY = scrollY;
    oilAcc += Math.min(Math.abs(v), 160) / 130;                          // ≈ одна крапля на 130 px прокрутки
    while (oilAcc >= 1 && drops.length < 10) {
      oilAcc -= 1;
      drops.push({ x: p * oilW - 6 - Math.random() * 26, y: 0, r: 0, rMax: 2.8 + Math.random() * 1.6,
        phase: 0, t: 0, bead: 270 + Math.random() * 300, vy: 0, vx: 0, rem: 1, life: 0 });
    }
    if (oilAcc > 3) oilAcc = 0;
    if (!oilRaf && drops.length) { oilT = 0; oilRaf = requestAnimationFrame(oilStep); }
  }
  let oilT = 0;
  function oilBody(c, x, y, r, h) {
    c.beginPath(); c.moveTo(x, y - h);
    c.bezierCurveTo(x + r * .55, y - h * .45, x + r, y - r * .2, x + r, y + r * .15);
    c.bezierCurveTo(x + r, y + r * .85, x - r, y + r * .85, x - r, y + r * .15);
    c.bezierCurveTo(x - r, y - r * .2, x - r * .55, y - h * .45, x, y - h); c.closePath();
  }
  function oilStep(now) {
    const c = oilCtx, k = oilDpr, dt = oilT ? now - oilT : 16.7; oilT = now;
    c.setTransform(k, 0, 0, k, 0, 0); c.clearRect(0, 0, oilW, oilH);
    if (!motion()) { drops.length = 0; oilRaf = 0; return; }                 // пауза/reduced-motion посеред падіння — масло зникає одразу
    for (let i = drops.length - 1; i >= 0; i--) {
      const d = drops[i];
      if (!oilAdvance(d, dt, beltV)) { drops.splice(i, 1); continue; }
      const fade = d.phase === 2 ? Math.max(0, 1 - Math.max(0, d.y - oilH * .45) / (oilH * .55)) : 1;
      if (fade <= 0) { drops.splice(i, 1); continue; }
      const r = d.r, h = r * (1 + Math.min(1.6, (d.phase === 2 ? d.vy * 16.7 : 0) * .32)), x = d.x, y = d.y;
      c.globalAlpha = fade;
      if (d.phase === 1 || d.rem > 0) {                                  // в'язка шийка: звужується від ланцюга до краплі
        const top = 0, end = d.phase === 1 ? y - h : Math.min(y - h, top + 3 + (1 - d.rem) * 6), w = d.phase === 1 ? r * .55 : r * .4 * d.rem;
        c.fillStyle = '#0B0805';
        c.beginPath(); c.moveTo(x - w * 1.6, top); c.quadraticCurveTo(x - w * .35, (top + end) / 2, x - .35, end);
        c.lineTo(x + .35, end); c.quadraticCurveTo(x + w * .35, (top + end) / 2, x + w * 1.6, top); c.closePath(); c.fill();
      }
      if (d.phase === 2 || r > .4) {
        const g = c.createRadialGradient(x - r * .35, y - h * .3, r * .1, x, y, h * 1.05);
        g.addColorStop(0, '#4A3612'); g.addColorStop(.35, '#1A1206'); g.addColorStop(1, '#030201');
        c.fillStyle = g; oilBody(c, x, y, r, h); c.fill();
        const film = c.createLinearGradient(x - r, y - h, x + r, y + r);         // тонка плівка: фіолет → бірюза → золото
        film.addColorStop(0, 'rgba(140,90,255,.55)'); film.addColorStop(.5, 'rgba(40,210,190,.45)'); film.addColorStop(1, 'rgba(253,197,1,.6)');
        c.strokeStyle = film; c.lineWidth = .7; oilBody(c, x, y, r, h); c.stroke();
        c.fillStyle = 'rgba(255,255,255,.85)';                                   // дзеркальний відблиск
        c.beginPath(); c.ellipse(x - r * .38, y - h * .18, r * .2, r * .32, -.5, 0, Math.PI * 2); c.fill();
        c.fillStyle = 'rgba(253,197,1,.28)';                                    // теплий рефлекс знизу
        c.beginPath(); c.ellipse(x + r * .25, y + r * .45, r * .35, r * .14, 0, 0, Math.PI * 2); c.fill();
      }
    }
    c.globalAlpha = 1;
    oilRaf = drops.length ? requestAnimationFrame(oilStep) : (c.clearRect(0, 0, oilW, oilH), 0);
  }
  function trackStations() {
    if (!trackStops) return;
    const names = { roboty: 'Роботи', tekhnika: 'Техніка', cina: 'Ціна', materialy: 'Матеріали', dokaz: 'Кадри', geo: 'Де працюємо', zapyt: 'Заявка' };
    const list = secTops.filter(s => names[s.id]);
    trackStops.replaceChildren(...list.map((s, i) => {
      const li = document.createElement('li'), a = document.createElement('a');
      a.href = '#' + s.id; a.tabIndex = -1; a.dataset.n = String(i + 1).padStart(2, '0'); a.dataset.name = names[s.id];
      li.style.left = (clamp(s.top / docMax, 0, 1) * 100).toFixed(2) + '%'; li.append(a); return li;
    }));
  }
  let gaugeP = 0, liftTimer = 0;
  /* клік по вантажу: відчіпляється й падає туди, де стояв. Гак — декоративний <i>, тому слухаємо саме нижню частину (вантаж нижче 58 px). */
  gFloat.addEventListener('click', e => {
    if (!gauge.classList.contains('has-load') || e.offsetY < 58) return;
    gauge.classList.remove('has-load', 'is-lifting');
    const fall = (1 - gaugeP) * gauge.clientHeight;
    if (!motion() || fall < 4) { gauge.classList.add('is-splat'); return; }
    gauge.style.setProperty('--drop', (-fall).toFixed(1) + 'px');
    gauge.style.setProperty('--drop-t', (.25 + Math.sqrt(fall) / 40).toFixed(2) + 's');   // t ∝ √h, як у вільному падінні
    gauge.classList.add('is-falling');
  });
  gauge.addEventListener('animationend', e => {
    if (e.animationName !== 'load-drop') return;
    gauge.classList.remove('is-falling');
    gauge.classList.add('is-splat');
  });
  function gaugeRender(y) {
    const p = clamp(y / docMax, 0, 1);
    nav.style.setProperty('--sp', p.toFixed(4));
    trackRender(p);
    gFloat.style.transform = `translate3d(0,${(p * gauge.clientHeight).toFixed(1)}px,0)`;
    gOut.value = (p === 0 ? '0,0' : '−' + (p * 6).toFixed(1).replace('.', ',')) + ' м';
    gauge.classList.toggle('is-on', y > 80);
    if (p >= .985 && !gauge.classList.contains('is-falling')) {   // гак дійшов до низу — вантаж підчеплено й далі їде з гаком
      if (gauge.classList.contains('is-splat')) { gauge.classList.remove('is-splat'); gauge.classList.add('is-mush'); }   // після падіння гак бере вже грудку
      gauge.classList.add('has-load');
    }
    if (motion() && p < gaugeP - .0004 && gauge.classList.contains('has-load')) {   // підйом: вантаж махає й губить монети, поки гак іде вгору
      gauge.classList.add('is-lifting');
      clearTimeout(liftTimer);
      liftTimer = setTimeout(() => gauge.classList.remove('is-lifting'), 650);
    }
    gaugeP = p;
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
    if (track) track.classList.toggle('is-up', navHidden);   // після рішення про шапку: ланцюг іде за нею
    lastY = y;
  }
  const onScroll = () => { if (!ticking) { ticking = true; requestAnimationFrame(render); } };
  addEventListener('scroll', onScroll, { passive: true });
  let rT;
  addEventListener('resize', () => { clearTimeout(rT); rT = setTimeout(() => { if (!mobileLayout() && !menu.hidden) openMenu(false, false); profile(); measure(); render(); }, 120); });

  /* ───── ПОЯВА СЕКЦІЙ, ЛІЧИЛЬНИКИ, МАРШРУТИ ───── */
  const rio = 'IntersectionObserver' in window ? new IntersectionObserver(es => es.forEach(e => {
    if (!e.isIntersecting) return;
    const t = /** @type {HTMLElement} */ (e.target);
    t.classList.add('is-in'); if (rio) rio.unobserve(t);
    $$('[data-count]', e.target).forEach(countUp);
    if (t.dataset.count !== undefined) countUp(t);
  }), { threshold: 0, rootMargin: '20% 0px 20% 0px' }) : null;   // симетрична зона появи: стрибок до центру високої сітки не пропускає заголовок
  function reveal(root) {
    $$('.rv', root || document).forEach(node => { if (!rio || !motion()) node.classList.add('is-in'); else rio.observe(node); });
    $$('[data-count]', root || document).forEach(node => { if (node.closest('.rv')) return; if (!rio || !motion()) countUp(node); else rio.observe(node); });   /* лічильники поза .rv (герой) */
  }
  function countUp(node) {
    if (node.dataset.done) return; node.dataset.done = '1';
    const to = parseFloat(node.dataset.count), suf = node.dataset.suffix || '', dur = 1400, t0 = performance.now();
    if (!motion()) { node.textContent = fmt(to) + suf; return; }
    const step = t => { const k = motion() ? ease(clamp((t - t0) / dur, 0, 1)) : 1; node.textContent = fmt(to * k) + suf; if (k < 1) requestAnimationFrame(step); };
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
    const chip = (cat, name, n, on) => el('button', { class: 'chip', type: 'button', 'data-cat': cat, 'aria-pressed': String(on) }, name, ' ', el('span', { class: 'num' }, String(n)));
    fill(chips, chip('all', 'Уся техніка', D.fleet.length, true), D.cats.map(c => chip(c.id, c.name, counts[c.id] || 0, false)));
    fill(grid, D.fleet.map((u, i) => el('article', { class: 'unit rv rv--scale', style: { '--d': `${(i % 8) * 60}ms` }, 'data-cat': u.cat, 'data-id': u.id },
      el('figure', null,
        el('img', { src: u.img, alt: u.name, width: 800, height: 600, loading: 'lazy', decoding: 'async' }),
        el('span', { class: 'unit__bp', 'aria-hidden': 'true' }),
        el('span', { class: 'unit__cat' }, catName(u.cat)),
        el('button', { class: 'unit__pass', type: 'button', 'data-pass': u.id, 'aria-haspopup': 'dialog', 'aria-label': `Паспорт: ${u.name}` }, 'Паспорт')),
      el('div', { class: 'unit__body' }, el('h3', null, u.name),
        u.specs.length ? el('dl', { class: 'unit__specs' }, u.specs.map(sp => el('div', null, el('dt', null, sp.k), el('dd', null, sp.v))))
          : el('p', { class: 'unit__purpose' }, unitPurpose(u))),
      el('div', { class: 'unit__foot' },
        el('p', { class: u.price ? 'unit__price' : 'unit__price is-neg' }, u.price ? [`${fmt(u.price)} `, el('small', null, `грн/${u.unit}`)] : 'договірна'),
        el('button', { class: 'btn btn--sm', type: 'button', 'data-req': u.cat === 'trans' ? 'transport' : 'rent', 'data-subject': u.name }, 'У заявку')))));
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
    initBlueprints(grid);
    grid.addEventListener('pointerleave', e => { $$('.unit', grid).forEach(u => { u.style.removeProperty('--rx'); u.style.removeProperty('--ry'); }); }, true);
    grid.addEventListener('pointerout', e => { const u = e.target.closest('.unit'); if (u && !u.contains(e.relatedTarget)) { u.style.removeProperty('--rx'); u.style.removeProperty('--ry'); } });
  }

  /* ───── КРЕСЛЕННЯ І ПАСПОРТ МАШИНИ ───── */
  /* креслення — лише на намір (наведення на парк, «Паспорт»): поза критичним бюджетом байтів; у бандлі вже вбудовано */
  /* W3C Trusted Types: CSP require-trusted-types-for 'script' забороняє рядки в синках скриптів; єдиний дозволений URL —
     модуль креслень того ж походження. Браузер без Trusted Types отримує той самий рядок. */
  const ttPolicy = window.trustedTypes && window.trustedTypes.createPolicy
    ? window.trustedTypes.createPolicy('pbt', { createScriptURL: u => { if (u !== 'js/blueprint.js') throw new TypeError('script URL'); return u; } }) : null;
  let bpLoad = null;
  const loadBP = () => window.PBTBlueprint ? Promise.resolve(window.PBTBlueprint) : (bpLoad = bpLoad || new Promise((ok, fail) => {
    const s = document.createElement('script'); s.src = /** @type {any} */ (ttPolicy ? ttPolicy.createScriptURL('js/blueprint.js') : 'js/blueprint.js');
    s.onload = () => window.PBTBlueprint ? ok(window.PBTBlueprint) : fail(new Error('blueprint'));
    s.onerror = () => { bpLoad = null; s.remove(); fail(new Error('blueprint')); };
    document.head.appendChild(s);
  }));
  const unitById = id => D.fleet.find(x => x.id === id);
  /* штрихування заново при кожному наведенні: прибрати клас, змусити перерахунок, повернути */
  const replay = svg => { if (!motion()) return; svg.classList.remove('bp-anim'); void svg.getBoundingClientRect(); svg.classList.add('bp-anim'); };
  function initBlueprints(grid) {
    if (finePointer) grid.addEventListener('pointerover', e => {
      const fig = e.target.closest('.unit figure'); if (!fig || fig.contains(e.relatedTarget)) return;
      const host = $('.unit__bp', fig), card = fig.closest('.unit'); if (!host || !card) return;
      loadBP().then(BP => {
        if (!host.firstChild) { const u = unitById(card.dataset.id), r = u && BP.draw(u); if (!r) return; host.appendChild(r.svg); }
        if (fig.matches(':hover')) replay(host.firstChild);
      }, () => {});
    });
    grid.addEventListener('focusin', e => { if (e.target.closest('[data-pass]')) loadBP().catch(() => {}); });   // клавіатура: модуль їде, поки фокус на кнопці
    grid.addEventListener('click', e => { const b = e.target.closest('[data-pass]'); if (b) loadBP().then(BP => openPassport(BP, b.dataset.pass), () => { const r = b.closest('.unit').querySelector('[data-req]'); if (r) r.click(); }); });
  }
  const pass = $('#passport');
  function openPassport(BP, id) {
    const u = unitById(id); if (!u || !pass || pass.open || typeof pass.showModal !== 'function') return;
    const r = BP.draw(u, { angle: 38 }); if (!r) return;
    const n = D.fleet.indexOf(u) + 1, total = D.fleet.length;
    $('#passCode').textContent = `ПБ · ${u.id.toUpperCase()} · арк. ${String(n).padStart(2, '0')}/${total}`;
    $('#passTitle').textContent = u.name;
    $('#passCls').textContent = `${r.cls} · контур класу, масштаб умовний`;
    const draw = $('#passDraw'); draw.replaceChildren(r.svg);
    const reachBox = $('#passReach'), angle = $('#passAngle');
    reachBox.hidden = !(r.setAngle && r.boom);
    if (!reachBox.hidden) {
      const upd = () => {
        const a = angle.valueAsNumber, m = r.setAngle(a);
        $('#passAngleOut').textContent = `${a}°`;
        $('#passReachOut').textContent = m ? `Виліт ${m.r.toLocaleString('uk-UA')} м · оголовок на ${m.h.toLocaleString('uk-UA')} м вище п’яти стріли` : '';
      };
      angle.value = '38'; angle.oninput = upd; upd();
    }
    const rows = [['Найменування', u.name], ['Клас', r.cls]].concat((u.specs || []).map(x => [x.k, x.v]))
      .concat([['Ставка', u.price ? `${fmt(u.price)} грн/${u.unit}` : 'договірна'], ['Ставки станом на', D.priceDate.split('-').reverse().join('.')], ['Аркуш', `${n} з ${total}`], ['Виконавець', 'ПЛЕЙНБУД · Полтава']]);
    $('#passStamp').replaceChildren(...rows.map(([k, v]) => el('tr', null, el('th', { scope: 'row' }, k), el('td', null, v))));
    const req = $('#passReq'); req.dataset.req = u.cat === 'trans' ? 'transport' : 'rent'; req.dataset.subject = u.name;
    pass.showModal();
    replay(r.svg);
  }
  if (pass) {
    pass.addEventListener('click', e => {
      if (e.target === pass || e.target.closest('[data-pass-close]') || e.target.closest('[data-req]')) pass.close();
      else if (e.target.closest('#passPrint')) window.print();
    });
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
  function tweenTotal(out, to) {
    const from = totalShown, t0 = performance.now(), id = ++totalAnim;
    const show = v => fill(out, `${fmt(v)}\u00a0`, el('small', null, 'грн'));
    if (!motion()) { totalShown = to; show(to); return; }
    const step = t => { if (id !== totalAnim) return; const k = motion() ? ease(clamp((t - t0) / 520, 0, 1)) : 1; totalShown = from + (to - from) * k; show(totalShown); if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }
  function renderCalc() {
    const sel = $('#cMachine'), hr = $('#cHours'), hrN = $('#cHoursN'), km = $('#cKm'), kmN = $('#cKmN');
    // Hashed CSP forbids inline handlers; keyboard Enter must not submit this form.
    $('#calcForm').addEventListener('submit', event => event.preventDefault());
    const priced = D.fleet.filter(u => u.price && u.unit === 'год');
    fill(sel, priced.map(u => el('option', { value: u.id }, `${u.name} — ${fmt(u.price)} грн/год`)));
    sel.disabled = !priced.length;
    const paintRange = r => r.style.setProperty('--p', `${((r.value - r.min) / (r.max - r.min) * 100).toFixed(1)}%`);
    const sync = (a, b) => a.addEventListener('input', () => { b.value = a.value; paintRange(hr); paintRange(km); calc(); });
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
      const line = (label, value) => el('div', null, el('span', null, label), el('b', null, value));
      const deliveryLine = crane ? line('Подача автокрана', 'уточнюється')
        : !needsTrailer ? line('Подача тралом', 'не заявлена')
          : tr ? line(`Подача тралом ${tr.name.replace(/^Трал\s*/, '')}: ${kmv} км × ${tr.rate} грн`, `${fmt(deliv)} грн`)
            : line('Подача тралом: маса невідома або поза діапазоном', 'уточнюється');
      fill($('#cLines'), line(`Оренда: ${hours} год × ${fmt(u.price)} грн`, `${fmt(rent)} грн`), deliveryLine,
        line(transportKnown ? 'Разом, орієнтовно' : 'Оренда без подачі', `${fmt(total)} грн`));
      $('#cOrder').dataset.subject = `${u.name} — ${hours} год${crane ? '' : `, подача ${kmv} км${transportKnown ? '' : ' (ціну уточнити)'}`}`;
      $('#cOrder').dataset.calcHours = String(hours);
      $('#cOrder').dataset.calcKm = crane ? '' : String(kmv);
      $('#cOut').dataset.total = transportKnown ? String(total) : '';
      $('#cOut').dataset.estimate = transportKnown ? 'with-delivery' : 'rent-only';
    }
    paintRange(hr); paintRange(km); calc(); $('#calcUnavailable').hidden = true;
    window.PBTcalc = (id, hours, kmv) => {
      const u = priced.find(x => x.id === id);
      return quoteModel.legacyTotal(u, D.trailers, hours, kmv);
    };
  }

  /* ───── МАТЕРІАЛИ, ДОКАЗ, ГЕОГРАФІЯ ───── */
  const x2 = src => /^media\/.+\.webp$/.test(src) ? `${src} 1x, ${src.replace(/\.webp$/, '@2x.webp')} 2x` : null;   // data:URI однофайлової збірки — без srcset
  function renderMats() {
    fill($('#mats'), el('div', { class: 'tiles' }, D.materials.map((m, i) => el('article', { class: 'tile rv', style: { '--d': `${(i % 4) * 80}ms` } },
      el('figure', null, el('img', { src: m.img, srcset: x2(m.img), alt: m.name, width: 639, height: 396, loading: 'lazy', decoding: 'async' }), el('span', { class: 'tile__group' }, m.group)),
      el('div', { class: 'tile__body' }, el('h3', null, m.name), el('p', { class: 'tile__price' }, `${fmt(m.price)}\u00a0`, el('small', null, `грн/${m.unit}`)),
        el('p', { class: 'tile__doc' }, m.doc), el('button', { class: 'btn btn--sm tile__order', type: 'button', 'data-req': 'material', 'data-subject': m.name }, 'У заявку'))))));
  }
  function renderProof() {
    const standalone = window.PBT_BUNDLE && !D.mp4Only;
    fill($('#reel'), D.proof.map((p, i) => el(standalone ? 'article' : 'a', {
      class: 'proof-card rv', style: { '--d': `${(i % 3) * 90}ms` },
      href: standalone ? null : (proofUrl(p.url) || '#roboty'), target: standalone ? null : '_blank', rel: standalone ? null : 'noopener',
      'aria-label': `${p.t}: ${p.s}${standalone ? '' : ' — відкрити відео'}` },
    el('figure', null, el('img', { src: p.poster, alt: '', width: 640, height: 360, loading: 'lazy', decoding: 'async' }),
      el('video', { 'data-video': p.video, 'data-poster': p.poster, 'aria-hidden': 'true', tabindex: '-1' }),
      standalone ? null : el('i', { 'aria-hidden': 'true' }),
      el('figcaption', null, el('b', null, p.t), el('span', null, p.s))))));
    $$('#reel .proof-card').forEach(watchVideo);
    const logos = duplicate => D.partners.map((p, i) => el('li', { 'aria-hidden': duplicate ? 'true' : null },
      el('img', { src: p, alt: duplicate ? '' : `Логотип в ілюстративній добірці ${i + 1}`, width: 196, height: 196, loading: 'lazy', decoding: 'async' })));
    fill($('#partners'), logos(false), logos(true));      /* декоративний повтор не дублює доступний список */
  }
  /* назви областей поза зоною виїзду — українською (у SVG-джерелі вони англійською, аудит п.41) */
  const OBL_UA = { 'Autonomous Republic of Crimea': 'Автономна Республіка Крим', 'Sevastopol': 'Севастополь', 'Chernivtsi Oblast': 'Чернівецька область',
    'Donetsk Oblast': 'Донецька область', 'Ivano-Frankivsk Oblast': 'Івано-Франківська область', 'Kherson Oblast': 'Херсонська область',
    'Khmelnytskyi Oblast': 'Хмельницька область', 'Luhansk Oblast': 'Луганська область', 'Lviv Oblast': 'Львівська область',
    'Mykolaiv Oblast': 'Миколаївська область', 'Odessa Oblast': 'Одеська область', 'Rivne Oblast': 'Рівненська область', 'Sumy Oblast': 'Сумська область',
    'Ternopil Oblast': 'Тернопільська область', 'Vinnytsia Oblast': 'Вінницька область', 'Volyn Oblast': 'Волинська область', 'Zakarpattia Oblast': 'Закарпатська область' };
  function renderGeo() {
    const home = 'Полтавська', svg = $('#geoMap svg');
    const list = $('#geoList');
    const R = (D.routes && D.routes.to) || {};
    fill(list, D.regions.map((r, i) => el('li', { class: r === home ? 'rv home' : 'rv', style: { '--d': `${i * 50}ms` } },
      el('button', { class: 'geo__pick', type: 'button', 'data-ua': r, 'aria-pressed': 'false', 'aria-controls': 'geoInfo' },
        el('b', null, `${r} область`), el('span', null, r === home ? 'база · Полтава' : R[r] ? `${fmt(R[r].km)} км` : 'виїзд')))));
    if (!svg) return;
    $('#geoMap').classList.add('rv');
    const hov = $('#geoHover');
    svg.addEventListener('pointerover', e => { const p = e.target.closest('.obl'); if (!p) return; hov.textContent = p.dataset.ua ? `${p.dataset.ua} область — ${p.dataset.ua === home ? 'база' : 'працюємо'}` : `${OBL_UA[p.dataset.name] || 'Регіон'} — за запитом`; });
    svg.addEventListener('pointerout', () => { hov.textContent = ''; });
    initRoutes(svg, list, home);
    /* Контури — дані (media/map/oblasts.json, tools/geo_map.py), не 30 КБ gzip у критичному HTML. Вантажаться, коли секція
       за ~1,5 екрана, будуються createElementNS без розбору розмітки; центри пораховано заздалегідь — без getBBox посеред
       прокрутки (A/B 09.10: ривок 344 мс на CPU ×4). Збірка без сервера несе ті самі дані в D.geoMap. */
    const NS = 'http://www.w3.org/2000/svg';
    const qlen = (x0, y0, x1, y1, qx, y2) => { let L = 0, px = x0, py = y0; for (let k = 1; k <= 24; k++) { const t = k / 24, u = 1 - t, x = u * u * x0 + 2 * u * t * x1 + t * t * qx, y = u * u * y0 + 2 * u * t * y1 + t * t * y2; L += Math.hypot(x - px, y - py); px = x; py = y; } return L; };
    function mount(map) {
      if (!map || !Array.isArray(map.regions) || svg.querySelector('.obl')) return;
      const shapes = document.createDocumentFragment();
      for (const r of map.regions) {
        const p = document.createElementNS(NS, 'path');
        p.setAttribute('class', r.served ? 'obl served' : 'obl'); p.setAttribute('d', r.d);
        p.dataset.name = r.name; p.dataset.ua = r.ua;
        if (r.ua === home) p.classList.add('home');
        shapes.appendChild(p);
      }
      svg.appendChild(shapes);
      const homeR = map.regions.find(r => r.ua === home); if (!homeR) return;
      const [hx, hy] = homeR.c;
      const served = map.regions.filter(r => r.served && r.ua && r.ua !== home && r.name !== 'Kyiv');
      const g = document.createElementNS(NS, 'g'); g.setAttribute('class', 'routes');
      served.forEach((r, i) => {
        const [x, y] = r.c, mx = (hx + x) / 2, my = (hy + y) / 2 - Math.abs(x - hx) * .18 - 14;
        const path = document.createElementNS(NS, 'path');
        path.setAttribute('d', `M${hx.toFixed(1)},${hy.toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${x.toFixed(1)},${y.toFixed(1)}`);
        path.setAttribute('class', 'route'); path.dataset.ua = r.ua;
        path.style.setProperty('--len', qlen(hx, hy, mx, my, x, y).toFixed(1)); path.style.setProperty('--d', `${.2 + i * .12}s`);
        g.appendChild(path);
      });
      const ring = document.createElementNS(NS, 'circle'); ring.setAttribute('class', 'beacon-ring'); ring.setAttribute('cx', String(hx)); ring.setAttribute('cy', String(hy)); ring.setAttribute('r', '9');
      const dot = document.createElementNS(NS, 'circle'); dot.setAttribute('class', 'beacon'); dot.setAttribute('cx', String(hx)); dot.setAttribute('cy', String(hy)); dot.setAttribute('r', '6');
      g.append(ring, dot); svg.appendChild(g);
      svg.dataset.ready = '1';
      svg.dispatchEvent(new Event('mapready'));             // вибір, зроблений до приходу контурів, застосовується до них
    }
    const load = () => D.geoMap ? mount(D.geoMap)
      : fetch('media/map/oblasts.json', { credentials: 'same-origin' }).then(r => (r.ok ? r.json() : null)).then(mount, () => { /* без карти лишається список областей */ });
    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); load(); } }, { rootMargin: '150% 0px' });
      io.observe($('#geoMap'));
    } else load();
  }

  /* ───── МАРШРУТИ: область → відстань дорогою → ціна подачі тралом → калькулятор ───── */
  function initRoutes(svg, list, home) {
    const info = $('#geoInfo'), R = D.routes && D.routes.to; if (!info || !R) return;
    const geo = info.closest('.geo');
    function pick(ua) {
      const r = R[ua], isHome = ua === home;
      $$('.geo__pick', list).forEach(b => b.setAttribute('aria-pressed', String(b.dataset.ua === ua)));
      $$('.route', svg).forEach(p => p.classList.toggle('is-sel', p.dataset.ua === ua));
      $$('.obl', svg).forEach(p => p.classList.toggle('is-sel', p.dataset.ua === ua));
      geo.classList.toggle('has-sel', !!r);
      const kids = [];
      if (isHome) {
        kids.push(el('p', { class: 'geo__leg' }, 'Полтава · база'), el('p', { class: 'geo__km' }, 'від 0 км'),
          el('p', { class: 'geo__cost' }, 'Подача по області — за фактичним кілометражем від бази.'));
      } else if (r) {
        const t = (D.trailers || []).filter(x => Number.isSafeInteger(x.rate) && x.rate > 0).sort((a, b) => a.maxT - b.maxT);
        kids.push(el('p', { class: 'geo__leg' }, `${D.routes.from} → ${r.city}`),
          el('p', { class: 'geo__km' }, [el('b', null, fmt(r.km)), ' км дорогою']),
          el('dl', { class: 'geo__cost' }, t.map(x => el('div', null, [el('dt', null, `${x.name}, ${fmt(x.rate)} грн/км`), el('dd', null, `≈ ${fmt(x.rate * r.km)} грн`)]))),
          el('button', { class: 'btn btn--sm geo__calc', type: 'button', 'data-km': String(r.km) }, `Підставити ${r.km} км у калькулятор`));
      }
      kids.push(el('p', { class: 'geo__src' }, `Відстань: ${D.routes.source}, ${D.routes.date.split('-').reverse().join('.')}. Ставки тралу — станом на ${D.priceDate.split('-').reverse().join('.')}.`));
      info.replaceChildren(...kids);
      info.hidden = false;
    }
    list.addEventListener('click', e => { const b = e.target.closest('.geo__pick'); if (b) pick(b.dataset.ua); });
    svg.addEventListener('mapready', () => { const b = $('.geo__pick[aria-pressed="true"]', list); if (b) pick(b.dataset.ua); });
    svg.addEventListener('click', e => { const p = e.target.closest('.obl'); if (p && p.dataset.ua && (R[p.dataset.ua] || p.dataset.ua === home)) pick(p.dataset.ua); });
    info.addEventListener('click', e => {
      const b = e.target.closest('.geo__calc'); if (!b) return;
      const n = $('#cKmN'), cin = $('#cina'); if (!n || !cin) return;
      n.value = b.dataset.km; n.dispatchEvent(new Event('input', { bubbles: true }));
      cin.scrollIntoView({ behavior: motion() ? 'smooth' : 'auto', block: 'start' });
      (n.disabled ? $('#cMachine') : n).focus({ preventScroll: true });   // автокран їде своїм ходом: подача не тралом — обрати іншу техніку
    });
  }

  /* External links from configuration: https only, parsed by the platform, not by a prefix check. */
  function httpsUrl(value) {
    try { const u = new URL(String(value)); return u.protocol === 'https:' && !/["'<>\s]/.test(String(value)) ? u.href : null; } catch { return null; }
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
    const phoneHref = tel(c.phone);
    $$('[data-phone]').forEach(a => { a.textContent = phoneHuman(c.phone) || 'Телефон уточнюється'; if (a.tagName === 'A') a.href = phoneHref; });
    $$('[data-phone-action]').forEach(a => {
      a.hidden = !c.phone;
      if (c.phone) a.href = phoneHref;
      else a.removeAttribute('href');
    });
    /* другий телефон не наданий — у розмітці <span>-заготовка: <a> без href псувало crawlable-anchors */
    $$('[data-phone2]').forEach(node => {
      const present = !!c.phone2, row = node.closest('[data-phone2-row]') || node;
      row.hidden = !present; node.textContent = phoneHuman(c.phone2) || '';
      if (!present) return;
      let a = node;
      if (node.tagName !== 'A') { a = document.createElement('a'); a.className = node.className; a.dataset.phone2 = ''; a.textContent = node.textContent; node.replaceWith(a); }
      a.href = tel(c.phone2);
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
    if (c.phone) ch.push({ k: 'Телефон', v: phoneHuman(c.phone), href: phoneHref });
    if (c.phone2) ch.push({ k: 'Телефон', v: phoneHuman(c.phone2), href: tel(c.phone2) });
    if (c.viber) ch.push({ k: 'Viber', v: phoneHuman(c.viber), href: `viber://chat?number=${encodeURIComponent(c.viber)}` });
    if (c.telegram) ch.push({ k: 'Telegram', v: c.telegram, href: `https://t.me/${encodeURIComponent(String(c.telegram).replace('@', ''))}` });
    if (email) ch.push({ k: 'Електронна пошта', v: email, href: `mailto:${email}` });
    fill($('#channels'), ch.length ? ch.map(x => el('a', { href: x.href }, el('span', null, x.k), el('b', null, x.v)))
      : el('div', null, el('b', null, 'Канали зв’язку'), el('span', null, 'уточнюються')));
    const soc = [['tiktok', 'TikTok'], ['instagram', 'Instagram'], ['facebook', 'Facebook'], ['youtube', 'YouTube']].filter(([k]) => httpsUrl(c[k]));
    $$('[data-social]').forEach(ul => { ul.hidden = !soc.length; fill(ul, soc.map(([k, n]) => el('li', null, el('a', { href: httpsUrl(c[k]), target: '_blank', rel: 'noopener' }, n)))); });
  }
  function loadBusiness() {
    const fb = () => applyBusiness(D.business || {});
    fb();
    if (window.PBT_BUNDLE || location.protocol === 'file:') return;
    fetch('/api/config', { cache: 'no-store' }).then(r => r.ok ? r.json() : Promise.reject()).then(j => applyBusiness(Object.keys(j).length ? j : D.business)).catch(fb);
  }

  /* ───── ВАЛІДАЦІЯ ЗАЯВКИ: той самий контракт, що й сервер ───── */
  const kyivToday = () => {
    /** @type {Intl.DateTimeFormatOptions} */
    const opts = { year: 'numeric', month: '2-digit', day: '2-digit', calendar: 'iso8601', numberingSystem: 'latn' };
    // Locale fallback can reorder date fields; compare only explicitly assembled ISO dates.
    const iso = formatter => {
      const parts = Object.fromEntries(formatter.formatToParts(new Date()).map(part => [part.type, part.value]));
      return `${parts.year}-${parts.month}-${parts.day}`;
    };
    // Browsers with tzdata older than 2022b know only the old zone name; a RangeError here would silently block the form.
    for (const timeZone of ['Europe/Kyiv', 'Europe/Kiev']) {
      try { return iso(new Intl.DateTimeFormat('en-CA', { ...opts, timeZone })); } catch { /* next name */ }
    }
    return iso(new Intl.DateTimeFormat('en-CA', opts));
  };
  const V = {
    contact(method, s) {
      s = (s || '').trim(); if (!s) return null;
      if (method === 'telegram' && s.startsWith('@')) return /^@[A-Za-z0-9_]{5,32}$/.test(s) ? s : null;
      let d = s.replace(/[\s()-]/g, '');
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
  const offlineLead = !!window.PBT_BUNDLE || location.protocol === 'file:';
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
    try { const r = JSON.parse(sessionStorage.getItem(PENDING) || 'null'); return r && typeof r.k === 'string' && typeof r.d === 'string' && r.x > Date.now() ? r : null; } catch { return null; }
  };
  const pendingWrite = r => { try { sessionStorage.setItem(PENDING, JSON.stringify(r)); } catch { /* blocked storage: in-memory idempotency only */ } };
  const pendingClear = () => { try { sessionStorage.removeItem(PENDING); } catch { /* nothing was stored */ } };
  async function leadDigest(key, body) {
    try {
      const raw = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`${key}\n${body}`));
      return Array.from(new Uint8Array(raw), b => b.toString(16).padStart(2, '0')).join('');
    } catch { return null; }   // crypto.subtle needs a secure context; plain HTTP degrades to in-memory.
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
  function showLeadFallback(p) {
    form.hidden = true;
    fallback.classList.add('is-on');
    $('#fbText').textContent = humanText(p);
    fallback.focus();
  }
  form.addEventListener('submit', async e => {
    e.preventDefault();
    if ($('#send').disabled) return;
    const p = payload(); const err = validate(p);
    ['subject', 'hours', 'km', 'date', 'contact', 'comment'].forEach(k => setErr(k, err[k]));
    msg.classList.remove('is-on');
    if (Object.keys(err).length) { const first = form.querySelector('.is-err input, .is-err textarea'); if (first) first.focus(); return; }
    if (offlineLead) {
      showLeadFallback(p);
      return;
    }
    const h = JSON.stringify(p);
    const btn = $('#send'); btn.disabled = true; btn.textContent = 'Надсилаю…';
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 15000);
    try {
      await bindIdempotencyKey(h);
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
    } catch {
      showLeadFallback(p);
    } finally { clearTimeout(deadline); btn.disabled = false; btn.textContent = 'Надіслати заявку'; }
  });
  if (offlineLead) {
    $('#requestLeadDescription').textContent = 'Підготуйте текст заявки та повідомте деталі диспетчеру.';
    $('#requestDeliveryNote').textContent = 'Автономна версія готує текст заявки на вашому пристрої.';
    $('#send').textContent = 'Підготувати заявку';
    $('#fallbackStatus').textContent = 'Заявку не надіслано';
    $('#fallbackTitle').textContent = 'Текст заявки готовий';
    $('#fallbackDetail').textContent = 'Скопіюйте текст або зателефонуйте диспетчеру.';
  }
  $('#send').disabled = false;
  $('#formUnavailable').hidden = true;
  $('#fbCopy').addEventListener('click', async () => {
    const t = $('#fbText').textContent; const b = $('#fbCopy');
    try { await navigator.clipboard.writeText(t); b.textContent = 'Скопійовано'; } catch { const r = document.createRange(); r.selectNodeContents($('#fbText')); const s = getSelection(); if (s) { s.removeAllRanges(); s.addRange(r); } b.textContent = 'Виділено — скопіюй'; }
    setTimeout(() => b.textContent = 'Скопіювати текст', 2500);
  });
  $('#again').addEventListener('click', () => { done.classList.remove('is-on'); form.hidden = false; form.reset(); idemHash = ''; pendingClear(); $('#subject').focus(); });
  $('#fbRetry')?.addEventListener('click', () => {
    fallback.classList.remove('is-on'); form.hidden = false;
    if (!offlineLead) {
      msg.textContent = 'Підтвердження не отримано. Можна повторити надсилання: незмінена заявка не дублюється.';
      msg.classList.add('is-on');
    }
    $('#send').focus();
  });

  document.addEventListener('click', e => {
    const b = /** @type {HTMLElement} */ (e.target).closest('[data-req]'); if (!(b instanceof HTMLElement)) return;
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
    fill(list, chs.map((c, i) => el('li', { class: 'cine__ch', id: `cine-${c.id}`, 'data-i': i },
      el('figure', null, el('img', { src: cposter(c.id), alt: `${c.word}: ${c.line}`, width: 1920, height: 1080, loading: 'lazy', decoding: 'async' })),
      el('p', { class: 'cine__n num' }, `${String(i + 1).padStart(2, '0')} / ${total}`),
      el('h3', { class: 'cine__w' }, c.word),
      el('p', { class: 'cine__l' }, c.line))));
    /* атрибуція CC BY / BY-SA — одним списком у підвалі, не поверх кадрів (ліцензія дозволяє «будь-яким розумним способом») */
    const cr = $('#cineCredits');
    const ext = (href, text) => el('a', { href: httpsUrl(href), target: '_blank', rel: 'noopener' }, text);
    if (cr) fill(cr, el('details', { class: 'credits' }, el('summary', null, 'Джерела ілюстративних кадрів «Масштабу»'),
      el('ul', null, chs.map(c => el('li', null, ext(c.credit.page, `«${c.credit.title}»`), `, ${c.credit.author} · `,
        ext(c.credit.license_url, c.credit.license), ' · Wikimedia Commons; кадровано, виконано колірну корекцію')))));
    if (!videoCapable() || D.cinePosters || !('IntersectionObserver' in window)) return;   /* однофайловий бандл: лише постери */
    sec.classList.add('is-pinned');
    fill(rail, chs.map(c => el('a', { href: `#cine-${c.id}` }, el('span', null, c.word))));
    const layers = $$('.cine__v', sec), items = $$('.cine__ch', list), railDots = $$('a', rail);
    let cur = -1, front = 0, inView = false;
    const prof = () => (mobileLayout() && innerHeight > innerWidth ? 'm' : 'w');
    /* Кліпи «Масштабу» у WebM — VP9 Profile 1 (4:4:4): майже ніде не декодується апаратно. W3C Media Capabilities:
       на дотику WebM лише якщо декодування енергоефективне, інакше апаратний H.264 того самого кадру; на ПК — як і досі,
       якщо плавно. canPlayType('vp9') без профілю відповідав «так» і на телефонах, що потім декодували 4:4:4 програмно. */
    const CINE_WEBM = 'video/webm; codecs="vp09.01.41.08"', webmPick = {};
    function webmFor(p) {
      if (webmPick[p]) return webmPick[p];
      const can = !D.mp4Only && !!document.createElement('video').canPlayType(CINE_WEBM);
      const size = p === 'm' ? { width: 720, height: 1280 } : { width: 1920, height: 1080 };
      return (webmPick[p] = !can ? Promise.resolve(false)
        : !(navigator.mediaCapabilities && navigator.mediaCapabilities.decodingInfo) ? Promise.resolve(finePointer)
        : navigator.mediaCapabilities.decodingInfo({ type: 'file', video: { contentType: CINE_WEBM, ...size, bitrate: 4e6, framerate: 30 } })
          .then(i => !!(i.supported && i.smooth && (finePointer || i.powerEfficient)), () => finePointer));
    }
    function load(v, id) {
      const p = prof(), n = id + '-' + p;
      if (v.dataset.clip === n) return;
      v.dataset.clip = n; v.removeAttribute('src'); v.replaceChildren();
      v.poster = C_BASE + n + '.webp';
      webmFor(p).then(webm => {
        if (v.dataset.clip !== n) return;                                  // кадр уже змінився, поки браузер відповідав
        v.replaceChildren();
        if (webm) { const a = document.createElement('source'); a.src = C_BASE + n + '.webm'; a.type = CINE_WEBM; v.append(a); }
        const b = document.createElement('source'); b.src = C_BASE + n + '.mp4'; b.type = 'video/mp4'; v.append(b);
        v.dataset.codec = webm ? 'vp9-444' : 'h264';
        v.load();
        // play() з show() міг прийти раніше за джерела (рішення асинхронне) — відтворення відновлюється тут
        if (v.classList.contains('is-on') && inView && videoAllowed()) { const pr = v.play(); if (pr && pr.catch) pr.catch(() => {}); }
      });
    }
    function show(i) {
      if (i === cur) return;
      cur = i;
      items.forEach((node, k) => node.classList.toggle('is-cur', k === i));
      railDots.forEach((node, k) => node.classList.toggle('is-on', k === i));
      const next = layers[1 - front], prev = layers[front];
      next.poster = C_BASE + chs[i].id + '-' + prof() + '.webp';
      if (videoAllowed()) load(next, chs[i].id);
      else {
        // Новий розділ у паузі показує власний постер, а не кадр попереднього кліпу.
        next.removeAttribute('src'); next.replaceChildren(); delete next.dataset.clip; next.load();
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
    const cio = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) show(Number(/** @type {HTMLElement} */ (e.target).dataset.i)); }), { rootMargin: '-45% 0px -45% 0px' });
    items.forEach(node => cio.observe(node));
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
