/* ПБТ · ПолтаваБудТехніка — сцени, стани, інтерактив. Без залежностей; все — функція прогресу скролу.
   Контракт валідації заявки спільний із сервером: tests/contracts/lead_vectors.json (window.PBTv — чиста функція для тестів). */
(function () {
  'use strict';
  const D = window.PBT || {};
  const doc = document.documentElement;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const quality = () => doc.dataset.quality || 'full';
  const fmt = n => Math.round(n).toLocaleString('uk-UA');
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const seg = (p, a, b) => clamp((p - a) / (b - a), 0, 1);
  const ease = t => (t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
  const pad = n => String(n).padStart(3, '0');
  const mobileLayout = () => innerWidth < 1024;
  const phoneHuman = p => (p || '').replace(/^\+38(0\d{2})(\d{3})(\d{2})(\d{2})$/, '$1 $2 $3 $4');

  /* ───── профіль за можливостями (голова документа ставить ранній; тут — оновлення на resize) ───── */
  function profile() {
    const m = q => matchMedia(q).matches, w = innerWidth, h = innerHeight;
    const coarse = m('(pointer:coarse)') && !m('(any-pointer:fine)');
    doc.dataset.profile = (!coarse && w >= 1024 && w / h >= 1.05) ? 'wide-fine' : ((coarse && (w < 760 || h > w)) || w < 600) ? 'compact-touch' : 'medium-hybrid';
  }

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

  /* ───── ГЕРОЙ: поверхня → занурення ───── */
  const sHero = $('.s-hero'), hero = $('#hero'), word = $('#heroWord span'), win = $('#heroWin'), seqImg = $('#heroSeq'),
    copy = $('#heroCopy'), water = $('#heroWater'), bgImg = $('#heroBgImg'), canvas = $('#caustics');
  const FRAMES = D.heroFrames || Array.from({ length: 40 }, (_, k) => `media/hero/f_${pad(k + 1)}.webp`);
  const N = FRAMES.length, frames = new Array(N).fill(null);
  let cur = -1, wantIdx = 0, preloading = false;
  function preload() {
    if (preloading || quality() === 'static') return;
    preloading = true;
    let i = 0, active = 0;
    const next = () => {
      while (active < 3 && i < N) {
        const k = i++; const im = new Image(); active++;
        im.onload = im.onerror = () => { active--; frames[k] = im.naturalWidth ? im : false; if (k <= wantIdx) scrub(); next(); };
        im.src = FRAMES[k];
      }
    };
    next();
  }
  function scrub() {
    let k = wantIdx;
    while (k >= 0 && !frames[k]) k--;            /* найближчий декодований кадр не далі за бажаний — без порожнього кадру */
    if (k < 0 || k === cur) return;
    cur = k; seqImg.src = frames[k].src;
  }
  let heroTop = 0, heroTotal = 1;
  function heroRender(y) {
    const p = clamp((y - heroTop) / heroTotal, 0, 1);
    if (quality() !== 'static') {
      wantIdx = Math.round(seg(p, 0, .72) * (N - 1)); scrub();
      const wp = ease(seg(p, 0, .6));
      word.style.transform = `translate3d(0,${(-p * 16).toFixed(2)}vh,0) scale(${(1 - .34 * wp).toFixed(4)})`;
      word.style.opacity = (1 - seg(p, .22, .62)).toFixed(3);
      win.style.transform = mobileLayout() ? `scale(${(1 + .06 * p).toFixed(4)})` : `translate3d(0,-50%,0) translate3d(0,${(-p * 8).toFixed(2)}vh,0) scale(${(1 + .04 * p).toFixed(4)})`;
      win.style.opacity = (1 - seg(p, .72, .92)).toFixed(3);              /* вікно тоне разом із героєм — наприкінці лише вода */
      const cp = seg(p, .76, .96);
      copy.style.opacity = (1 - cp).toFixed(3); copy.style.transform = `translate3d(0,${(-cp * 24).toFixed(1)}px,0)`;
      water.style.setProperty('--wl', (seg(p, .5, .985) * 1.04).toFixed(4));
      if (bgImg) bgImg.style.opacity = (1 - .55 * seg(p, .3, .9)).toFixed(3);
    }
    return p;
  }

  /* каустика: світло на воді (лише повна якість, без reduced-motion, лише поки герой у кадрі) */
  let ctx = null, cW = 0, cH = 0, cLast = 0, heroP = 0;
  function causticsSize() {
    if (!canvas) return;
    const dpr = Math.min(devicePixelRatio || 1, 1.5);
    cW = canvas.clientWidth; cH = canvas.clientHeight;
    canvas.width = Math.round(cW * dpr); canvas.height = Math.round(cH * dpr);
    ctx = canvas.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  function caustics(t) {
    if (!ctx || quality() !== 'full' || reduced || mobileLayout() || heroP >= 1 || document.hidden) { requestAnimationFrame(caustics); return; }
    if (t - cLast < 40) { requestAnimationFrame(caustics); return; }        /* ≤25 к/с — це атмосфера, не сюжет */
    cLast = t;
    ctx.clearRect(0, 0, cW, cH);
    const s = t / 1000, lines = 11;
    ctx.lineWidth = 1.1;
    for (let i = 0; i < lines; i++) {
      const yBase = cH * (.18 + i / lines * .82), f = .0042 + i * .00035, ph = i * 1.7;
      ctx.beginPath();
      for (let x = 0; x <= cW; x += 10) {
        const y = yBase + Math.sin(x * f + s * .9 + ph) * 12 + Math.sin(x * f * 2.3 - s * 1.3 + ph) * 6;
        x ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }
      const a = .05 + .05 * (.5 + .5 * Math.sin(s * .7 + i));
      ctx.strokeStyle = `rgba(191,227,255,${a.toFixed(3)})`; ctx.stroke();
    }
    requestAnimationFrame(caustics);
  }

  /* ───── ГЛИБИНОМІР + активна секція ───── */
  const gauge = $('#gauge'), gFloat = $('.gauge__float'), gOut = $('.gauge__m'), gStops = $$('.gauge__stops a'), navLinks = $$('.nav__links a');
  const sections = $$('main section[id]');
  let docMax = 1, secTops = [];
  function measure() {
    heroTop = sHero.offsetTop; heroTotal = Math.max(1, sHero.offsetHeight - innerHeight);
    docMax = Math.max(1, doc.scrollHeight - innerHeight);
    secTops = sections.map(s => ({ id: s.id, top: s.offsetTop }));
    $$('.gauge__stops li').forEach((li, i) => { const s = secTops[i]; if (s) li.style.top = (clamp(s.top / docMax, 0, 1) * 100).toFixed(2) + '%'; });
    causticsSize();
  }
  function gaugeRender(y) {
    const p = clamp(y / docMax, 0, 1);
    gFloat.style.transform = `translate3d(0,${(p * gauge.clientHeight).toFixed(1)}px,0)`;
    gOut.value = (p === 0 ? '0,0' : '−' + (p * 6).toFixed(1).replace('.', ',')) + ' м';
    gauge.classList.toggle('is-on', y > 80);
    let active = secTops[0] ? secTops[0].id : '';
    for (const s of secTops) if (s.top <= y + innerHeight * .42) active = s.id;
    gStops.forEach(a => { const id = a.getAttribute('href').slice(1); a.classList.toggle('is-on', id === active); a.classList.toggle('is-past', secTops.findIndex(s => s.id === id) < secTops.findIndex(s => s.id === active)); });
    navLinks.forEach(a => a.classList.toggle('is-on', a.getAttribute('href') === '#' + active));
  }

  /* ───── РЕНДЕР: один контур на подію скролу ───── */
  let ticking = false;
  function render() {
    ticking = false;
    const y = scrollY;
    heroP = heroRender(y);
    gaugeRender(y);
    nav.classList.toggle('is-solid', y > 24);
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

  /* ───── ПАРК ───── */
  const catName = id => (D.cats.find(c => c.id === id) || {}).name || '';
  function renderPark() {
    const grid = $('#park'), chips = $('#chips');
    const counts = {};
    D.fleet.forEach(u => counts[u.cat] = (counts[u.cat] || 0) + 1);
    chips.innerHTML = [`<button class="chip" type="button" data-cat="all" aria-pressed="true">Уся техніка <span class="num">${D.fleet.length}</span></button>`]
      .concat(D.cats.map(c => `<button class="chip" type="button" data-cat="${c.id}" aria-pressed="false">${esc(c.name)} <span class="num">${counts[c.id] || 0}</span></button>`)).join('');
    grid.innerHTML = D.fleet.map(u => `
      <article class="unit" data-cat="${u.cat}" data-id="${u.id}">
        <figure><img src="${u.img}" alt="${esc(u.name)}" width="800" height="600" loading="lazy" decoding="async"><span class="unit__cat">${esc(catName(u.cat))}</span></figure>
        <div class="unit__body"><h3>${esc(u.name)}</h3>
          <dl class="unit__specs">${u.specs.map(s => `<div><dt>${esc(s.k)}</dt><dd>${esc(s.v)}</dd></div>`).join('')}</dl></div>
        <div class="unit__foot"><p class="unit__price${u.price ? '' : ' is-neg'}">${u.price ? `${fmt(u.price)} <small>грн/${esc(u.unit)}</small>` : 'договірна'}</p>
          <button class="btn btn--ghost btn--sm" type="button" data-req="rent" data-subject="${esc(u.name)}">У заявку</button></div>
      </article>`).join('');
    chips.addEventListener('click', e => {
      const b = e.target.closest('.chip'); if (!b) return;
      $$('.chip', chips).forEach(c => c.setAttribute('aria-pressed', String(c === b)));
      const cat = b.dataset.cat;
      $$('.unit', grid).forEach(u => u.hidden = !(cat === 'all' || u.dataset.cat === cat));
      measure();
    });
  }

  /* ───── КАЛЬКУЛЯТОР ЗМІНИ ───── */
  const weightOf = u => { const s = (u.specs.find(x => /Вага|Вантажопідйомність/.test(x.k)) || {}).v || ''; const m = s.match(/(\d+(?:[.,]\d+)?)\s*т/); return m ? parseFloat(m[1].replace(',', '.')) : null; };
  const trailerFor = u => { const w = weightOf(u); const t = D.trailers.find(t => (w == null ? 22 : w) <= t.maxT) || D.trailers[D.trailers.length - 1]; return t; };
  function renderCalc() {
    const sel = $('#cMachine'), hr = $('#cHours'), hrN = $('#cHoursN'), km = $('#cKm'), kmN = $('#cKmN');
    const priced = D.fleet.filter(u => u.price && u.unit === 'год');
    sel.innerHTML = priced.map(u => `<option value="${u.id}">${esc(u.name)} — ${fmt(u.price)} грн/год</option>`).join('');
    const sync = (a, b) => { a.addEventListener('input', () => { b.value = a.value; calc(); }); };
    sync(hr, hrN); sync(hrN, hr); sync(km, kmN); sync(kmN, km);
    sel.addEventListener('change', calc);
    function calc() {
      const u = priced.find(x => x.id === sel.value) || priced[0];
      const hours = clamp(parseInt(hrN.value, 10) || 0, 1, 5000), kmv = clamp(parseInt(kmN.value, 10) || 0, 0, 3000);
      const crane = u.cat === 'crane', tr = trailerFor(u);
      const rent = hours * u.price, deliv = crane ? 0 : kmv * tr.rate, total = rent + deliv;
      $('#cTotal').innerHTML = `${fmt(total)}<small>грн</small>`;
      $('#cLines').innerHTML = `<div><span>Оренда: ${hours} год × ${fmt(u.price)} грн</span><b>${fmt(rent)} грн</b></div>` +
        (crane ? `<div><span>Подача автокрана</span><b>уточнюється</b></div>` : `<div><span>Подача ${esc(tr.name).toLowerCase()}: ${kmv} км × ${tr.rate} грн</span><b>${fmt(deliv)} грн</b></div>`) +
        `<div><span>Разом, орієнтовно</span><b>${fmt(total)} грн</b></div>`;
      km.disabled = kmN.disabled = crane;
      $('#cOrder').dataset.subject = `${u.name} — ${hours} год${crane ? '' : `, подача ${kmv} км`}`;
      $('#cOut').dataset.total = String(total);
    }
    calc();
    window.PBTcalc = (id, hours, kmv) => { const u = priced.find(x => x.id === id); if (!u) return null; const crane = u.cat === 'crane'; return hours * u.price + (crane ? 0 : kmv * trailerFor(u).rate); };
  }

  /* ───── МАТЕРІАЛИ, ДОКАЗ, ГЕОГРАФІЯ ───── */
  function renderMats() {
    /* одна сітка на всі 8 позицій (4×2 на десктопі — без порожніх клітинок); група — підпис у плитці */
    $('#mats').innerHTML = `<div class="tiles">${D.materials.map(m => `
      <article class="tile"><img src="${m.img}" alt="${esc(m.name)}" width="639" height="396" loading="lazy" decoding="async">
        <div class="tile__body"><p class="tile__group">${esc(m.group)}</p><h4>${esc(m.name)}</h4><p class="tile__price">${fmt(m.price)}<small>грн/${esc(m.unit)}</small></p><p class="tile__doc">${esc(m.doc)}</p></div></article>`).join('')}</div>`;
  }
  function renderProof() {
    $('#reel').innerHTML = D.proof.map(p => `<a href="${p.url}" target="_blank" rel="noopener"><img src="${p.img}" alt="${esc(p.t)}: ${esc(p.s)}" width="576" height="324" loading="lazy" decoding="async"><i aria-hidden="true"></i><figcaption><b>${esc(p.t)}</b><span>${esc(p.s)}</span></figcaption></a>`).join('');
    $('#partners').innerHTML = D.partners.map((p, i) => `<li><img src="${p}" alt="Логотип партнера ${i + 1}" width="196" height="196" loading="lazy" decoding="async"></li>`).join('');
  }
  function renderGeo() {
    const home = 'Полтавська';
    $$('#geoMap .obl').forEach(p => { if (p.dataset.ua === home) p.classList.add('home'); });
    $('#geoList').innerHTML = D.regions.map(r => `<li class="${r === home ? 'home' : ''}"><b>${esc(r)} область</b><span>${r === home ? 'база · Полтава' : 'виїзд'}</span></li>`).join('');
    const hov = $('#geoHover');
    $('#geoMap').addEventListener('pointerover', e => { const p = e.target.closest('.obl'); if (!p) return; hov.textContent = p.dataset.ua ? `${p.dataset.ua} область — ${p.dataset.ua === home ? 'база' : 'працюємо'}` : `${p.dataset.name} — за запитом`; });
    $('#geoMap').addEventListener('pointerout', () => { hov.textContent = ''; });
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
      const d = new Date(+m[1], +m[2] - 1, +m[3]);                       /* локальна дата, без зсуву часового поясу */
      if (d.getFullYear() !== +m[1] || d.getMonth() !== +m[2] - 1 || d.getDate() !== +m[3]) return null;
      const today = new Date(); today.setHours(0, 0, 0, 0);
      return d >= today ? v : null;
    }
  };
  /* чиста функція для тестів: чи валідне значення поля в контексті типу запиту */
  window.PBTv = (field, value, type, method) => {
    if (field === 'contact') return V.contact(method || 'phone', value) !== null;
    if (field === 'hours') return V.int(value, 1, 5000) !== null;
    if (field === 'km') return V.int(value, 0, 3000) !== null;
    if (field === 'date') return V.date(value) !== null;
    if (field === 'subject') return !(['rent', 'material', 'transport'].includes(type) && (value || '').trim().length < 2);
    return true;
  };

  /* ───── ЗАЯВКА ───── */
  const MSG = { subject: { rent: 'Вкажи, яка техніка потрібна.', material: 'Вкажи матеріал і фракцію.', transport: 'Вкажи, що й куди перевезти.' },
    hours: 'Ціле число від 1 до 5000.', km: 'Ціле число від 0 до 3000.', date: 'Дата не раніше сьогодні.', contact: 'Перевір контакт: 0XX XXX XX XX або @нік у Telegram.', comment: 'Опиши задачу кількома словами.' };
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
    return [`Заявка · ${typeLabel[p.type] || p.type}`, p.subject && `Що: ${p.subject}`, p.hours && `Обсяг: ${p.hours}`, p.km && `Подача: ${p.km} км`, p.place && `Об'єкт: ${p.place}`,
      p.date && `Дата: ${p.date}`, p.name && `Ім'я: ${p.name}`, `Зв'язок: ${p.method} ${p.contact}`, p.comment && `Коментар: ${p.comment}`].filter(Boolean).join('\n');
  }
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const p = payload(); const err = validate(p);
    ['subject', 'hours', 'km', 'date', 'contact', 'comment'].forEach(k => setErr(k, err[k]));
    msg.classList.remove('is-on');
    if (Object.keys(err).length) { const first = form.querySelector('.is-err input, .is-err textarea'); if (first) first.focus(); return; }
    const h = JSON.stringify(p);
    if (h !== idemHash) { idemHash = h; idemKey = uuid(); }     /* один ключ на логічну відправку: повтор після обриву — та сама заявка */
    const btn = $('#send'); btn.disabled = true; btn.textContent = 'Надсилаю…';
    try {
      if (window.PBT_BUNDLE) throw new Error('bundle');
      const r = await fetch('/api/lead', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idemKey }, body: h });
      const j = await r.json().catch(() => ({}));
      if (r.status === 201 && j.ok) {
        form.hidden = true; done.classList.add('is-on'); $('#ref').textContent = j.ref; done.focus();
      } else if (r.status === 422 && j.fields) {
        Object.entries(j.fields).forEach(([k, v]) => setErr(k, v));
        msg.textContent = 'Перевір позначені поля.'; msg.classList.add('is-on');
      } else if (r.status === 429) { msg.textContent = j.message || 'Забагато запитів. Спробуй за 10 хвилин або зателефонуй.'; msg.classList.add('is-on'); }
      else { msg.textContent = 'Сервер не прийняв заявку. Спробуй ще раз або зателефонуй — номери поруч.'; msg.classList.add('is-on'); }
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

  /* кнопки «У заявку» / «Замовити» — тип + предмет у форму */
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-req]'); if (!b) return;
    const t = b.dataset.req, s = b.dataset.subject;
    const radio = form.querySelector(`input[name="type"][value="${t}"]`); if (radio) radio.checked = true;
    if (s) $('#subject').value = s;
    if (b.tagName === 'BUTTON') { e.preventDefault(); document.getElementById('zapyt').scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' }); }
    setTimeout(() => $('#subject').focus({ preventScroll: true }), 700);
  });

  /* ───── СТАРТ ───── */
  function start() {
    profile();
    renderPark(); renderCalc(); renderMats(); renderProof(); renderGeo(); loadBusiness();
    measure(); render();
    hero.classList.add('is-lit');
    if (quality() !== 'static') { preload(); requestAnimationFrame(caustics); }
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { measure(); render(); });
    addEventListener('load', () => { measure(); render(); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
