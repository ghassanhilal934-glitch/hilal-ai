/* Hilal AI — لوحة المدير */
(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const BASE = (localStorage.getItem('hilal_api_base') || window.location.origin).replace(/\/$/, '');
  let token = sessionStorage.getItem('hilal_admin_token') || '';

  function toast(msg) {
    const el = $('#toast');
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('show'), 3200);
  }

  async function api(path, opts = {}) {
    opts.headers = opts.headers || {};
    opts.headers['Content-Type'] = 'application/json';
    if (token) opts.headers['Authorization'] = 'Bearer ' + token;
    const res = await fetch(BASE + path, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || ('HTTP ' + res.status));
    return data;
  }

  function showApp() {
    $('#loginScreen').hidden = true;
    $('#adminApp').hidden = false;
    loadAll();
  }

  async function login() {
    const pass = $('#adminPass').value;
    if (!pass) { $('#loginError').textContent = 'أدخل كلمة المرور'; return; }
    try {
      const d = await api('/api/admin/login', {
        method: 'POST', body: JSON.stringify({ password: pass }),
      });
      token = d.token;
      sessionStorage.setItem('hilal_admin_token', token);
      $('#loginError').textContent = '';
      showApp();
    } catch (e) { $('#loginError').textContent = e.message; }
  }

  function renderStats(s) {
    const cards = [
      ['إجمالي المستخدمين', s.users, ''],
      ['مستخدمون دفعوا', s.paid_users, ''],
      ['إجمالي الإيرادات', s.revenue_usdt + ' USDT', 'gold'],
      ['النقاط المتداولة', s.points_in_circulation, ''],
      ['إعلانات مستلمة', s.ads_claimed, ''],
      ['تسجيلات اليوم', s.signups_today, ''],
    ];
    $('#stats').innerHTML = cards.map(([label, value, cls]) =>
      `<div class="stat ${cls}"><span>${label}</span><strong>${value}</strong></div>`
    ).join('');
  }

  function renderUsers(list) {
    const q = ($('#userSearch').value || '').trim().toLowerCase();
    const rows = list.filter(u => !q || u.email.toLowerCase().includes(q));
    const body = $('#usersTable tbody');
    if (!rows.length) { body.innerHTML = '<tr><td colspan="6">لا يوجد مستخدمون</td></tr>'; return; }
    body.innerHTML = rows.map(u => `
      <tr>
        <td class="dir-ltr">${escapeHtml(u.email)}</td>
        <td>${u.points}</td>
        <td>${u.paid_count ? '<span class="badge">دفع</span>' : '—'}</td>
        <td class="dir-ltr">${escapeHtml(u.invite_code)}</td>
        <td>${escapeHtml(u.created_at || '')}</td>
        <td><div class="row-actions">
          <button data-quick="${escapeHtml(u.email)}">+5</button>
          <button data-ban="${escapeHtml(u.email)}">حظر</button>
          <button data-unban="${escapeHtml(u.email)}">فك</button>
        </div></td>
      </tr>`).join('');

    body.querySelectorAll('[data-quick]').forEach(b => b.onclick = () => {
      $('#pointsEmail').value = b.dataset.quick;
      $('#pointsAmount').value = '5';
      $('#pointsEmail').scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    body.querySelectorAll('[data-ban],[data-unban]').forEach(b => b.onclick = async () => {
      const banned = !!b.dataset.ban;
      if (!confirm((banned ? 'حظر ' : 'فك حظر ') + b.dataset.ban + '؟')) return;
      try {
        await api('/api/admin/ban', {
          method: 'POST',
          body: JSON.stringify({ email: b.dataset.ban || b.dataset.unban, banned }),
        });
        toast(banned ? 'تم الحظر ✅' : 'تم فك الحظر ✅');
        loadAll();
      } catch (e) { toast(e.message); }
    });
  }

  function renderPayments(list) {
    const body = $('#paymentsTable tbody');
    if (!list.length) { body.innerHTML = '<tr><td colspan="6">لا توجد مدفوعات بعد</td></tr>'; return; }
    body.innerHTML = list.map(p => `
      <tr>
        <td class="dir-ltr" title="${escapeHtml(p.tx_hash)}">${escapeHtml(p.tx_hash.slice(0, 14))}…</td>
        <td class="dir-ltr">${escapeHtml(p.email)}</td>
        <td>${escapeHtml(p.package_id)}</td>
        <td>${p.amount} USDT</td>
        <td>+${p.points}</td>
        <td>${escapeHtml(p.created_at || '')}</td>
      </tr>`).join('');
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  async function loadAll() {
    try {
      const [s, u, p] = await Promise.all([
        api('/api/admin/stats'), api('/api/admin/users'), api('/api/admin/payments'),
      ]);
      renderStats(s);
      window._admUsers = u.users;
      renderUsers(u.users);
      renderPayments(p.payments);
    } catch (e) {
      if (/401|جلسة/.test(e.message)) {
        token = ''; sessionStorage.removeItem('hilal_admin_token');
        $('#adminApp').hidden = true; $('#loginScreen').hidden = false;
      }
      toast(e.message);
    }
  }

  $('#adminLoginBtn').onclick = login;
  $('#adminPass').addEventListener('keydown', e => { if (e.key === 'Enter') login(); });
  $('#adminRefresh').onclick = loadAll;
  $('#adminLogout').onclick = () => {
    token = ''; sessionStorage.removeItem('hilal_admin_token');
    $('#adminApp').hidden = true; $('#loginScreen').hidden = false;
    $('#adminPass').value = '';
  };
  $('#userSearch').addEventListener('input', () => renderUsers(window._admUsers || []));

  $('#addPointsBtn').onclick = async () => {
    const btn = $('#addPointsBtn'); btn.disabled = true;
    try {
      const d = await api('/api/admin/add-points', {
        method: 'POST',
        body: JSON.stringify({
          email: $('#pointsEmail').value.trim(),
          points: parseFloat($('#pointsAmount').value),
          note: $('#pointsNote').value.trim(),
        }),
      });
      $('#pointsMsg').textContent = `تم ✅ الرصيد الجديد: ${d.balance}`;
      toast('تم تحديث النقاط');
      loadAll();
    } catch (e) { $('#pointsMsg').textContent = '⚠️ ' + e.message; }
    finally { btn.disabled = false; }
  };

  async function setBan(banned) {
    try {
      await api('/api/admin/ban', {
        method: 'POST',
        body: JSON.stringify({ email: $('#banEmail').value.trim(), banned }),
      });
      $('#banMsg').textContent = banned ? 'تم الحظر ✅' : 'تم فك الحظر ✅';
      loadAll();
    } catch (e) { $('#banMsg').textContent = '⚠️ ' + e.message; }
  }
  $('#banBtn').onclick = () => setBan(true);
  $('#unbanBtn').onclick = () => setBan(false);

  if (token) showApp();
})();
