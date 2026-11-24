chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.get(['apiBase'], ({ apiBase }) => {
    if (!apiBase) chrome.storage.sync.set({ apiBase: 'https://hilal-ai-8s01.onrender.com' });
  });
});
