(function () {
  'use strict';

  if (window.PBT_BUNDLE || !/^https?:$/.test(location.protocol)) return;

  const panel = /** @type {HTMLDialogElement} */ (document.querySelector('#supportPanel'));
  const title = /** @type {HTMLElement} */ (document.getElementById('supportTitle'));
  const form = /** @type {HTMLFormElement} */ (document.querySelector('#supportForm'));
  const message = /** @type {HTMLTextAreaElement} */ (document.querySelector('#supportMessage'));
  const send = /** @type {HTMLButtonElement} */ (document.querySelector('#supportSend'));
  const timeline = /** @type {HTMLElement} */ (document.getElementById('supportTimeline'));
  const body = /** @type {HTMLElement} */ (document.getElementById('supportBody'));
  const mode = /** @type {HTMLElement} */ (document.getElementById('supportMode'));
  const status = /** @type {HTMLElement} */ (document.getElementById('supportStatus'));
  const examples = /** @type {HTMLElement} */ (document.getElementById('supportExamples'));
  const clear = /** @type {HTMLButtonElement} */ (document.querySelector('#supportClear'));
  const file = /** @type {HTMLInputElement} */ (document.querySelector('#supportFile'));
  const fileZone = /** @type {HTMLElement} */ (document.getElementById('supportAttachments'));
  const fileName = /** @type {HTMLElement} */ (document.getElementById('supportFileName'));
  const removeFile = /** @type {HTMLButtonElement} */ (document.querySelector('#supportRemoveFile'));
  const consent = /** @type {HTMLInputElement} */ (document.querySelector('#supportConsent'));
  const consentGroup = /** @type {HTMLElement} */ (document.getElementById('supportConsentGroup'));
  const draft = /** @type {HTMLElement} */ (document.getElementById('supportDraft'));
  const draftType = /** @type {HTMLSelectElement} */ (document.querySelector('#supportDraftType'));
  const draftSubject = /** @type {HTMLInputElement} */ (document.querySelector('#supportDraftSubject'));
  const draftPlace = /** @type {HTMLInputElement} */ (document.querySelector('#supportDraftPlace'));
  const draftComment = /** @type {HTMLTextAreaElement} */ (document.querySelector('#supportDraftComment'));
  const apply = /** @type {HTMLButtonElement} */ (document.querySelector('#supportApply'));
  const human = /** @type {HTMLElement} */ (document.getElementById('supportHuman'));
  if (!panel?.showModal || !title || !form || !message || !send || !timeline || !body || !mode || !status || !examples ||
      !clear || !file || !fileZone || !fileName || !removeFile || !consent || !consentGroup || !draft || !draftType ||
      !draftSubject || !draftPlace || !draftComment || !apply || !human) return;

  const endpoint = '/api/support';
  const anchors = new Set(['#roboty', '#tekhnika', '#cina', '#materialy', '#geo', '#zapyt']);
  const types = new Set(['rent', 'material', 'transport', 'other']);
  const images = new Set(['image/jpeg', 'image/png', 'image/webp']);
  const audio = new Set(['audio/wav', 'audio/mpeg', 'audio/webm', 'audio/mp4', 'audio/ogg']);
  const fileAliases = new Map([['audio/x-wav', 'audio/wav'], ['audio/x-m4a', 'audio/mp4'],
    ['audio/mp3', 'audio/mpeg'], ['video/webm', 'audio/webm'], ['video/mp4', 'audio/mp4']]);
  const extTypes = new Map([['jpg', 'image/jpeg'], ['jpeg', 'image/jpeg'], ['png', 'image/png'], ['webp', 'image/webp'],
    ['wav', 'audio/wav'], ['mp3', 'audio/mpeg'], ['webm', 'audio/webm'], ['mp4', 'audio/mp4'], ['m4a', 'audio/mp4'],
    ['ogg', 'audio/ogg']]);
  const greeting = timeline.firstElementChild?.textContent?.trim() || '';
  /** @type {string[]} */
  let history = [];
  /** @type {AbortController|null} */
  let active = null;
  /** @type {HTMLElement|null} */
  let trigger = null;
  let ready = false;
  let loading = false;
  let modelEnabled = false;
  let leaving = false;
  let draftEdited = false;

  function setStatus(text) {
    status.textContent = text;
    status.hidden = !text;
  }

  function sync() {
    message.disabled = !ready;
    message.readOnly = !!active;
    send.disabled = !ready || !!active || (!message.value.trim() && !file.files?.length);
    clear.disabled = !!active;
    file.disabled = !!active;
    removeFile.disabled = !!active;
    consent.disabled = !!active;
    apply.disabled = !!active;
    form.setAttribute('aria-busy', String(!!active));
  }

  function discardFile() {
    file.value = '';
    fileName.textContent = '';
    fileName.hidden = true;
    removeFile.hidden = true;
  }

  /** @param {File} item */
  function attachmentKind(item) {
    const raw = item.type.toLowerCase();
    const extension = item.name.split('.').pop()?.toLowerCase() || '';
    const mime = fileAliases.get(raw) || raw || extTypes.get(extension) || '';
    if (!images.has(mime) && !audio.has(mime)) return '';
    if (item.size < 1 || item.size > (images.has(mime) ? 1 : 1.5) * 1024 * 1024) return '';
    return mime;
  }

  function entry(text, user, info = '') {
    const item = document.createElement('div');
    item.className = 'support__message ' + (user ? 'support__message--user' : 'support__message--agent');
    if (info) {
      const label = document.createElement('p');
      label.className = 'support__speaker';
      label.textContent = info;
      item.append(label);
    }
    const paragraph = document.createElement('p');
    paragraph.textContent = text;
    item.append(paragraph);
    timeline.append(item);
    return item;
  }

  function showSources(turn, sources) {
    if (!Array.isArray(sources)) return;
    const links = document.createElement('div');
    links.className = 'support__sources';
    const unique = new Set();
    for (const source of sources.slice(0, 6)) {
      const href = source?.href, label = source?.label;
      if (typeof href !== 'string' || !anchors.has(href) || unique.has(href) ||
          typeof label !== 'string' || !label.trim() || !document.getElementById(href.slice(1))) continue;
      const link = document.createElement('a');
      link.href = href;
      link.textContent = label.slice(0, 100);
      link.addEventListener('click', () => leave(href, false));
      links.append(link);
      unique.add(href);
    }
    if (unique.size) turn.append(links);
  }

  function showDraft(fields) {
    if (!fields || !types.has(fields.type) || draftEdited) return;
    const values = [fields.subject, fields.place, fields.comment];
    if (!values.every(value => typeof value === 'string') || !values.some(value => value.trim())) return;
    draftType.value = fields.type;
    for (const [control, value] of /** @type {[HTMLInputElement|HTMLTextAreaElement, string][]} */ ([
      [draftSubject, values[0]], [draftPlace, values[1]], [draftComment, values[2]],
    ])) {
      control.value = value.slice(0, control.maxLength);
    }
    draft.hidden = false;
  }

  function markDraftEdit() { draftEdited = true; }

  async function capabilities() {
    if (loading || ready) return;
    if (!navigator.onLine) {
      mode.textContent = 'Немає мережі. Можна скористатися контактами.';
      return;
    }
    loading = true;
    mode.textContent = 'Перевіряю доступність помічника…';
    try {
      const response = await fetch(endpoint, { credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(5000) });
      if (!response.ok) throw new Error('unavailable');
      const capability = await response.json();
      if (capability.available !== true || !['local', 'model'].includes(capability.mode)) throw new Error('unavailable');
      ready = true;
      modelEnabled = capability.mode === 'model' && capability.provider === 'OpenAI';
      fileZone.hidden = !(modelEnabled && capability.attachments === true);
      consentGroup.hidden = !modelEnabled;
      examples.hidden = history.length !== 0;
      mode.textContent = modelEnabled ? 'Без дозволу відповідь готується локально.' : 'Локальний режим · каталог і підготовка заявки.';
    } catch {
      mode.textContent = 'Помічник зараз недоступний. Скористайтеся контактами або формою заявки.';
    } finally {
      loading = false;
      sync();
      if (ready && panel.open && document.activeElement === title) message.focus();
    }
  }

  function leave(hash, draftTransfer) {
    leaving = true;
    panel.close();
    if (draftTransfer && location.hash !== hash) window.history.pushState(window.history.state, '', hash);
    // Focus follows the new context, not the original launcher.
    window.requestAnimationFrame(() => {
      const destination = document.getElementById(hash.slice(1));
      if (!destination) return;
      let focus = draftTransfer ? document.getElementById('subject') : destination;
      if (!focus) focus = destination;
      if (!focus.matches('input,textarea,select,a,button,[tabindex]')) focus.tabIndex = -1;
      focus.focus({ preventScroll: true });
      destination.scrollIntoView({ block: 'start' });
    });
  }

  function transferDraft() {
    const lead = /** @type {HTMLFormElement|null} */ (document.querySelector('#lead'));
    if (!lead || lead.hidden) {
      setStatus('Спочатку відкрийте нову заявку у формі сайту.');
      return;
    }
    if (/** @type {HTMLButtonElement|null} */ (lead.querySelector('#send'))?.disabled) {
      setStatus('Дочекайтеся відповіді на попередню заявку.');
      return;
    }
    if (![draftSubject, draftPlace, draftComment].some(field => field.value.trim())) {
      setStatus('Додайте хоча б одне поле до чернетки.');
      return;
    }
    const selectedType = /** @type {HTMLInputElement|null} */ (lead.querySelector('input[name="type"]:checked'));
    const selection = Array.from(lead.querySelectorAll('input[type="radio"][name="type"]'))
      .find(radio => radio instanceof HTMLInputElement && radio.value === draftType.value);
    const priorDetails = Array.from(lead.querySelectorAll('#subject,#place,#comment,#hours,#km,#date'))
      .some(field => (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) && field.value.trim());
    if (selection instanceof HTMLInputElement && selectedType !== selection) {
      if (priorDetails) {
        setStatus('У формі є чернетка іншого типу. Перевірте її перед перенесенням.');
        return;
      }
      selection.checked = true;
      selection.dispatchEvent(new Event('change', { bubbles: true }));
    }
    const fields = [['subject', draftSubject.value], ['place', draftPlace.value], ['comment', draftComment.value]];
    let transferred = false;
    for (const [id, value] of fields) {
      const field = lead.querySelector('#' + id);
      if ((field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) && !field.value.trim() && value.trim()) {
        field.value = value.trim();
        transferred = true;
        field.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }
    if (!transferred) {
      setStatus('У формі вже є ці дані або чернетка порожня. Наявні поля збережено.');
      return;
    }
    leave('#zapyt', true);
  }

  /** @param {File} item @returns {Promise<string>} */
  function readAttachment(item) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error('file'));
      reader.onabort = () => reject(new Error('file'));
      reader.onload = () => {
        const data = typeof reader.result === 'string' && reader.result.split(',', 2)[1];
        if (data) resolve(data);
        else reject(new Error('file'));
      };
      reader.readAsDataURL(item);
    });
  }

  function reset() {
    history = [];
    draftEdited = false;
    timeline.replaceChildren();
    entry(greeting, false);
    draft.hidden = true;
    draftSubject.value = '';
    draftPlace.value = '';
    draftComment.value = '';
    draftType.value = 'rent';
    message.value = '';
    clear.hidden = true;
    consent.checked = false;
    examples.hidden = !ready;
    discardFile();
    setStatus('');
    sync();
    body.scrollTop = 0;
    message.focus();
  }

  document.querySelectorAll('[data-support-open]').forEach(node => {
    if (!(node instanceof HTMLButtonElement)) return;
    node.hidden = false;
    node.addEventListener('click', () => {
      trigger = node;
      leaving = false;
      panel.showModal();
      if (ready) message.focus();
      else title.focus();
      void capabilities();
    });
  });
  panel.addEventListener('close', () => {
    active?.abort();
    if (!leaving) trigger?.focus();
  });
  human.addEventListener('click', () => leave('#zapyt', false));
  apply.addEventListener('click', transferDraft);
  clear.addEventListener('click', reset);
  [draftSubject, draftPlace, draftComment].forEach(control => control.addEventListener('input', markDraftEdit));
  draftType.addEventListener('change', markDraftEdit);

  examples.querySelectorAll('[data-support-prompt]').forEach(node => node.addEventListener('click', () => {
    if (!(node instanceof HTMLButtonElement) || active) return;
    message.value = node.dataset.supportPrompt || '';
    sync();
    message.focus();
  }));
  message.addEventListener('input', sync);
  message.addEventListener('keydown', event => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && !send.disabled) {
      event.preventDefault();
      form.requestSubmit(send);
    }
  });
  file.addEventListener('change', () => {
    const item = file.files?.[0];
    if (!item || !attachmentKind(item)) {
      discardFile();
      if (item) setStatus('Оберіть JPEG, PNG або WebP до 1 МіБ чи аудіо до 1,5 МіБ.');
    } else {
      setStatus('');
      fileName.textContent = item.name.slice(0, 120);
      fileName.hidden = false;
      removeFile.hidden = false;
    }
    sync();
  });
  removeFile.addEventListener('click', () => { discardFile(); setStatus(''); sync(); file.focus(); });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!ready || active) return;
    if (!navigator.onLine) { setStatus('Немає з’єднання. Ваш текст залишився в полі.'); return; }
    const item = file.files?.[0];
    const mime = item ? attachmentKind(item) : '';
    if (item && (!mime || fileZone.hidden)) {
      discardFile();
      setStatus('Цей файл зараз не можна додати.');
      sync();
      return;
    }
    const allowed = modelEnabled && consent.checked;
    if (item && !allowed) {
      setStatus('Щоб додати файл, дозвольте його передавання OpenAI або приберіть файл.');
      consent.focus();
      return;
    }
    const text = message.value.trim();
    if (!text && !item) return;
    const prompt = text || (images.has(mime) ? 'Погляньте на фото об’єкта.' : 'Розберіть моє аудіоповідомлення.');
    const submission = new AbortController();
    active = submission;
    sync();
    setStatus('Готую відповідь…');
    const deadline = setTimeout(() => submission.abort(), 45000);
    try {
      const attachment = item ? { mime, data: await readAttachment(item) } : undefined;
      const response = await fetch(endpoint, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: prompt, history, attachment, consent: allowed }),
        signal: submission.signal,
      });
      if (!response.ok) {
        if (response.status === 429) { setStatus('Забагато запитів. Спробуйте трохи пізніше.'); return; }
        throw new Error('unavailable');
      }
      const turn = await response.json();
      if (!turn.ok || typeof turn.reply !== 'string' || !turn.reply.trim()) throw new Error('invalid response');
      const transcript = typeof turn.transcript === 'string' ? turn.transcript.trim() : '';
      let context = prompt;
      if (transcript) {
        const spoken = Array.from(transcript);
        const written = Array.from(prompt);
        const writtenLimit = Math.min(written.length, Math.max(500, 999 - spoken.length));
        context = written.slice(0, writtenLimit).join('') + '\n' + spoken.slice(0, 999 - writtenLimit).join('');
      }
      history = [...history, context].slice(-6);
      entry(prompt, true, 'Ви');
      if (transcript) entry(Array.from(transcript).slice(0, 1000).join(''), true, 'Розшифрування аудіо');
      const itemReply = entry(turn.reply, false, turn.mode === 'model' ? 'Помічник · модель' : 'Помічник · локально');
      showSources(itemReply, turn.sources);
      if (turn.handoff === true) {
        const next = document.createElement('a');
        next.href = '#zapyt';
        next.textContent = 'До диспетчера';
        next.addEventListener('click', () => leave('#zapyt', false));
        itemReply.append(next);
      }
      showDraft(turn.draft);
      if (turn.draft && !draft.hidden) {
        const review = document.createElement('button');
        review.className = 'support__draft-review';
        review.type = 'button';
        review.textContent = 'Переглянути чернетку';
        review.addEventListener('click', () => {
          draftSubject.focus({ preventScroll: true });
          draft.scrollIntoView({ block: 'start' });
        });
        itemReply.append(review);
      }
      clear.hidden = false;
      examples.hidden = true;
      message.value = '';
      consent.checked = false;
      discardFile();
      setStatus('');
      if (panel.open) itemReply.scrollIntoView({ block: 'nearest' });
    } catch {
      setStatus(panel.open ? 'Відповідь не надійшла. Можна повторити або звернутися до диспетчера.' : '');
    } finally {
      clearTimeout(deadline);
      active = null;
      sync();
    }
  });

  sync();
})();
