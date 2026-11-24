chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.get(['apiBase'], ({ apiBase }) => {
    if (!apiBase) chrome.storage.sync.set({ apiBase: 'http://192.168.1.104:8000' });
  });
});
