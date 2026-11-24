(() => {
  let mode = 'chat';
  const out = document.getElementById('out');

  document.querySelectorAll('.mode').forEach(b => b.onclick = () => {
    mode = b.dataset.mode;
    document.querySelectorAll('.mode').forEach(x => x.classList.toggle('active', x === b));
  });

  document.getElementById('go').onclick = async () => {
    const q = document.getElementById('q').value.trim();
    if (!q) return;
    const { apiBase, token } = await chrome.storage.sync.get(['apiBase', 'token']);
    if (!apiBase || !token) { out.textContent = '⚠️ سجّل الدخول في الواجهة الكاملة أولاً.'; return; }
    out.textContent = 'جارٍ المعالجة...';
    try {
      const path = mode === 'chat' ? '/api/ai/chat' : mode === 'image' ? '/api/ai/image' : '/api/ai/audio';
      const body = mode === 'chat' ? { prompt: q } : mode === 'audio' ? { text: q } : { prompt: q, mode: 'text' };
      const r = await fetch(apiBase + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
        body: JSON.stringify(body),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'HTTP ' + r.status);
      out.textContent = d.reply || ('تم: ' + (apiBase + d.url));
      if (d.url) window.open(apiBase + d.url, '_blank');
    } catch (e) { out.textContent = '⚠️ ' + e.message; }
  };
})();
