// Runs only on Penumbra's pairing page (`pair.html` on this computer). It hands the key from the
// page's fragment to the extension and tells the page whether pairing worked. The key never leaves
// this browser except to the Penumbra server the page came from.
(() => {
  const code = new URLSearchParams(location.hash.slice(1)).get("code");
  if (!code) return;
  chrome.runtime.sendMessage({ type: "pair", code }, (answer) => {
    window.postMessage({ penumbra: "paired", ok: Boolean(answer && answer.ok) }, location.origin);
  });
})();
