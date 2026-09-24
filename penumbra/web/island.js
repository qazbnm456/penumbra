// The island's behaviour. Zero-build, like the rest of `web/`, and it talks to the same server the
// workspace does, over HTTP with the same token (invariants 77 and 81).
//
// The SHELL owns geometry: it watches the pointer, sizes this window and calls
// `island.setState(...)`. The page owns everything drawn, and one navigation: clicking asks the shell
// to open the workspace by navigating to `/__shell/open`, which the shell intercepts and refuses.
// That fixed URL is the only thing this page can ask of the shell, and it carries no data.

(() => {
  const TOKEN_KEY = "penumbra-api-token";
  let token = "";

  // The shell opens this page at `island.html#token=…`, the same way it opens the workspace. The
  // fragment never reaches the server's log; it is read here and cleared from the address.
  try {
    const params = new URLSearchParams(window.location.hash.slice(1));
    token = params.get("token") || "";
    if (token) {
      try {
        localStorage.setItem(TOKEN_KEY, token);
      } catch {
        // storage blocked: this page keeps the token in memory, which is all it needs
      }
      window.history.replaceState(null, "", window.location.pathname);
    } else {
      token = localStorage.getItem(TOKEN_KEY) || "";
    }
  } catch {
    // no URL/history here: requests will say the token is missing
  }

  const say = (key, fallback, vars) => (typeof t === "function" ? t(key, fallback, vars) : fallback);
  const hole = document.getElementById("hole");
  const motes = document.getElementById("motes");
  const line = document.getElementById("say-line");
  const count = document.getElementById("count");
  const live = document.getElementById("live");
  let swallowed = 0;

  // Pin the shape to the resting window's size in pixels at once. Left at `100%`, a window the
  // shell enlarges before its first `setState` arrives would drag the shape with it in one jump.
  hole.style.width = `${window.innerWidth}px`;
  hole.style.height = `${window.innerHeight}px`;

  if (typeof applyStaticI18n === "function") applyStaticI18n();
  document.documentElement.lang = typeof uiLang === "function" ? uiLang() : "en";

  function setLine(key, fallback, vars) {
    line.textContent = say(key, fallback, vars);
  }

  // --- states, set by the shell --------------------------------------------------------------------

  const LINES = {
    hover: ["island.hint", "Drop anything here"],
    armed: ["island.release", "Let go to send it into the Horizon"],
  };

  window.island = {
    setState(state, edge, inset, width, height) {
      if (edge) document.body.dataset.edge = edge;
      if (typeof inset === "number") document.body.style.setProperty("--inset", `${inset}px`);
      // The shape's size is explicit and TRANSITIONED, so it grows out of the notch and shrinks back
      // into it. The window around it is already at least this big (the shell grows the window
      // first and shrinks it last), so the animation always has room.
      if (typeof width === "number" && typeof height === "number") {
        hole.style.width = `${width}px`;
        hole.style.height = `${height}px`;
      }
      document.body.dataset.state = state;
      const words = LINES[state];
      if (words) setLine(...words);
    },
  };

  // --- open the workspace --------------------------------------------------------------------------

  function openWorkspace() {
    window.location.href = "/__shell/open";
  }

  hole.addEventListener("click", openWorkspace);
  hole.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openWorkspace();
    }
  });

  // --- capture -------------------------------------------------------------------------------------

  async function send(path, init) {
    const headers = { ...(init.headers || {}), Authorization: `Bearer ${token}` };
    if (typeof uiLangName === "function") headers["X-Penumbra-Interface-Language"] = uiLangName();
    const resp = await fetch(path, { ...init, headers });
    if (!resp.ok) {
      let detail = `${resp.status}`;
      try {
        detail = (await resp.json()).detail || detail;
      } catch {
        // not JSON
      }
      throw new Error(detail);
    }
    return resp.json();
  }

  // What a drag carries, in the order a person means it: files first, then links, then text.
  function readDrop(data) {
    const files = [...(data.files || [])];
    if (files.length) return { files, urls: [], texts: [], names: files.map((f) => f.name) };
    const uris = (data.getData("text/uri-list") || "")
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith("#") && /^https?:\/\//i.test(l));
    if (uris.length) return { files: [], urls: uris, texts: [], names: uris.map(hostOf) };
    const text = (data.getData("text/plain") || "").trim();
    if (!text) return null;
    if (/^https?:\/\/\S+$/i.test(text)) return { files: [], urls: [text], texts: [], names: [hostOf(text)] };
    return { files: [], urls: [], texts: [text], names: [text.slice(0, 40)] };
  }

  function hostOf(url) {
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch {
      return url.slice(0, 40);
    }
  }

  async function capture(item) {
    if (item.files.length) {
      const form = new FormData();
      item.files.forEach((file) => form.append("file", file, file.name));
      const out = await send("/horizon/upload", { method: "POST", body: form });
      if (out.refused && out.refused.length && !(out.nodes || []).length) {
        throw new Error(out.refused.map((r) => r.filename).join(", "));
      }
      return (out.nodes || []).length;
    }
    const out = await send("/horizon", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls: item.urls, texts: item.texts }),
    });
    return (out.nodes || []).length;
  }

  // One pill per thing dropped, starting where it was let go and spiralling into the horizon.
  function fall(names, x, y) {
    const centre = document.querySelector(".core").getBoundingClientRect();
    const cx = centre.left + centre.width / 2;
    const cy = centre.top + centre.height / 2;
    names.slice(0, 6).forEach((name, i) => {
      const mote = document.createElement("span");
      mote.className = "mote";
      mote.textContent = name;
      mote.style.setProperty("--cx", `${cx}px`);
      mote.style.setProperty("--cy", `${cy}px`);
      mote.style.setProperty("--dx", `${x - cx + i * 14}px`);
      mote.style.setProperty("--dy", `${y - cy + i * 8}px`);
      mote.style.animationDelay = `${i * 70}ms`;
      motes.appendChild(mote);
      mote.addEventListener("animationend", () => mote.remove());
    });
  }

  // The page must claim the drag or the webview treats a dropped file as a navigation.
  window.addEventListener("dragover", (event) => {
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
  });

  window.addEventListener("drop", async (event) => {
    event.preventDefault();
    const item = event.dataTransfer && readDrop(event.dataTransfer);
    if (!item) return;
    window.island.setState("swallow");
    fall(item.names, event.clientX, event.clientY);
    try {
      const landed = await capture(item);
      swallowed += landed;
      count.textContent = `+${swallowed}`;
      count.hidden = false;
      setLine("island.swallowed", `Sent into the Horizon`, {});
      live.textContent = say("island.swallowedCount", `${landed} sent into the Horizon`, { n: landed });
    } catch (err) {
      setLine("island.failed", "Could not take that in");
      live.textContent = `${say("island.failed", "Could not take that in")}: ${err.message}`;
    }
  });
})();
