/* Hilal AI — واجهة Gemini-style عربية */
(() => {
  'use strict';

  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  // رابط ثابت يُستخدم داخل حزمة APK (Capacitor) حيث لا يكون origin هو الخادم
  // رابط نفق Cloudflare عالمي (HTTPS) — يعمل من أي هاتف في العالم.
  // يمكن تغييره من نافذة الإعدادات داخل التطبيق أو بإعادة بناء APK.
  const DEFAULT_API_URL = 'https://lounge-scholar-dream-powell.trycloudflare.com';

  function isNativeApp() {
    const cap = window.Capacitor;
    const origin = window.location;
    return !!(
      (cap && typeof cap.isNativePlatform === 'function' && cap.isNativePlatform()) ||
      origin.protocol === 'capacitor:' ||
      origin.protocol === 'ionic:' ||
      (origin.protocol === 'https:' && origin.hostname === 'localhost') ||
      (origin.protocol === 'http:' && origin.hostname === 'localhost' && origin.port !== '8000')
    );
  }

  function detectDefaultApi() {
    if (isNativeApp()) return DEFAULT_API_URL;
    const origin = window.location.origin;
    return origin && origin !== 'null' ? origin : DEFAULT_API_URL;
  }

  const BROWSER_API_URL = detectDefaultApi();
  let apiBase = localStorage.getItem('hilal_api_base') || BROWSER_API_URL;
  let token = localStorage.getItem('hilal_token') || '';
  let user = JSON.parse(localStorage.getItem('hilal_user') || 'null');
  let mode = 'chat';
  let selectedPkg = 'starter';
  let attached = null; // {name, data}
  let history = JSON.parse(localStorage.getItem('hilal_history') || '[]');
  let busy = false;
  let adTicket = null;       // تذكرة الإعلان الحالية
  let adTimer = null;        // مؤقّت العدّ التنازلي
  let adStartedAt = 0;       // وقت بدء المشاهدة محلياً
  let adInfo = { reward: 0.5, watch_seconds: 25, admob_rewarded_id: '', web_ad_link: '' };

  const MODE_INFO = {
    study: { icon: '🎓', hint: 'مساعد الدراسة مجاني 100% بلا حدود · يشرح ويُلخّص ويحلّ المسائل ويصنع الاختبارات', cost: 0 },
    chat:  { icon: '💬', hint: '30 رسالة مجانية يومياً · الاشتراك يفتح محادثة غير محدودة', cost: 0 },
    studio:{ icon: '🎨', hint: 'تصميم البراندات والإعلانات أو تعديل الصور · 0.5 نقطة للعملية', cost: 0.5 },
    image: { icon: '🖼️', hint: 'توليد صورة أو تغيير الملابس مع الحفاظ على الوجه · نقطة واحدة', cost: 1 },
    audio: { icon: '🎙️', hint: 'صوت عميق + مؤثرات ffmpeg · نقطة واحدة', cost: 1 },
    video: { icon: '🎬', hint: 'فيديو ناطق بتحريك الشفاه · نقطتان + علامة مائية للمجانيين', cost: 2 },
  };

  /* ---------------- helpers ---------------- */
  function syncExtension() {
    if (window.chrome && chrome.storage && chrome.storage.sync) {
      chrome.storage.sync.set({ apiBase, token });
    }
  }

  function toast(msg) {
    const el = $('#toast');
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('show'), 3200);
  }
  // يستخدمه support.js لعرض رسالة نسخ البريد داخل الواجهة نفسها
  window.hilalToast = toast;

  function openModal(id) { $('#' + id).classList.add('open'); }
  function closeModal(id) { $('#' + id).classList.remove('open'); }

  async function api(path, opts = {}) {
    // دائماً يوجد رابط افتراضي صالح، لذلك لا تظهر أي رسالة خطأ عند غياب الإعداد
    if (!apiBase) apiBase = BROWSER_API_URL;
    const base = apiBase.replace(/\/$/, '');
    opts.headers = opts.headers || {};
    opts.headers['Content-Type'] = 'application/json';
    if (token) opts.headers['Authorization'] = 'Bearer ' + token;
    let res;
    try { res = await fetch(base + path, opts); }
    catch (e) { toast('تعذّر الاتصال بالخادم'); throw e; }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || ('HTTP ' + res.status));
    return data;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function scrollBottom() {
    const c = $('#content'); c.scrollTop = c.scrollHeight;
  }

  function addMsg(role, html, raw = '') {
    $('#hero').style.display = 'none';
    const wrap = document.createElement('div');
    wrap.className = 'msg ' + role;
    wrap.innerHTML =
      `<div class="avatar">${role === 'user' ? '🧑' : MODE_INFO[mode].icon}</div>` +
      `<div class="bubble">${html}</div>`;
    $('#thread').appendChild(wrap);
    scrollBottom();
    return wrap;
  }

  function renderPoints() {
    $('#pointsBadge').textContent = '🌱 ' + (user ? user.points + ' نقطة' : '2 نقطة');
    $('#authBtn').textContent = user ? (user.email.split('@')[0] + ' ✓') : 'تسجيل الدخول';
    $('#inviteLink').textContent = user
      ? (apiBase || location.origin) + '/?invite=' + user.invite_code
      : 'سجّل الدخول أولاً';
    renderChatUsage();
  }

  // عدّاد المحادثة المجانية: يتجدد كل 24 ساعة، والمشتركون لا حدود لهم
  function renderChatUsage() {
    const el = $('#chatUsage');
    if (!el) return;
    if (mode !== 'chat' || !user) { el.textContent = ''; el.style.display = 'none'; return; }
    if (user.chat_unlimited || user.has_paid) {
      el.textContent = '✨ محادثة غير محدودة مع الاشتراك';
      el.style.display = 'block';
      return;
    }
    const limit = user.chat_limit || 30;
    const remaining = user.chat_remaining === undefined || user.chat_remaining === null
      ? limit : user.chat_remaining;
    const reset = user.chat_reset_at
      ? new Date(user.chat_reset_at * 1000).toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' })
      : '';
    el.textContent = `المتبقي اليوم: ${remaining} / ${limit} رسالة مجانية` + (reset ? ` · يتجدد الساعة ${reset}` : '');
    el.style.display = 'block';
  }

  function renderHistory() {
    const box = $('#historyList');
    if (!history.length) { box.innerHTML = '<p class="muted">لا توجد محادثات بعد</p>'; return; }
    box.innerHTML = history.slice(-12).reverse().map((h, i) =>
      `<div class="hist-item" data-i="${history.length - 1 - i}">` +
      `<span>${escapeHtml(h.title || 'محادثة')}</span><button data-del="${history.length - 1 - i}">✕</button></div>`
    ).join('');
  }

  function setMode(next) {
    mode = next;
    $$('.tab,.side-item').forEach(b => b.classList.toggle('active', b.dataset.mode === next));
    $('#hint').textContent = MODE_INFO[next].hint;
    const input = $('#promptInput');
    input.placeholder = {
      study: 'اسأل مساعد الدراسة: اشرح، لخّص، حل مسألة، أو اصنع اختباراً...',
      chat: 'اسأل Hilal AI أي شيء...',
      studio: 'صف التصميم أو ارفق صورة واكتب أمر التعديل (تجميل، إضاءة، سينمائي...)',
      image: 'صف الصورة التي تريدها، أو ارفق صورتك وصورة الملابس...',
      audio: 'اكتب النص الذي تريد تحويله لصوت عميق...',
      video: 'اكتب ما يقوله الشخص في الفيديو الناطق...',
    }[next];
    renderExtraInputs();
    renderChatUsage();
  }

  function renderExtraInputs() {
    const box = $('#extraInputs');
    box.innerHTML = '';
    if (mode === 'studio') {
      box.innerHTML =
        `<label class="upload-chip">صورة للتعديل والتجميل (اختياري)<input type="file" id="studioFile" accept="image/*"></label>`;
      $('#studioFile').onchange = e => readFile(e.target.files[0], 'photo');
    } else if (mode === 'image') {
      box.innerHTML =
        `<label class="upload-chip">صورتك (للحفاظ على الوجه)<input type="file" id="personFile" accept="image/*"></label>` +
        `<label class="upload-chip">صورة الملابس/الخلفية<input type="file" id="styleFile" accept="image/*"></label>`;
      $('#personFile').onchange = e => readFile(e.target.files[0], 'person');
      $('#styleFile').onchange = e => readFile(e.target.files[0], 'style');
    } else if (mode === 'video') {
      box.innerHTML =
        `<label class="upload-chip">صورة الوجه<input type="file" id="faceFile" accept="image/*"></label>` +
        `<label class="upload-chip">صوت جاهز (اختياري)<input type="file" id="audioFile" accept="audio/*"></label>`;
      $('#faceFile').onchange = e => readFile(e.target.files[0], 'face');
      $('#audioFile').onchange = e => readFile(e.target.files[0], 'audio');
    }
  }

  function readFile(file, key) {
    if (!file) return;
    const r = new FileReader();
    r.onload = () => {
      attached = attached || {};
      attached[key] = r.result;
      toast('تم إرفاق: ' + file.name);
    };
    r.readAsDataURL(file);
  }

  /* ---------------- get / refresh ---------------- */
  async function refreshMe() {
    if (!token) return;
    try {
      const me = await api('/api/me');
      user = me;
      localStorage.setItem('hilal_user', JSON.stringify(user));
      renderPoints();
      fetchPackages();
    } catch (e) {
      if (/الجلسة|401/.test(e.message)) {
        token = ''; user = null;
        localStorage.removeItem('hilal_token'); localStorage.removeItem('hilal_user');
        renderPoints();
      }
    }
  }

  async function fetchPackages() {
    try {
      const d = await api('/api/packages');
      $('#walletAddress').textContent = d.wallet_address || 'لم يُضبط بعد';
      $('#packageCards').innerHTML = Object.entries(d.packages).map(([id, p]) =>
        `<div class="pkg ${id === selectedPkg ? 'selected' : ''}" data-pkg="${id}">` +
        `<strong>${p.name}</strong><div class="price">${p.price_usdt} USDT</div>` +
        `<small>${p.points} نقطة</small></div>`).join('');
      $('#packageSelect').innerHTML = Object.entries(d.packages).map(([id, p]) =>
        `<option value="${id}">${p.name} — ${p.price_usdt} USDT</option>`).join('');
      $$('.pkg').forEach(el => el.onclick = () => {
        selectedPkg = el.dataset.pkg;
        $('#packageSelect').value = selectedPkg;
        $$('.pkg').forEach(x => x.classList.toggle('selected', x === el));
      });
    } catch (e) { /* يعرض لاحقاً عند فتح النافذة */ }
  }

  /* ---------------- Rewarded Ads ---------------- */
  // AdMob عبر الكاباسيتور (إن وُجد)، وإلا رابط إعلان ويب مباشر
  function getAdMob() {
    const cap = window.Capacitor;
    if (!cap || typeof cap.isNativePlatform !== 'function' || !cap.isNativePlatform()) return null;
    if (cap.Plugins && cap.Plugins.AdMob) return cap.Plugins.AdMob;
    if (window.plugins && window.plugins.AdMob) return window.plugins.AdMob;
    return null;
  }

  async function fetchAdStatus() {
    if (!token) { $('#adsRemaining').textContent = '—'; return; }
    try {
      const s = await api('/api/ads/status');
      $('#adsRemaining').textContent = s.ads_remaining;
      adInfo.reward = s.reward;
      adInfo.watch_seconds = s.watch_seconds;
      $('#watchAdBtn').disabled = s.ads_remaining <= 0;
      if (s.ads_remaining <= 0) $('#adHint').textContent = 'استهلكت إعلانات اليوم، عد غداً 🌙';
    } catch (e) { /* تجاهل */ }
  }

  function updateAdCountdown() {
    if (!adTicket) return;
    const elapsed = Math.floor((Date.now() - adStartedAt) / 1000);
    const need = adInfo.watch_seconds;
    const left = Math.max(0, need - elapsed);
    const cd = $('#adCountdown');
    const hint = $('#adWaitHint');
    const btn = $('#claimAdBtn');
    if (cd) cd.textContent = left;
    if (hint) hint.textContent = left > 0
      ? `تبقّى ${left} ثانية قبل تفعيل المكافأة`
      : 'يمكنك استلام مكافأتك الآن ✅';
    if (btn) btn.disabled = left > 0;
    if (left === 0 && adTimer) { clearInterval(adTimer); adTimer = null; }
  }

  async function watchAd() {
    if (!token) { openModal('authModal'); toast('سجّل الدخول أولاً'); return; }
    const btn = $('#watchAdBtn');
    btn.disabled = true;
    try {
      const s = await api('/api/ads/start', { method: 'POST' });
      adTicket = s.ticket;
      adInfo.watch_seconds = s.watch_seconds;
      adInfo.reward = s.reward;
      adInfo.admob_rewarded_id = s.admob_rewarded_id;
      adInfo.web_ad_link = s.web_ad_link;
      adStartedAt = Date.now();

      // افتح الإعلان: AdMob أصلياً، أو رابط الويب في تبويب جديد
      const admob = getAdMob();
      if (admob && s.admob_rewarded_id) {
        try {
          await admob.prepareRewardVideoAd({ adId: s.admob_rewarded_id });
          await admob.showRewardVideoAd({ adId: s.admob_rewarded_id });
        } catch (e) {
          toast('تعذّر عرض إعلان AdMob، افتح رابط الويب');
          if (s.web_ad_link) window.open(s.web_ad_link, '_blank', 'noopener');
        }
      } else if (s.web_ad_link) {
        $('#adLink').href = s.web_ad_link;
        window.open(s.web_ad_link, '_blank', 'noopener');
      }

      $('#adCountdown').textContent = s.watch_seconds;
      $('#adWaitHint').textContent = `تبقّى ${s.watch_seconds} ثانية قبل تفعيل المكافأة`;
      $('#claimAdBtn').disabled = true;
      openModal('adModal');
      if (adTimer) clearInterval(adTimer);
      adTimer = setInterval(updateAdCountdown, 1000);
      updateAdCountdown();
    } catch (e) {
      toast(e.message);
      btn.disabled = false;
      fetchAdStatus();
    }
  }

  async function claimAd() {
    if (!adTicket) return;
    const btn = $('#claimAdBtn');
    btn.disabled = true; btn.textContent = 'جارٍ الاستلام...';
    try {
      const d = await api('/api/ads/claim', {
        method: 'POST', body: JSON.stringify({ ticket: adTicket }),
      });
      if (user) { user.points = d.balance; localStorage.setItem('hilal_user', JSON.stringify(user)); renderPoints(); }
      $('#adsRemaining').textContent = d.ads_remaining;
      toast(`تمت إضافة ${d.points_added} نقطة 🎉`);
      adTicket = null;
      if (adTimer) { clearInterval(adTimer); adTimer = null; }
      closeModal('adModal');
      $('#watchAdBtn').disabled = d.ads_remaining <= 0;
    } catch (e) {
      toast(e.message);
      btn.disabled = false;
    } finally {
      btn.textContent = 'استلم 0.5 نقطة';
    }
  }

  /* ---------------- send ---------------- */
  async function send() {
    if (busy) return;
    const text = $('#promptInput').value.trim();
    if (!text && !attached) { toast('اكتب رسالة أو أرفق ملفاً'); return; }
    if (!token) { openModal('authModal'); toast('سجّل الدخول أولاً للحصول على 2 نقطة مجانية'); return; }

    const title = (text || 'ملف مرفق').slice(0, 34);
    addMsg('user', escapeHtml(text || '📎 ملف مرفق'));
    $('#promptInput').value = '';
    attached = attached || {};
    const files = { ...attached };
    attached = null;
    renderExtraInputs();

    const wait = addMsg('ai', '<span class="loading"><i></i><i></i><i></i></span>');
    busy = true; $('#sendBtn').disabled = true;
    try {
      let out;
      if (mode === 'study') {
        out = await api('/api/ai/study', { method: 'POST', body: JSON.stringify({ prompt: text }) });
        wait.querySelector('.bubble').textContent = out.reply;
      } else if (mode === 'chat') {
        out = await api('/api/ai/chat', { method: 'POST', body: JSON.stringify({ prompt: text }) });
        wait.querySelector('.bubble').textContent = out.reply;
        if (out.chat) Object.assign(user, out.chat);
      } else if (mode === 'studio') {
        const payload = { prompt: text, mode: files.photo ? 'edit' : 'design' };
        if (files.photo) payload.image = files.photo;
        out = await api('/api/ai/studio', { method: 'POST', body: JSON.stringify(payload) });
        wait.querySelector('.bubble').innerHTML =
          `<div>${payload.mode === 'edit' ? 'تم تعديل الصورة وتحسينها 🎨' : 'تم إنشاء التصميم 🎨'}</div>` +
          `<a href="${apiBase + out.url}" target="_blank"><img src="${apiBase + out.url}" alt="studio design"></a>` +
          `<div class="caption-block"><p class="caption-text">${escapeHtml(out.caption || '')}</p>` +
          `<button type="button" class="copy" data-copy-caption>نسخ النص الإعلاني</button></div>`;
      } else if (mode === 'image') {
        if (!text && !files.style) throw new Error('اكتب وصف الصورة');
        const payload = { prompt: text, mode: files.person || files.style ? 'tryon' : 'text' };
        if (files.person) payload.image = files.person;
        if (files.style) payload.style = files.style;
        out = await api('/api/ai/image', { method: 'POST', body: JSON.stringify(payload) });
        wait.querySelector('.bubble').innerHTML = `تم توليد الصورة 🖼️<a href="${apiBase + out.url}" target="_blank"><img src="${apiBase + out.url}" alt="generated"></a>`;
      } else if (mode === 'audio') {
        out = await api('/api/ai/audio', { method: 'POST', body: JSON.stringify({ text }) });
        wait.querySelector('.bubble').innerHTML = `تم توليد الصوت 🎙️<audio controls src="${apiBase + out.url}"></audio>`;
      } else if (mode === 'video') {
        if (!files.face) throw new Error('يرجى إرفاق صورة الوجه');
        if (!text && !files.audio) throw new Error('اكتب النص أو أرفق صوتاً');
        const payload = { image: files.face, text: text || undefined, audio: files.audio };
        out = await api('/api/ai/video', { method: 'POST', body: JSON.stringify(payload) });
        wait.querySelector('.bubble').innerHTML = `الفيديو الناطق جاهز 🎬<video controls src="${apiBase + out.url}"></video>`;
      }
      if (out && out.points_left !== undefined) {
        user.points = out.points_left;
        localStorage.setItem('hilal_user', JSON.stringify(user));
        renderPoints();
      }
      history.push({ title, mode, at: Date.now() });
      localStorage.setItem('hilal_history', JSON.stringify(history));
      renderHistory();
    } catch (e) {
      wait.querySelector('.bubble').textContent = '⚠️ ' + e.message;
      if (/نقاطك غير كافية|الرسالة المجانية|اشترك/.test(e.message)) {
        openModal('rechargeModal');
        refreshMe();
      }
    } finally {
      busy = false; $('#sendBtn').disabled = false;
    }
  }

  /* ---------------- events ---------------- */
  document.addEventListener('click', e => {
    const t = e.target.closest('[data-close]');
    if (t) closeModal(t.dataset.close);
    const c = e.target.closest('[data-copy]');
    if (c) {
      const txt = $('#' + c.dataset.copy).textContent;
      (window.hilalCopyText
        ? window.hilalCopyText(txt)
        : navigator.clipboard.writeText(txt)
      ).then(() => toast('تم النسخ ✓')).catch(() => toast('تعذّر النسخ، حاول مرة أخرى'));
    }
    const cp = e.target.closest('[data-copy-caption]');
    if (cp) {
      const txt = cp.closest('.caption-block').querySelector('.caption-text').textContent;
      (window.hilalCopyText
        ? window.hilalCopyText(txt)
        : navigator.clipboard.writeText(txt)
      ).then(() => toast('تم نسخ النص الإعلاني ✓')).catch(() => toast('تعذّر النسخ، حاول مرة أخرى'));
    }
  });

  $$('.tab,.side-item').forEach(b => b.addEventListener('click', () => {
    setMode(b.dataset.mode);
    $('#sidebar').classList.remove('open');
  }));

  $('#menuBtn').onclick = () => $('#sidebar').classList.toggle('open');
  $('#newChatBtn').onclick = () => { $('#thread').innerHTML = ''; $('#hero').style.display = 'block'; };
  $('#templates').addEventListener('click', e => {
    const b = e.target.closest('.template'); if (!b) return;
    if (b.dataset.mode) setMode(b.dataset.mode);
    $('#promptInput').value = b.dataset.prompt;
    $('#promptInput').focus();
  });
  $('#quickTemplates').addEventListener('click', e => {
    const b = e.target.closest('.qt'); if (!b) return;
    if (b.dataset.mode) setMode(b.dataset.mode);
    $('#promptInput').value = b.dataset.prompt;
    $('#promptInput').focus();
    toast('جاهز! اضغط إرسال أو أرفق الصورة المطلوبة');
  });
  $('#sendBtn').onclick = send;
  $('#promptInput').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
  $('#promptInput').addEventListener('input', e => {
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px';
  });
  $('#attachBtn').onclick = () => $('#fileInput').click();
  $('#fileInput').onchange = e => readFile(
    e.target.files[0],
    mode === 'video' ? 'face' : mode === 'studio' ? 'photo' : 'person'
  );

  $('#rechargeBtn').onclick = () => { fetchPackages(); fetchAdStatus(); openModal('rechargeModal'); };
  $('#watchAdBtn').onclick = watchAd;
  $('#claimAdBtn').onclick = claimAd;
  $('#closeAdModal').onclick = () => {
    closeModal('adModal');
    if (adTimer) { clearInterval(adTimer); adTimer = null; }
    // التذكرة تبقى صالحة؛ يمكن استلامها لاحقاً من نفس النافذة عبر زر المشاهدة
    fetchAdStatus();
  };
  $('#authBtn').onclick = () => openModal('authModal');
  $('#settingsBtn').onclick = () => {
    $('#defaultApiUrl').textContent = BROWSER_API_URL;
    $('#apiBaseInput').value = apiBase;
    openModal('settingsModal');
  };
  $('#resetApiBtn').onclick = () => {
    $('#apiBaseInput').value = BROWSER_API_URL;
    toast('تم استعادة الرابط الافتراضي');
  };
  $('#saveSettings').onclick = () => {
    apiBase = $('#apiBaseInput').value.trim().replace(/\/$/, '') || BROWSER_API_URL;
    localStorage.setItem('hilal_api_base', apiBase);
    syncExtension();
    closeModal('settingsModal');
    toast('تم حفظ إعدادات الخادم');
    refreshMe(); fetchPackages();
  };

  async function auth(endpoint) {
    const payload = {
      email: $('#authEmail').value.trim(),
      password: $('#authPass').value.trim(),
    };
    if (endpoint === 'register') payload.invite_code = $('#authInvite').value.trim() || undefined;
    try {
      const d = await api('/api/' + endpoint, { method: 'POST', body: JSON.stringify(payload) });
      token = d.token;
      localStorage.setItem('hilal_token', token);
      syncExtension();
      $('#authHint').textContent = 'تم! جارٍ تحميل حسابك...';
      await refreshMe();
      closeModal('authModal');
      toast(endpoint === 'register' ? 'أهلاً بك! حصلت على نقطتين مجانيتين 🌱' : 'أهلاً بعودتك 🌙');
    } catch (e) { $('#authHint').textContent = '⚠️ ' + e.message; }
  }
  $('#loginBtn').onclick = () => auth('login');
  $('#registerBtn').onclick = () => auth('register');

  $('#verifyBtn').onclick = async () => {
    const tx = $('#txInput').value.trim();
    if (!tx) { toast('أدخل TxID'); return; }
    const btn = $('#verifyBtn'); btn.disabled = true; btn.textContent = 'جارٍ التحقق...';
    try {
      const d = await api('/api/verify-payment', {
        method: 'POST',
        body: JSON.stringify({ tx_hash: tx, package_id: $('#packageSelect').value }),
      });
      toast(`تمت إضافة ${d.points_added} نقطة ✅`);
      $('#txInput').value = '';
      refreshMe();
    } catch (e) { toast(e.message); }
    finally { btn.disabled = false; btn.textContent = 'تحقق وأضف النقاط'; }
  };

  // Invite code from URL
  const params = new URLSearchParams(location.search);
  if (params.get('invite')) $('#authInvite').value = params.get('invite');

  // init
  $('#defaultApiUrl').textContent = BROWSER_API_URL;
  renderPoints(); renderHistory(); setMode('chat');
  refreshMe(); fetchPackages(); fetchAdStatus();
})();
