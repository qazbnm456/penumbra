// Says whether this browser is paired with a running Penumbra, and how to pair or unpair it.
const msg = (key, ...subs) => chrome.i18n.getMessage(key, subs) || key;
document.querySelectorAll("[data-msg]").forEach((el) => {
  const text = msg(el.dataset.msg);
  if (text) el.textContent = text;
});
document.documentElement.lang = chrome.i18n.getUILanguage();

const status = document.getElementById("status");

async function paint() {
  const { base, token } = await chrome.storage.local.get(["base", "token"]);
  document.getElementById("unpaired").hidden = Boolean(token);
  document.getElementById("paired").hidden = !token;
  status.classList.remove("is-ok");
  if (!token) {
    status.textContent = msg("statusUnpaired");
    return;
  }
  try {
    const resp = await fetch(`${base}/extension/status`, { headers: { Authorization: `Bearer ${token}` } });
    if (resp.status === 401) {
      status.textContent = msg("errorUnpaired");
      return;
    }
    if (!resp.ok) throw new Error(String(resp.status));
    status.textContent = msg("statusPaired", base);
    status.classList.add("is-ok");
  } catch {
    status.textContent = msg("errorServer");
  }
}

document.getElementById("unpair").addEventListener("click", async () => {
  await chrome.storage.local.remove(["base", "token"]);
  await paint();
});
chrome.storage.onChanged.addListener(() => void paint());
void paint();
