// The pairing page's only job is to say what happened. The extension's content script reads the
// key from the fragment and answers with a window message; this page never touches the key itself
// except to take it out of the address bar once it has been read, so it does not linger in history.
(() => {
  if (typeof applyStaticI18n === "function") applyStaticI18n();
  document.documentElement.lang = typeof uiLang === "function" ? uiLang() : "en";
  const status = document.getElementById("pair-status");
  const help = document.getElementById("pair-help");
  let answered = false;

  const forget = () => history.replaceState(null, "", location.pathname);

  window.addEventListener("message", (event) => {
    if (event.source !== window || !event.data || event.data.penumbra !== "paired") return;
    answered = true;
    forget();
    if (event.data.ok) {
      status.textContent = t("pair.done", "Connected. You can close this page.");
      status.classList.add("is-done");
    } else {
      status.textContent = t("pair.failed", "The extension could not reach Penumbra.");
      help.textContent = t("pair.failedHelp", "Make sure Penumbra is running, then press Connect browser in its settings again.");
      help.hidden = false;
    }
  });

  if (!location.hash.includes("code=")) {
    status.textContent = t("pair.noCode", "Open this page from Penumbra's settings (Connect browser).");
    return;
  }
  setTimeout(() => {
    if (answered) return;
    forget();
    status.textContent = t("pair.noExtension", "The Penumbra extension is not installed in this browser.");
    help.textContent = t("pair.noExtensionHelp",
      "Install it (Settings in Penumbra explains how), then press Connect browser again.");
    help.hidden = false;
  }, 2500);
})();
