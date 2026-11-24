/* Hilal AI — زر التواصل / الدعم الفني (Gmail) ونسخ البريد بضغطة واحدة */
(() => {
  'use strict';

  const SUPPORT_EMAIL = 'ghassanhilal934@gmail.com';
  window.hilalSupportEmail = SUPPORT_EMAIL;

  async function copyText(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
      throw new Error('clipboard unavailable');
    } catch (_) {
      // بديل يعمل داخل APK (capacitor://) ومتصفحات بدون صلاحية الحافظة
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.cssText = 'position:fixed;top:0;left:-9999px;opacity:0';
      document.body.appendChild(ta);
      ta.select();
      ta.setSelectionRange(0, text.length);
      let ok = false;
      try { ok = document.execCommand('copy'); } catch (_) {}
      document.body.removeChild(ta);
      return ok;
    }
  }
  window.hilalCopyText = copyText;

  function notify(msg) {
    if (typeof window.hilalToast === 'function') window.hilalToast(msg);
    else {
      const el = document.getElementById('supportToast') || (() => {
        const d = document.createElement('div');
        d.id = 'supportToast';
        d.className = 'toast show';
        document.body.appendChild(d);
        return d;
      })();
      el.textContent = msg;
      el.classList.add('show');
      clearTimeout(el._t);
      el._t = setTimeout(() => el.classList.remove('show'), 3000);
    }
  }

  // يُحقن البريد من هذا الملف الخارجي حتى لا تعترضه أدوات إخفاء البريد (Cloudflare)
  function hydrate() {
    document.querySelectorAll('[data-support-email]').forEach(el => {
      el.textContent = SUPPORT_EMAIL;
    });
    document.querySelectorAll('[data-mail-support]').forEach(a => {
      const subject = a.dataset.subject || 'Hilal AI - Support Request';
      a.href = 'mailto:' + SUPPORT_EMAIL + '?subject=' + encodeURIComponent(subject);
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', hydrate);
  } else {
    hydrate();
  }

  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-copy-support],[data-copy-text]');
    if (!btn) return;
    e.preventDefault();
    const ok = await copyText(btn.dataset.copyText || SUPPORT_EMAIL);
    notify(ok ? 'تم نسخ البريد الإلكتروني ✓' : 'انسخ البريد يدوياً: ' + SUPPORT_EMAIL);
  });
})();
