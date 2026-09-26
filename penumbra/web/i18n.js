// Interface language for the web UI. Deliberately SEPARATE from the orbit's output language.
//
// `PN_OUTPUT_LANGUAGE` / `Orbit.output_language` (invariant 39) decide what the MODEL writes —
// answers, summaries, a podcast script. This decides what the BUTTONS say. They are different
// questions with different right answers: a reader in Taiwan may well want a Chinese interface over
// English papers, and folding the two together makes that combination unexpressible.
//
// The choice IS now sent to the server, as one SIGNAL among four that `naming.SuggestLanguage`
// weighs when an orbit has no output language yet (`X-Penumbra-Interface-Language`, added in `api()`).
// That is not the two settings merging: an explicit output-language setting still wins outright and
// the settings page still carries both rows. It is that a reader who picked Traditional Chinese for
// the interface has told us something real about what they read, and ranking it ABOVE
// `Accept-Language` — which was inherited from the OS, not chosen here — is what a user asked for
// after their orbit came back titled in English. An earlier version of this comment said nothing
// here ever reaches a prompt; that stopped being true and is stated rather than left to be found.
//
// Zero-build, same as the rest of `web/`: a plain script defining globals, loaded before `app.js`.

// **Preferences from before the rename.** The app was rlm-notebook, and its per-reader choices
// (interface language, theme, panel width, the API token) were stored under `rlmnb-*`. Copied once
// to `penumbra-*` where the new key is still empty, so a browser user keeps them. This file loads
// first, so everything that reads a preference already sees the new key. Storage can be blocked,
// which costs only the carry-over.
try {
  for (let i = localStorage.length - 1; i >= 0; i--) {
    const old = localStorage.key(i);
    if (old && old.startsWith("rlmnb-")) {
      const renamed = `penumbra-${old.slice("rlmnb-".length)}`;
      if (localStorage.getItem(renamed) === null) localStorage.setItem(renamed, localStorage.getItem(old));
    }
  }
} catch {
  // no storage in this context
}

const UI_LANGUAGES = [
  // `name` is the ENGLISH name, and is what travels to the server as the language SIGNAL — the
  // model weighing it answers in English language names ("Traditional Chinese"), so sending
  // `zh-Hant` or `繁體中文` would make it parse a code or a word in the very language it is trying
  // to identify. `label` stays in the language itself, because that is what a picker should show.
  { code: "en", label: "English", name: "English" },
  { code: "zh-Hant", label: "繁體中文", name: "Traditional Chinese" },
];

// The English name of the interface language currently in force, for the request header.
function uiLangName() {
  const found = UI_LANGUAGES.find((l) => l.code === uiLang());
  return found ? found.name : "";
}

const STRINGS = {
  en: {},  // the source language: every key falls back to `index.html`/`app.js`'s own text
  "zh-Hant": {
    // --- header
    "app.newOrbit": "開新軌道",
    "app.settings": "設定",
    "app.theme": "切換淺色／深色",
    "app.pickerTip": "切換軌道、改名，或開一個新的",
    "app.workspace": "軌道",
    "app.orbits": "軌道清單",
    "studio.resize": "調整面板寬度",
    "modal.close": "關閉",
    "traj.head": "執行軌跡",
    // The five playback controls. They were the only `data-tip`s in `index.html` with no
    // `data-i18n-tip` beside them, so the accessibility tree computed their names in English
    // ("⏮ Previous step") inside a Chinese interface while ✕ and the search box announced 關閉
    // and 搜尋回合… two elements away.
    "traj.prev": "上一步",
    "traj.play": "照這次執行的真實速度重播",
    "traj.next": "下一步",
    "traj.speed": "重播速度",
    "traj.expand": "展開成全螢幕",
    "traj.run": "這次執行",
    "app.noOrbit": "未開啟軌道",
    // A bookmarked link to an orbit that has since been deleted. It used to open a blank
    // "Untitled orbit" and say nothing, so the reader's own bookmark became a new empty thing.
    // The wordmark, which is Home. It used to claim to start a new orbit and do nothing at
    // all on the default screen, from the first tab stop.
    "app.home": "回到視界",
    "lens.clear": "清除",
    "lens.clearAll": "清除標籤",
    "lens.kickerMany": "這些標籤亮起了什麼",
    "lens.kickerOne": "這個標籤亮起了什麼",
    "lens.remove": "移除 #{name}",
    "lens.countMany": "{n} 則收錄帶有其中至少一個",
    "lens.countOne": "{n} 則收錄帶有這個標籤",
    "lens.noSummary": "還沒摘要，目前只知道它的標籤。",
    "lens.loose": "還沒歸入軌道",
    "lens.more": "還有 {n} 則。",
    "lens.askMany": "對這些標籤亮起的收錄提問",
    "lens.askOne": "對這個標籤亮起的收錄提問",
    "graph.tags": "標籤",
    "graph.zoomHome": "回到整張圖",
    "app.homeHint": "回到視界。按右鍵認識半影小月",
    "mascot.name": "半影小月",
    "mascot.line1": "嗨，我是半影小月。我一半亮著、一半在影子裡，中間那道模糊的交界叫做半影，Penumbra 這個名字就是從這裡來的。",
    "mascot.line2": "你丟進來的東西都會先落在視界。我提著這盞燈一則一則照過去，照亮的地方就成了摘要。",
    "mascot.line3": "看起來有關係的東西，我會用線把它們牽在一起，星圖上的虛線就是這些線。找到歸宿的，就收進軌道裡慢慢繞。",
    "mascot.line4": "除非你另外設定，我只在你按下去的時候才動手，不會背著你偷花額度。好啦，丟點東西進來吧！",
    "mascot.next": "下一句",
    "mascot.done": "好喔",
    "app.skipToCapture": "跳到收納欄位",
    "app.skipToAsk": "跳到提問欄位",
    "app.orbitGone": "那個軌道已經不在了。",
    "app.orbitFailed": "無法開啟那個軌道：{message}",
    "app.cancel": "取消",
    // The destructive action NAMES ITSELF. "Yes" against "Cancel" is `confirm()`'s wording, kept
    // along with `confirm()`'s shape; a reader skimming a dialog reads the buttons, not the
    // sentence, so the button has to say what it does.
    "app.confirm": "刪除",
    "app.dismiss": "關閉這則訊息",
    "app.untitled": "未命名軌道",
    // Only ever appended to a label that collides with another one (`facetLabels`).
    "app.sourceCount": "{count} 個來源",
    // Shown where the "file into" picker would be, on a node that has no text to file.
    // A file dropped outside the Horizon. Refused rather than captured: filing something into a
    // surface the reader is not looking at is its own surprise.
    "horizon.dropElsewhere": "要丟檔案的話，請先回到視界。",
    "sources.oneFileOnly": "這裡一次只能放一個檔案，其餘的請丟進視界。",
    "horizon.tooBigToUpload": "這個檔案超過 {limit} 的上限。",
    "horizon.wasStopped": "你停掉了這一則",
    "horizon.stillReading": "還在讀這一則…",
    "horizon.notFilable": "還沒有文字，無法歸入軌道",
    "horizon.filedInGone": "一個已刪除的軌道",
    // The summary pass's own failure count. The REASON beside it is the server's own
    // sentence and is deliberately not translated: it names an environment variable.
    // The stretched open-button's accessible name, used only when a row has neither a title
    // nor prose to name it by.
    // A drop where some files landed and some did not. Names them: "could not ingest that
    // file" beside a stream that grew by two is not actionable.
    "horizon.someRefused": "讀不到 {names}",
    // A node past the corpus ceiling: it captured fine and cannot be answered from.
    "horizon.tooBig": "太大，無法用來提問",
    // The Horizon failure block's heading. Same shape as the chat and summary failures.
    "horizon.stopTip": "停掉還在排隊的；正在讀的那一則會讀完。",
    "horizon.couldNotRead": "讀不到這一則",
    "horizon.openNode": "展開這一則",
    // A pass that never began, which is NOT "n nodes failed" - nothing was attempted.
    "horizon.distilNoStart": "摘要無法開始",
    "horizon.distilDismiss": "關閉",
    "horizon.distilFailedCount": "{n} 則摘要失敗",
    "app.newOrbitRow": "＋ 新的軌道",
    "app.rowMeta": "{sources} 個來源 · {turns} 則問答",
    "app.rename": "改名",
    "app.deleteOrbit": "刪除軌道",
    "app.deleteOrbitAsk": "要刪除「{name}」嗎？裡面的來源和對話會一起刪除，視界裡的東西會留著。",
    "app.generating": "這個軌道有工作正在執行",
    "time.justNow": "剛剛",
    "time.minutes": "{n} 分鐘前",
    "time.hours": "{n} 小時前",
    "time.days": "{n} 天前",
    "err.rename": "無法改名：{message}",

    // --- sources
    "sources.head": "來源",
    "sources.tab.url": "網址",
    "sources.tab.text": "貼上文字",
    "sources.tab.file": "檔案",
    "sources.url.hint": "網頁或 YouTube 連結。YouTube 只取字幕，不下載影片或音訊。",
    "sources.text.placeholder": "在這裡貼上文字…",
    "sources.file.hint": "PDF、TXT 或 Markdown，一次一個檔案。",
    "sources.add": "加入來源",
    "sources.empty": "還沒有來源。從上面加入一個。",
    "sources.adding": "加入中…",
    // Named by the SOURCE. A rail of rows each announcing "Open" tells a screen-reader user which
    // control they are on and nothing about which source it opens.
    "sources.open": "開啟「{name}」",
    "sources.remove": "移除這個來源",
    "sources.removeConfirm": "要把「{origin}」從這個軌道移除嗎？",
    "sources.flagHelp":
      "這段內容出現在來源本身，不是你的提問。它不會被擋下，回答仍可能引用它；這只是提醒你，這份來源裡有看起來像在對模型下指令的文字。",
    "err.removeSource": "無法移除來源：{message}",

    // --- chat
    "chat.head": "對話",
    "chat.startUrl": "貼上連結",
    "chat.startText": "貼上文字",
    "chat.startFile": "上傳檔案",
    "flag.ignoreInstructions": "要模型忽略原本指示的文字",
    "flag.reassignRole": "試圖改變模型角色的文字",
    "flag.roleLabel": "行首出現對話角色標籤（System:／User:／Assistant:）",
    "flag.disregardRules": "要模型無視規則的文字",
    "flag.revealSecrets": "要模型說出提示詞或憑證的文字",
    "flag.base64": "一長串類似 base64 的字元（可能是編碼過的內容）",
    "cite.reasonNoSource": "這個軌道裡沒有來源 {id}，可能已經移除。",
    "cite.reasonNoWhole": "{id} 分成好幾段，引用時必須指明其中一段：{known}。",
    "cite.reasonNoBlock": "來源 {id} 裡沒有 {locator}。它有的是：{known}。",
    "kind.web": "網頁",
    "kind.pdf": "PDF",
    "kind.text": "文字",
    "kind.youtube": "YouTube",
    "err.desktopWhere": "在桌面版裡，這些設定在「{config}」，改完後用「{restart}」套用。",
    "err.desktopRestart": "可以用「{restart}」重新啟動它。",
    "settings.landing": "新收的東西放到哪裡",
    "settings.landingOff": "只留在視界",
    "settings.landingHelp": "預設會把收進來的東西也歸入你的第一個軌道，馬上就能提問。不論怎麼選，它都會留在視界裡。",
    "island.open": "打開 Penumbra",
    "island.hint": "把任何東西丟過來",
    "island.release": "放開，丟進視界",
    "island.swallowed": "已丟進視界",
    "island.swallowedCount": "{n} 樣東西已丟進視界",
    "island.failed": "收不進來",
    "island.pen": "寫一句",
    "island.noteLabel": "寫一句話收進視界",
    "island.notePlaceholder": "寫下一個念頭，按 Return 收進視界，Esc 取消",
    "island.noted": "收進視界了",
    "island.listenHint": "或直接打字，記下一個念頭",
    "island.couldNotRead": "這些檔案無法讀取",
    "island.noServer": "Penumbra 沒有回應。在這裡按右鍵可以重新啟動它。",
    "island.tooBig": "檔案太大",
    "island.restarted": "Penumbra 剛重新啟動，請再丟一次。",
    "island.unsupported": "目前只收 PDF、TXT 和 Markdown 檔",
    "island.partial": "{n} 樣已丟進視界，{refused} 樣無法讀取",
    "island.swallowing": "處理中…",
    "island.glance": "已摘要 {done} / {total} 項，{n} 項可以歸檔",
    "chat.needSource": "請先加入來源，每個回答都以你的來源為依據。",
    "panels.label": "軌道面板",
    "chat.export": "匯出",
    "chat.exportTip": "把這個軌道（來源、概覽、每一則回答與其引用）下載成一份 Markdown 檔。",
    "copy.action": "複製",
    "copy.help": "把這段內容和它的引用複製成 Markdown",
    "copy.done": "已複製",
    "copy.failed": "複製失敗，請自行選取文字複製。",
    "copy.references": "參考資料",
    "copy.unverified": "未驗證",
    "copy.unverifiedTag": "（未驗證）",
    "chat.empty": "加入來源之後就可以開始提問。",
    "chat.placeholder": "針對你的來源提問…",
    "chat.needsSource": "先加入一份來源，再開始提問。",
    "chat.ask": "提問",
    "chat.enterHint": "送出",
    "chat.newlineHint": "換行",
    "chat.thinking": "思考中…",
    "chat.stopped": "（已停止）",
    "chat.askNext": "接著問",
    "chat.noStarters": "這份概覽沒有附上建議問題，重新產生可以再試一次。",
    "chat.startWith": "可以先問",
    // A turn that failed. NOT an answer, so it does not get the answer's surface.
    "chat.askFailed": "這個問題沒有跑完",
    "chat.generateOverview": "整理重點並建議問題",
    "chat.orJustAsk": "…或直接在下面提問。",
    "chat.regenerateOverview": "↻ 重新產生概覽",
    "chat.overview": "概覽",
    "chat.overviewStale": "概覽 · 來源在這之後有變動",
    "chat.overviewSuperseded": "這份概覽已被較新的一份取代。",
    "chat.overviewFailed": "概覽沒有做出來",
    "chat.tryAgain": "↻ 再試一次",
    "chat.readingSources": "正在讀取你的來源…",
    "chat.saveAsNote": "存成筆記",
    "chat.saved": "已存進筆記",
    "chat.saveAsNoteHelp":
      "在右側的「筆記」留一份副本。筆記之後可以升級成來源，之後的提問才能引用它。",

    // --- citations
    "cite.references": "{n} 則參考",
    "cite.trace": "⌁ 推理",
    "cite.traceTip": "顯示模型讀到這段文字的那一步",
    "cite.verified": "這個引用確實指向來源裡的一段文字，但不代表旁邊的句子忠實轉述了它。",
    "cite.unverified": "在目前的來源裡找不到這個引用指向的位置{reason}",
    "cite.loading": "載入中…",
    "source.kind": "類型",
    "source.url": "網址",
    "source.origin": "出處",
    "source.pasted": "貼上的文字",
    "source.pastedIn": "直接貼進這個軌道",
    "source.size": "大小",
    "source.sizeValue": "{blocks} 個區塊 · {chars} 個字元",
    "source.flags": "已標記",

    // --- studio
    // The PANE is the Studio; this is its first VIEW, and calling both "Studio" left the reader
    // with a tab that appeared to contain itself. The four guide kinds live under it.
    "studio.head": "工作室",
    "studio.guideStale": "產生期間來源有變動，這份是依照變動前的來源做的。按 ↻ 重新產生，改用目前的來源。",
    "studio.guideKinds": "導覽種類",
    "sources.howToAdd": "加入來源的方式",
    "studio.headTip": "所有來源的摘要與分析",
    "podcast.headTip": "雙主持人的語音摘要",
    "podcast.hostA": "主持人 A",
    "podcast.hostB": "主持人 B",
    "traj.meta.main_model": "規劃模型",
    "traj.meta.sub_model": "輔助模型",
    "traj.meta.max_iterations": "回合上限",
    "traj.meta.max_tokens": "token 上限",
    "traj.meta.max_retries": "重試次數",
    "traj.meta.source_chars": "語料字數",
    "traj.meta.output_language": "輸出語言",
    "traj.meta.language": "語言",
    "traj.meta.target_length": "長度",
    "traj.meta.question": "問題",
    "traj.meta.accept_language": "Accept-Language",
    "traj.meta.interface_language": "介面語言",
    "references.headTip": "這次對話引用過的每一段",
    "notes.headTip": "你自己的隨手筆記",
    "studio.collapse": "收合這個面板",
    "references.head": "參考",
    "references.sub": "這個軌道裡所有被引用過的段落，集中在一處。",
    "references.empty": "還沒有任何引用。先提問，或產生一份概覽。",
    "references.uses": "引用 {n} 次",
    // --- trajectory drawer
    "chat.refreshOverview": "↻ 重新產生",
    "chat.clear": "清空對話",
    "chat.clearTip": "刪除這個軌道裡所有的提問與回答。來源、筆記和概覽會保留。",
    "chat.clearConfirm": "確定要刪除全部 {n} 則提問與回答？來源、筆記和概覽會保留。",
    "chat.regenerateTurn": "↻ 重新產生",
    "chat.regenerateTurnTip": "重新問一次這個問題，並取代這則回答。會再跑一次完整的模型執行。",
    "chat.overviewSecondHalf": "摘要完成 · 正在產生建議問題…",
    "traj.title": "執行軌跡",
    "traj.open": "開啟這次執行的軌跡",
    "traj.start": "開始",
    "traj.axis": "工具時間",
    "traj.initTitle": "起始狀態",
    "traj.initSub": "輸入 + 環境",
    "traj.timingTag": "● 每回合耗時",
    "traj.timingTagOff": "ⓘ 耗時",
    "traj.budgetTag": "\u25cf 用量",
    "traj.budgetTagCut": "\u26a0 已截斷",
    "traj.budgetTagNone": "\u24d8 用量",
    "traj.budgetOk": "用量最高的回合用了 {used} / {cap} tokens（{pct}%）。",
    "traj.budgetCut": "有一個回合撞到生成上限：{used} tokens，上限 {cap}。被截斷的如果是程式碼，通常下一個回合就會修好；被截斷的如果是最終答案，這次執行就結束了。",
    "traj.budgetNone": "這份軌跡沒有記錄 token 用量：它早於這個欄位存在。這不等於「沒有發生截斷」。",
    "traj.budgetPartial": "這次執行沒有回報生成上限。",
    "traj.budgetNoUsage": "生成上限是 {cap} tokens；這次執行沒有記錄可供比對的 token 用量。",
    "traj.budgetDropped": "步數預算被拒絕並退回函式庫的預設值，所以設定的上限並未生效。",
    "traj.noTools": "這次執行沒有呼叫任何工具，連指示要它在 SUBMIT 前執行的驗證器也沒有。",
    "traj.noMeta": "這次執行沒有留下設定紀錄。",
    "traj.notStarted": "這次執行還沒有留下任何紀錄，可能還在啟動，也可能根本沒跑起來。",
    "traj.search": "搜尋回合…",
    "traj.stat": "{turns} 個回合 · {tools} 次工具呼叫",
    "traj.init": "起始",
    "traj.turn": "第 {n} 回合",
    "traj.task": "任務",
    "traj.reasoning": "推理",
    "traj.code": "程式碼",
    "traj.output": "輸出",
    "traj.tool": "工具",
    "traj.openTurn": "\u2191 開啟回合 {n}",
    "traj.verdict": "驗證結果",
    "traj.result": "結果",
    "traj.input": "輸入",
    "traj.error": "錯誤",
    "traj.matches": "{n} 筆符合",
    "traj.missing": "找不到這次執行的軌跡（{message}）",
    // What the steps pill BECOMES when there is no trajectory behind it. No run id: the
    // reader cannot act on one, and it used to arrive inside a native alert box.
    "traj.none": "這次執行沒有留下過程。",
    "traj.timingLive": "每回合耗時是即時記錄的，每個回合解析完就寫下。",
    "traj.timingStale": "這份軌跡沒有每回合的耗時（回合不是即時標記的，或這次執行太短）；上方的工具時間軸仍是真實時間。",
    "cite.unverifiedShort": "未驗證",
    "cite.unverifiedHover": "來源裡找不到這個位置：{label}",
    "cite.unverifiedWhy":
      "這則引用指向的位置在這個來源裡不存在，所以無法查核。引文本身仍可能正確，對不上的是位置，不一定是內容。",
    "studio.sub": "根據你的來源產生的內容。你沒按下去之前，這裡不會自動執行任何東西。",
    "studio.tab.summary": "摘要",
    "studio.tab.faq": "問答",
    "studio.tab.timeline": "時間軸",
    "studio.tab.insight": "洞察",
    "studio.tip.summary": "用幾段文字整理所有來源的內容，附上可以查證的引用。",
    "studio.tip.faq": "你的來源真正回答得了的問題，每題都附答案和引用。",
    "studio.tip.timeline": "從來源裡抽出有日期的事件，依序排列。",
    "studio.tip.insight": "最重要的一個結論，一句話。",
    "studio.regenerate": "↻ 重新產生",
    "studio.regenerateTip": "用目前的來源再跑一次。",
    "studio.generate": "產生{kind}",
    "studio.generating": "正在產生{kind}…",
    "studio.addSourceFirst": "先加入來源，才能產生這個。",
    "studio.kind.summary": "摘要",
    "studio.kind.faq": "問答",
    "studio.kind.timeline": "時間軸",
    "studio.kind.insight": "洞察",
    "studio.noFaq": "沒有整理出問答，來源的內容不夠。",
    "studio.noTimeline": "沒有時間軸事件，來源裡沒有能標出時間的內容。",

    // --- podcast
    "podcast.head": "Podcast",
    "podcast.sub": "兩位主持人討論你的來源，產出一集可以播放或下載的節目。",
    "podcast.generate": "產生 Podcast",
    "podcast.length": "長度",
    "podcast.lenShort": "短",
    "podcast.lenDefault": "中等",
    "podcast.lenLong": "長",
    "podcast.lengthTip": "節目的目標長度。越長，模型執行和語音合成花的時間都越久。",
    "podcast.regenerate": "↻ 重新產生 Podcast",
    "podcast.regenerateStale": "↻ 重新產生 · 來源已變動",
    "podcast.generateTip": "先寫出一份以你的來源為依據的雙主持人腳本，再合成語音。這是這裡最慢的操作。",
    "podcast.needsSource": "先加入一份來源，才能產生。",
    "podcast.writing": "正在撰寫腳本…",
    "podcast.stale": "Podcast · 來源在這之後有變動",
    "podcast.audioGone": "這一集的音訊檔不見了，逐字稿還在。",
    "podcast.play": "播放",
    "podcast.pause": "暫停",
    "podcast.seek": "調整播放位置",
    "podcast.empty": "沒有產生 Podcast 腳本，來源的內容不夠討論。",
    "podcast.download": "⤓ 下載 {ext}",
    "podcast.downloadPlain": "⤓ 下載音訊",

    // --- notes
    "notes.head": "筆記",
    "notes.sub":
      "你自己的隨手筆記。在對話裡按回答旁的 ☆ 存下一則回答，之後把筆記升級成來源，之後的提問就能引用它。",
    "notes.placeholder": "寫一則筆記…",
    "notes.delete": "刪除這則筆記",
    "notes.deleteConfirm": "刪除這則筆記？刪除後無法復原。",
    "notes.add": "新增筆記",
    "notes.empty": "還沒有筆記。",
    "notes.promote": "→ 升級成來源",
    "md.urlCopied": "已複製連結網址",
    "notes.promoteHelp":
      "把這則筆記變成真正的來源。只有這樣，後續的提問才引用得到它；筆記本身只是文字，沒有自己的引用。",

    // --- run status
    "run.awaitingModelLong": "仍在等模型第一次回應 · {time} · 回覆前不會有進度；可以按停止",
    "run.notStoppable": "這個階段無法停止。",
    "podcast.synthesizing": "正在合成語音…（這個階段無法停止）",
    // No U+2301. It renders as an illegible ~7px squiggle at 0.7rem and carries no meaning a
    // reader could recover; the word does the whole job.
    "err.stepsLoad": "執行過程",
    "err.stepsGone": "⌁ 沒有紀錄",
    "err.stepsGoneNote": "這次執行的紀錄已被清除。紀錄只保留一段時間。",
    "run.stop": "⏹ 停止",
    // Only when the server could not reach the run. The page may not claim a stop it did not get.
    // A run found on the server that this page did not start (it was reloaded). Deliberately
    // generic: the id does not say which action it was, and naming a stage the page cannot
    // see is what invariant 60 forbids.
    "run.recovered": "這個軌道還有東西在跑",
    // A run the reader stopped. Not an error - they asked for it - and never with the run id or
    // the worker's exit code, which are the two things they cannot act on.
    // The actionable half of a server failure, without the status code, the exception class,
    // the OpenSSL source line or the shell incantation.
    "err.noModel": "還沒有設定模型。請設定 PN_MAIN_MODEL 並重新啟動伺服器。",
    "err.fakeIp": "這個連結被解析成保留位址，通常是假 IP 模式的代理或 VPN（Clash、Surge）在回應 DNS。把 PN_FETCH_ALLOW_CIDRS 設成它使用的範圍（常見的是 198.18.0.0/15），再重新啟動伺服器。",
    "err.refusedTarget": "這個位址不在可以抓取的範圍內。",
    "err.unreachable": "連不上這個位址。",
    "err.runTimedOut": "這次執行超過時間上限而被中止。較長的 Podcast 需要更多時間：把 PN_RUN_TIMEOUT_SECONDS 調高，然後重新啟動伺服器。",
    "err.noClaudeCode": "claude-agent-sdk 開頭的模型會透過 Claude Code 使用你的 Claude 訂閱，但這台電腦沒有安裝 Claude Code。請先安裝，在終端機執行一次 claude 登入，然後重新啟動伺服器。",
    "err.misconfigured": "有一項設定讓伺服器無法執行這個動作：{why}",
    "err.corpusCap": "這次要讀的文字超過單次執行的上限。移除一份來源，或把 PN_MAX_CORPUS_CHARS 調高，然後重新啟動伺服器。",
    "err.htmlReply": "模型伺服器回傳的是一個網頁，而不是回覆。中間很可能有代理伺服器或登入頁擋著。",
    "err.providerDown": "模型伺服器沒有回應。請確認它正在執行，而且 PN_BASE_URL 指向它。",
    "err.noServer": "與 Penumbra 伺服器失去連線，請確認它仍在執行後再試一次。",
    "err.serverFault": "伺服器出了問題，詳細情況在伺服器的日誌裡。",
    // 供應商端的三種失敗，加上兩種檔案失敗。每一句都只留讀者能動手的那一半：要去看哪個金鑰、
    // 哪個環境變數、哪一種檔案可以用，而不是狀態碼、例外類別名稱或一段 Python dict。
    "err.badKey": "模型供應商不接受 {model} 的 API 金鑰。請檢查 PN_API_KEY，然後重新啟動伺服器。",
    "err.badKeyPlain": "模型供應商不接受這個 API 金鑰。請檢查 PN_API_KEY，然後重新啟動伺服器。",
    "err.overQuota": "模型供應商拒絕了請求：超過頻率或額度上限。等一下再試，或檢查你的方案。",
    "err.noSuchModel": "你的供應商沒有叫做 {model} 的模型。請檢查 PN_MAIN_MODEL 並重新啟動伺服器。",
    "err.noSuchModelPlain": "你的供應商沒有這個模型。請檢查 PN_MAIN_MODEL 並重新啟動伺服器。",
    // 別人的網站回的狀態碼，不是模型供應商的問題。403 從供應商來是金鑰被拒，從網頁來是那一頁不讓人讀，
    // 而「抓不到的頁面」本來就是收東西最常見的失敗。翻成它的意思，不要把數字丟給讀者。
    "err.pageRefused": "這一頁不讓我們讀。可能需要登入，或是它擋自動抓取。",
    "err.pageGone": "這一頁已經不在了。",
    "err.pageBusy": "這個網站要我們慢一點。等一下再試。",
    "err.pageBroken": "這個網站自己出錯了。等一下再試。",
    "err.replyTooLong": "這個模型不會產生這麼長的回覆。把 PN_MAX_TOKENS 調小，然後重新啟動伺服器。",
    "err.contextTooLong": "來源太長，這個模型一次讀不完。拿掉一份，或換一個上下文長度更大的模型。",
    "err.badFileType": "這種檔案不支援。可以用 PDF、TXT 或 Markdown。",
    "err.badPdf": "這份 PDF 讀不出來，可能壞了，或其實不是 PDF。",
    "run.alreadyRunning": "這個軌道已經有東西在跑了。",
    "run.recoveredDone": "那次執行結束了。",
    "run.loadResult": "載入結果",
    "run.wasStopped": "你停止了這次執行。",
    "run.stopFailed": "停不下來，這次執行可能還在跑。",
    "run.stopping": "停止中…",
    "trace.start": "啟動",
    "trace.step": "第 {n} 步",
    "trace.stepBare": "步驟",
    "trace.tool": "工具",
    "trace.escalation": "子模型",
    "trace.final": "收尾",
    "trace.result": "結果",
    "trace.done": "完成",
    "trace.failed": "失敗",
    "trace.notFound": "這次執行沒有即時進度",
    "run.logToggle": "{n} 個步驟",
    "run.waiting": "已等待 {time}",
    "run.awaitingModel": "正在等待模型第一次回應 · {time}",
    "run.count.thinking": "步",
    "run.count.tool": "次工具",
    "run.count.escalation": "次求助子模型",

    // --- settings
    "settings.head": "設定",
    "settings.close": "關閉",
    "settings.save": "儲存",
    "settings.useDefault": "使用預設",
    "settings.uiLanguage": "介面語言",
    "settings.uiLanguageHelp": "只影響這個畫面的文字，不影響模型寫出來的內容。",
    "settings.outputLanguage": "輸出語言",
    "settings.outputLanguageHelp":
      "留空的話，每個軌道會自己從你的介面和系統語言、來源和提問推斷。",
    "settings.outputLanguagePlaceholder": "例如：繁體中文",
    "settings.voiceA": "Podcast 聲音：主持人 A",
    // The toggle invariant 80 promised. A BEHAVIOUR preference, which invariant 41 allows on
    // this page; its BOUND (PN_AUTO_DISTIL_MAX_PER_BATCH) stays environment-only.
    "settings.on": "開啟",
    "settings.off": "關閉",
    "settings.autoDistil": "自動摘要新收進來的東西",
    "settings.autoDistilHelp": "預設關閉。每一則摘要都是一次模型呼叫，用的是你自己的 API 金鑰，所以匯入 200 筆書籤，在你開啟這個選項前不會花一毛錢。",
    "settings.voiceB": "Podcast 聲音：主持人 B",
    "settings.voiceHelp": "留空的話，就讓軌道的語言決定這一對聲音。",
    "settings.pinnedBy": "由 {env} 指定。取消這個環境變數後才能在這裡修改。",
    "studio.noOrbit": "先開啟一個有來源的軌道，再選擇分頁產生內容。",
    "settings.readError": "儲存的設定讀取失敗（{error}），顯示的是預設值。",
    "settings.modelWhere": "模型和 API 金鑰在「{config}」裡設定，不在這裡。",
    "settings.saved": "設定已儲存。",
    "settings.saveFailed": "無法儲存設定：{message}",

    // --- generic errors
    "err.openOrbitFirst": "請先開啟一個軌道。",
    "err.addSource": "無法加入來源：{message}",
    "horizon.home": "視界",
    "horizon.homeTitle": "回到視界",
    "horizon.capture.label": "收進來",
    "horizon.capture.placeholder": "貼上連結，或寫下一個念頭…",
    "horizon.capture.send": "收進來",
    "horizon.capture.hint": "連結會抓取網頁內容，文字照你寫的保存。",
    "sources.choose": "選一個檔案…",
    "horizon.capture.choose": "選一個檔案…",
    "horizon.capture.orDrop": "或直接拖到這一頁的任何地方。",
    "horizon.empty": "還沒有東西落進來。在上面貼一個連結，小月會替你收著。",
    "horizon.stop": "停止",
    "horizon.more": "更早的",
    "horizon.sizeK": "約 {n} 千字",
    "horizon.sizeWan": "約 {n} 萬字",
    // **ONE noun for one object.** The rail said "新的面向" (new facet), the picker said
    // "＋ 新的軌道", the node's select said "新的軌道…", and the screen that opened
    // titled the result "未命名軌道" - three names for the same thing, in controls a
    // reader meets within one gesture of each other. "Facet" is the PITCH ("one facet of
    // yourself") and belongs in prose; the object is an orbit.
    "horizon.newFacet": "＋ 新的軌道",
    "horizon.today": "今天",
    "horizon.yesterday": "昨天",
    "horizon.daysAgo": "{n} 天前",
    "horizon.failed": "讀不到",
    // NAMES the batch, because the count beside it is the backlog and the two are different
    // numbers: "摘要它們" next to "324 則還沒摘要" promised 324 and spent on 50.
    "horizon.distil": "摘要其中 {n} 則",
    "horizon.longNote": "其中 {n} 則是長文件，每則要跑好幾次模型。",
    "horizon.alignNote": "摘要結束後，可能會再跑一次比對新實體。",
    "horizon.alignFailed": "新的實體沒有比對成功",
    "horizon.pendingSummaries": "{n} 則還沒摘要",
    "horizon.reading": "正在讀 {what}",
    "horizon.waiting": "等待中",
    "horizon.summarising": "摘要中",
    "horizon.progress": "{done} / {total}",
    "horizon.pending": "{n} 則等待中",
    "horizon.loading": "載入中…",
    "horizon.loadFailed": "{message}",
    "horizon.openFailed": "{message}",
    "horizon.fileInto": "歸入某個軌道",
    "horizon.fileIntoPlaceholder": "歸入…",
    "horizon.newOrbit": "新的軌道…",
    "horizon.filedIn": "已在 {where}",
    "horizon.firstRun.keep": "貼進來的東西會照原樣保存，並在背景讀取。",
    "horizon.firstRun.facets": "軌道用來歸類。等你知道某樣東西屬於哪裡，再把它放進去。",
    "horizon.firstRun.cost": "摘要要另外按才會執行。只是收著，不花錢。",
    "horizon.find": "找找你留下的東西…",
    "horizon.findClear": "清除",
    "horizon.noMatch": "沒有符合「{q}」的東西。",
    "horizon.retry": "再試一次",
    "horizon.forget": "移除",
    "horizon.forgetConfirm": "要移除這一則嗎？已經歸入軌道的內容會留著。",
    "horizon.forgetFailed": "無法移除：{message}",
    "horizon.promoteFailed": "無法歸入：{message}",
    "horizon.captureFailed": "收不進來：{message}",
    "horizon.distilFailed": "無法摘要：{message}",
    "askH.title": "問問你收過的東西",
    "askH.label": "問題",
    "askH.placeholder": "對你收過的東西提問…",
    "askH.scope": "從哪裡讀",
    "askH.everything": "全部",
    "askH.addScope": "選擇要讀哪些（也可以輸入 /）",
    "askH.pickerLabel": "要讀哪些",
    "askH.orbits": "軌道",
    "askH.pickBack": "Esc 返回",
    "askH.keyPreview": "預覽",
    "askH.keyAsk": "提問",
    "askH.keyNewline": "換行",
    "askH.keyCommands": "指令",
    "askH.keyMove": "移動",
    "askH.keyChoose": "選擇",
    "askH.keyBack": "返回",
    "askH.pickHint": "↑ ↓ 移動，Enter 選擇，Esc 返回或關閉。",
    "askH.pickNone": "沒有符合的名稱。",
    "askH.pickNothing": "還沒有標籤、實體或軌道。標籤和實體來自摘要。",
    "askH.tags": "標籤",
    "askH.entities": "實體",
    "askH.check": "看看會讀哪些",
    "askH.send": "提問",
    "askH.dismiss": "先不要",
    "askH.plan": "會讀這個範圍 {total} 項裡的 {count} 項。",
    "askH.planAll": "會讀這個範圍全部 {count} 項。",
    "askH.planMatched": "挑的是跟問題最相關的。",
    "askH.planRecent": "問題裡的字在這裡都找不到，所以改讀最新的幾項。",
    "askH.planRecentTooLarge": "找到的東西都太大，所以改讀最新的幾項。",
    "askH.planSkipped": "有 {n} 項太大，沒有放進來。",
    "askH.planCost": "提問會跑一次模型，要花費用。",
    "askH.planEmpty": "這個範圍裡還沒有能讀的東西。",
    "askH.planTooLarge": "這個範圍裡的東西都太大，一次提問讀不完。",
    "askH.planMore": "還有 {n} 項",
    "askH.readCount": "讀了 {n} 項",
    "askH.sources": "讀過的收錄",
    "askH.history": "之前問過的",
    "askH.remove": "移除這個問題",
    "askH.stillRunning": "還有一個問題在跑",
    "askH.stopped": "已停止，沒有留下紀錄。",
    "askH.askOrbit": "在這個軌道裡問",
    "askH.chipOrbit": "軌道：{name}",
    "askH.chipEntity": "實體：{name}",
    "askH.chipEverywhere": "{name}（所有軌道）",
    "askH.orbitBusy": "這個軌道還在回答上一個問題。你的問題已經放進它的輸入框，等回答完再送出。",
    "askH.orbitEmpty": "這個軌道還沒有來源。你的問題已經放進它的輸入框。",
    "askH.close": "關閉",
    "askH.more": "其他標籤與實體",
    "askH.moreChip": "＋ 其他標籤或實體",
    "askH.hint": "按 Enter 先看看會讀哪些，不花錢；確認後才真的提問。",
    "askH.hintOrbit": "按 Enter 直接在這個軌道的對話裡提問，會跑一次付費的模型。",
    "mode.label": "檢視方式",
    "mode.map": "星圖",
    "mode.list": "清單",
    "mode.graph": "知識圖",
    "mode.cols": "三欄",
    "map.lenses": "標籤",
    "map.empty": "收進第一樣東西，星圖就會開始長出來。",
    "map.legendDone": "已摘要",
    "map.legendPending": "還沒摘要",
    "map.legendLocal": "還沒登記到視界",
    "map.holeLabel": "視界：{n} 項還沒歸入軌道",
    "map.moonLocal": "還沒登記到視界",
    "map.moonFailed": "讀取失敗",
    "map.moonReading": "讀取中",
    "map.moonSummarising": "摘要中",
    "map.closeCard": "關閉",
    "map.fileInto": "歸入…",
    "map.filed": "收進「{name}」了。",
    "map.undo": "復原",
    "map.moved": "搬到「{name}」了。",
    "map.moveCited": "「{from}」裡有 {n} 則已儲存的引用指向這份來源。移出之後，這些引用會變成無法驗證。還是要移動嗎？",
    "map.moveKept": "已加進「{name}」，但沒辦法從「{from}」移出。",
    "map.looseNone": "你收的東西都已經在軌道裡了。",
    "map.looseHelp": "在這裡把每一則歸入軌道，或把它的小點拖到星球上。",
    "map.looseMore": "這裡只列出最新的 {n} 則，清單模式裡有全部。",
    "map.loading": "載入中…",
    "map.filedIn": "在「{where}」裡",
    "map.readInList": "閱讀全文",
    "horizon.filedAt": "{when} 歸入",
    "horizon.trail": "軌跡",
    "horizon.trailCaptured": "收錄",
    "horizon.trailFiled": "歸入「{name}」",
    "horizon.trailSummarised": "摘要完成",
    "horizon.capture.open": "收錄一樣東西（N）",
    "map.bridgeLabel": "「{a}」和「{b}」都提到 {names}",
    "map.bridgeKicker": "兩個軌道共同的主題",
    "map.bridgeNone": "它們已經沒有共同提到的東西了。",
    "map.bridgeShared": "兩邊都提到",
    "map.bridgeAsk": "問兩邊怎麼談「{name}」",
    "map.bridgeQuestion": "「{a}」和「{b}」分別怎麼談「{name}」？兩邊有什麼不同？",
    "panes.details": "詳細資料",
    "panes.resizeDetails": "調整詳細資料欄的寬度",
    "panes.resizeOrbits": "調整軌道清單的寬度",
    "panes.resizeSources": "調整來源欄的寬度",
    "panes.showDetails": "顯示詳細資料欄",
    "map.sectionNames": "它談到的",
    "map.sectionCaptures": "從視界歸入的收錄",
    "map.sectionLocal": "還沒登記到視界",
    "map.localHelp": "有 {n} 份還沒登記到視界，通常是用命令列加的。下次啟動伺服器時會補上，在那之前畫成空心的衛星。",
    "map.notInList": "這則收錄在清單比較後面，一次顯示不到。請在那裡用名稱搜尋。",
    "map.zoom": "縮放",
    "map.zoomIn": "放大",
    "map.zoomOut": "縮小",
    "map.zoomHome": "回到整張星圖",
    "map.legendBridge": "兩個軌道有共同的實體",
    "map.legendDistance": "越靠近中心，越近期有新東西。",
    "map.loose": "{n} 項還沒歸入軌道",
    "map.planetCount": "{n} 份來源",
    "map.planetLabel": "{name}，{n} 份來源",
    "map.cardCounts": "{n} 份來源，其中 {m} 項從視界歸入",
    "map.noEntitiesWaiting": "還沒有實體：這裡有 {n} 則還在等摘要。",
    "map.noCaptures": "沒有實體：這裡的來源是在軌道裡直接加的，實體只會來自從視界歸檔進來、並且摘要過的收錄。",
    "map.noEntitiesNamed": "沒有實體：這裡的摘要沒有提到任何實體。",
    "map.enter": "進入軌道",
    "map.distil": "摘要 {n} 項",
    "map.distilCost": "會跑 {n} 次模型。",
    "map.distilCostRange": "會跑 {min} 次到最多 {max} 次模型，包含最後比對新實體的一次。",
    "map.distilCostLong": "至少跑 {n} 次模型；長文件和比對新實體會再多幾次。",
    "map.distilling": "正在摘要：{done} / {total}",
    "map.distilLost": "連不上伺服器，看不到進度。還在重試。",
    "map.distilElsewhere": "有一個摘要正在跑。",
    "map.aligning": "正在比對新實體和已知的實體",
    "graph.label": "知識圖",
    "graph.entity": "實體",
    "graph.tag": "標籤",
    "graph.orbit": "軌道",
    "graph.entityLabel": "{name}，出現在 {n} 項收錄",
    "graph.inCaptures": "{n} 項收錄",
    "graph.omitted": "還有 {n} 個比較少被提到的實體沒有畫出來。",
    "graph.entitiesHere": "這裡的實體",
    "graph.together": "常一起出現",
    "graph.aliases": "也寫作",
    "suggest.head": "有 {n} 項可以歸入軌道",
    "suggest.anOrbit": "某個軌道",
    "suggest.why": "放進「{where}」：都提到 {why}",
    "suggest.add": "放進去",
    "suggest.no": "不要",
    "suggest.like": "放進「{where}」：內容和「{like}」相似",
    "graph.similarNote": "虛線連起內容相似的收錄，是在你的電腦上比對的。空心方塊是還沒摘要的收錄。",
    "settings.vectors": "本機關聯",
    "settings.vectorsHelp": "在你的電腦上找出內容相似的收錄，還沒摘要的也能連上。不花錢，模型只下載一次。",
    "settings.vectorsDownload": "下載模型（{mb} MB）",
    "settings.vectorsDownloading": "下載中：{done} / {total} MB",
    "settings.vectorsOn": "已開啟",
    "settings.vectorsWorking": "已開啟，正在比對新收錄…",
    "settings.vectorsRemove": "關閉並刪除模型",
    "settings.vectorsRemoveShort": "刪除模型",
    "settings.vectorsDownloadShort": "下載模型",
    "settings.vectorsDownloadLabel": "模型下載進度",
    "settings.vectorsBytes": "{done} / {total} MB",
    "settings.vectorsStop": "停止",
    "settings.vectorsCount": "已比對 {n} 項收錄",
    "settings.vectorsPillOff": "未開啟",
    "settings.vectorsPillOn": "已開啟",
    "settings.vectorsPillWorking": "比對中",
    "settings.vectorsPillDownloading": "下載中 {pct}%",
    "list.sep": "、",
    "graph.unmerge": "拆開",
    "graph.unmergeLabel": "把 {name} 拆開",
    "graph.ask": "問問這個",
    "graph.pending": "{n} 項還沒摘要，所以還連不上任何東西。",
    "graph.noEntities": "這裡還沒有東西提到任何實體。摘要之後才會找出來。",
    "graph.nothingFiled": "這個軌道裡沒有從視界歸入的東西，所以還畫不出圖。它的來源在三欄裡。",
    "err.tokenInvalid": "API token 遺失或過期：請在網址後加上 `?token=` 與伺服器印出的 token，重新開啟本頁。",
    "token.head": "需要 API token",
    "token.why": "Penumbra 跑在你自己的機器上，每一個請求都需要它啟動時印出的 token。這台機器上的每一個瀏覽器都連得到這個伺服器，所以「在本機」並不等於「只有你」。",
    "token.label": "貼上伺服器印出的 token",
    "token.hint": "找不到了嗎？把伺服器停掉再啟動一次，它每次都會印出來。",
    "token.submit": "解鎖",
    "token.desktop": "這個視窗和伺服器的連線中斷了。請選「{restart}」重新連線。",
    "token.bad": "這個 token 不被接受。請確認是這個伺服器這次啟動印出的那一個。",
    "err.promoteNote": "無法升級筆記：{message}",
    "err.deleteNote": "無法刪除筆記：{message}",
    "err.saveNote": "無法儲存筆記：{message}",
    // NO "（錯誤）" PREFIX. The two remaining call sites are a toast and an inline passage, both of
    // which already say "this went wrong" with their own treatment; a literal "(error)" in front of
    // a sentence is the pattern round two removed from the chat, and it outlived that fix on four
    // other surfaces. Those four use `failureBlock` now, which is the Horizon row's shape.
    "err.generic": "{message}",
    "studio.guideFailed": "這一項沒有跑完",
    "podcast.failed": "節目沒有做出來",
    "settings.loadFailed": "設定讀不出來",
    "sources.viewFailed": "這個來源打不開",
    "err.steps": "⌁ {n} 步",
  },
};

const UI_LANG_KEY = "penumbra-ui-lang";

function normalizeUiLang(raw) {
  if (!raw) return null;
  const value = String(raw).toLowerCase();
  // Traditional Chinese is `zh-Hant`, `zh-TW`, `zh-HK`, `zh-MO`. Simplified (`zh-CN`, `zh-Hans`)
  // deliberately does NOT match: shipping Traditional text to a Simplified reader would be worse
  // than English, and this project's own audience asked for Traditional specifically.
  if (/^zh(-|_)?(hant|tw|hk|mo)/.test(value)) return "zh-Hant";
  if (value === "zh-hant") return "zh-Hant";
  if (value.startsWith("en")) return "en";
  return null;
}

function uiLang() {
  const stored = localStorage.getItem(UI_LANG_KEY);
  if (stored && STRINGS[stored]) return stored;
  for (const candidate of navigator.languages || [navigator.language]) {
    const found = normalizeUiLang(candidate);
    if (found) return found;
  }
  return "en";
}

function setUiLang(code) {
  if (!STRINGS[code]) return;
  localStorage.setItem(UI_LANG_KEY, code);
  document.documentElement.lang = code;
  applyStaticI18n();
  window.dispatchEvent(new CustomEvent("ui-lang-changed", { detail: { lang: code } }));
}

// `fallback` is the ENGLISH source text, passed at the call site rather than kept in a second
// dictionary: `en` stays empty above, so the English UI is whatever the markup and the code already
// say and can never drift out of sync with a translation table nobody updated.
function t(key, fallback, vars) {
  const table = STRINGS[uiLang()] || {};
  let text = table[key];
  if (text === undefined) text = fallback !== undefined ? fallback : key;
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.split(`{${name}}`).join(String(value));
    }
  }
  return text;
}

// Static markup carries `data-i18n` (text), `data-i18n-title` and `data-i18n-placeholder`. The
// element's EXISTING content is the English fallback, so `index.html` stays readable on its own.
function applyStaticI18n(root) {
  const scope = root || document;
  scope.querySelectorAll("[data-i18n]").forEach((el) => {
    if (el.dataset.i18nSource === undefined) el.dataset.i18nSource = el.textContent.trim();
    el.textContent = t(el.dataset.i18n, el.dataset.i18nSource);
  });
  scope.querySelectorAll("[data-i18n-title]").forEach((el) => {
    if (el.dataset.i18nTitleSource === undefined) el.dataset.i18nTitleSource = el.title;
    el.title = t(el.dataset.i18nTitle, el.dataset.i18nTitleSource);
  });
  scope.querySelectorAll("[data-i18n-tip]").forEach((el) => {
    // `data-tip` drives this project's OWN tooltip (instant, styled, animated with the hover
    // effect) rather than the native `title`, which the browser delays about a second and renders
    // in its own chrome — the delay is what made the siblings' hover help feel snappier than ours.
    if (el.dataset.i18nTipSource === undefined) el.dataset.i18nTipSource = el.dataset.tip || "";
    el.dataset.tip = t(el.dataset.i18nTip, el.dataset.i18nTipSource);
  });
  //: **`aria-label`, which had no route at all.** Twelve controls in `index.html` carried a
  //: hardcoded English one, and `aria-label` OVERRIDES both the element's text and its `title` —
  //: so under `lang="zh-Hant"`, which is this product's default interface language for a Chinese
  //: reader, a screen reader announced "Go to the Horizon", "Settings", "Toggle theme", "Capture",
  //: "Ask", "Close". The wordmark's `title` was correctly translated and lost to its own label.
  //: None of them carried `lang="en"` either, so a Chinese voice read them phonetically.
  //:
  //: Controls built in JS already go through `t()`; this is the static half catching up.
  scope.querySelectorAll("[data-i18n-label]").forEach((el) => {
    if (el.dataset.i18nLabelSource === undefined) {
      el.dataset.i18nLabelSource = el.getAttribute("aria-label") || "";
    }
    el.setAttribute("aria-label", t(el.dataset.i18nLabel, el.dataset.i18nLabelSource));
  });
  scope.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    if (el.dataset.i18nPlaceholderSource === undefined) {
      el.dataset.i18nPlaceholderSource = el.placeholder;
    }
    el.placeholder = t(el.dataset.i18nPlaceholder, el.dataset.i18nPlaceholderSource);
  });
  scope.querySelectorAll("[data-i18n-html]").forEach((el) => {
    // Rich static copy. The body is a plain `textContent` assignment, which would FLATTEN any
    // markup — the route is currently unused (no element in `index.html` carries the attribute) and
    // an earlier comment here described a template-rebuilding mechanism that was never written.
    // Kept because `textContent` is the safe half of that idea (invariant 29); if a translated
    // sentence ever needs inline markup, this has to be built, not assumed.
    if (el.dataset.i18nHtmlSource === undefined) el.dataset.i18nHtmlSource = el.textContent.trim();
    const translated = t(el.dataset.i18nHtml, el.dataset.i18nHtmlSource);
    el.textContent = translated;
  });
}
