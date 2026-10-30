// Tatsat Real Estate · Talk to Aditi — browser client.
// Uses Pipecat's official JS client SDK (bundled in ./vendor) over SmallWebRTC.

import { PipecatClient, SmallWebRTCTransport } from "./vendor/pipecat-client.js";

// ---------------------------------------------------------------------------
// i18n
// ---------------------------------------------------------------------------

const STRINGS = {
  en: {
    brandSub: "Real Estate · Ahmedabad",
    role: "Property advisor",
    agentName: "Aditi",
    subtitle: "Find a home, estimate an EMI or book a site visit, just by talking.",
    start: "Start call",
    end: "End call",
    hint: "Allow the microphone when asked. You can interrupt Aditi at any time.",
    conversation: "Conversation",
    results: "Shortlist",
    activity: "Activity",
    latency: "Response",
    emptyTranscript: "Start a call and say hello.",
    tryThis: "Try: “I want to buy a 3 BHK in Bopal under 90 lakh.”",
    emptyResults: "Matching homes, EMI estimates and bookings appear here as you talk.",
    status: {
      idle: "Ready",
      connecting: "Connecting…",
      listening: "Listening",
      thinking: "Thinking…",
      speaking: "Speaking",
      ended: "Call ended",
    },
    you: "You",
    agent: "Aditi",
    interrupted: "interrupted",
    exact: "Matches",
    closest: "Closest options",
    forSale: "For sale",
    forRent: "For rent",
    sqft: "sq ft",
    emiTitle: "EMI estimate",
    perMonth: "per month",
    loan: "Loan",
    rate: "Rate",
    tenure: "Tenure",
    years: "years",
    totalInterest: "Total interest",
    bookingTitle: "Site visit confirmed",
    property: "Property",
    date: "Date",
    time: "Time",
    name: "Name",
    phone: "Phone",
    slotTaken: "Slot unavailable",
    tryInstead: "Aditi will suggest",
    details: "Details",
    switchedTo: "Continuing in English",
    noLog: "Tool calls appear here.",
    micError: "Microphone blocked. Allow mic access in the browser and try again.",
    connectError: "Couldn't connect to the assistant.",
    setupError: "Setup needed: add your API keys to the .env file, save, and reload this page.",
    serverDown: "Can't reach the server. Is it still running?",
    backupModel: "Switched to backup model",
    tryAsking: "Try asking",
    followupSent: "Sent on WhatsApp",
    followupPreview: "Follow-up message ready",
    followupFailed: "WhatsApp didn't deliver it",
    followupTo: "to",
    openWhatsapp: "Open in WhatsApp",
    followupLine: "Follow-up",
    visitRescheduled: "Visit rescheduled",
    visitCancelled: "Visit cancelled",
    yourVisits: "Your visits",
    noVisits: "No upcoming visits for this number.",
    summaryTitle: "Call summary",
    duration: "Duration",
    language: "Language",
    searched: "Searched",
    shortlisted: "Homes discussed",
    emiLine: "EMI estimate",
    visitsLine: "Site visits",
    nothingYet: "Nothing was searched or booked on this call.",
    close: "Close",
    suggestions: [
      ["3 BHK in Bopal under 90 lakh", "I want to buy a 3 BHK in Bopal under 90 lakh."],
      ["2 BHK to rent in Satellite", "I'm looking for a 2 BHK on rent in Satellite, up to 30 thousand a month."],
      ["EMI on a 70 lakh loan", "What would the EMI be on a 70 lakh home loan for 20 years?"],
      ["Book a visit tomorrow, 11 AM", "I'd like to visit Sapna Greens tomorrow at 11 AM. My name is Asha and my number is 98765 43210."],
      ["Check my booking", "Can you check my site visit booking? My number is 98765 43210."],
      ["WhatsApp me the options", "Can you send these options to my WhatsApp? My number is 98765 43210."],
    ],
  },
  hi: {
    brandSub: "रियल एस्टेट · अहमदाबाद",
    role: "प्रॉपर्टी सलाहकार",
    agentName: "अदिति",
    subtitle: "बोलकर घर ढूंढिए, EMI जानिए और साइट विज़िट बुक कीजिए।",
    start: "कॉल शुरू करें",
    end: "कॉल खत्म करें",
    hint: "पूछे जाने पर माइक्रोफ़ोन की अनुमति दें। आप अदिति को कभी भी बीच में टोक सकते हैं।",
    conversation: "बातचीत",
    results: "शॉर्टलिस्ट",
    activity: "गतिविधि",
    latency: "रिस्पॉन्स",
    emptyTranscript: "कॉल शुरू करें और नमस्ते कहें।",
    tryThis: "कहकर देखिए: “मुझे बोपल में 90 लाख तक का 3 BHK फ़्लैट चाहिए।”",
    emptyResults: "बात करते समय मिलते-जुलते घर, EMI और बुकिंग यहाँ दिखेंगी।",
    status: {
      idle: "तैयार",
      connecting: "कनेक्ट हो रहा है…",
      listening: "सुन रही हूँ",
      thinking: "सोच रही हूँ…",
      speaking: "बोल रही हूँ",
      ended: "कॉल समाप्त",
    },
    you: "आप",
    agent: "अदिति",
    interrupted: "बीच में रोका",
    exact: "मिलान",
    closest: "क़रीबी विकल्प",
    forSale: "बिक्री",
    forRent: "किराया",
    sqft: "वर्ग फ़ुट",
    emiTitle: "EMI अनुमान",
    perMonth: "महीना",
    loan: "लोन",
    rate: "ब्याज",
    tenure: "अवधि",
    years: "साल",
    totalInterest: "कुल ब्याज",
    bookingTitle: "साइट विज़िट कन्फ़र्म",
    property: "प्रॉपर्टी",
    date: "तारीख़",
    time: "समय",
    name: "नाम",
    phone: "फ़ोन",
    slotTaken: "स्लॉट अवेलेबल नहीं",
    tryInstead: "अदिति ये विकल्प सुझाएगी",
    details: "विवरण",
    switchedTo: "अब हिंदी में बातचीत",
    noLog: "टूल कॉल यहाँ दिखेंगे।",
    micError: "माइक्रोफ़ोन ब्लॉक है। ब्राउज़र में अनुमति दें और फिर कोशिश करें।",
    connectError: "असिस्टेंट से कनेक्ट नहीं हो पाया।",
    setupError: "सेटअप बाकी है: .env फ़ाइल में API keys डालें, सेव करें और पेज रीलोड करें।",
    serverDown: "सर्वर से कनेक्ट नहीं हो पा रहा। क्या वह चल रहा है?",
    backupModel: "बैकअप मॉडल पर स्विच किया",
    tryAsking: "पूछकर देखिए",
    followupSent: "WhatsApp पर भेजा गया",
    followupPreview: "फ़ॉलो-अप मैसेज तैयार",
    followupFailed: "WhatsApp पर नहीं पहुँचा",
    followupTo: "को",
    openWhatsapp: "WhatsApp में खोलें",
    followupLine: "फ़ॉलो-अप",
    visitRescheduled: "विज़िट का समय बदला",
    visitCancelled: "विज़िट रद्द",
    yourVisits: "आपकी विज़िट",
    noVisits: "इस नंबर पर कोई आने वाली विज़िट नहीं है।",
    summaryTitle: "कॉल सारांश",
    duration: "अवधि",
    language: "भाषा",
    searched: "खोज",
    shortlisted: "जिन घरों पर बात हुई",
    emiLine: "EMI अनुमान",
    visitsLine: "साइट विज़िट",
    nothingYet: "इस कॉल पर कुछ खोजा या बुक नहीं किया गया।",
    close: "बंद करें",
    suggestions: [
      ["बोपल में 90 लाख तक 3 BHK", "मुझे बोपल में 90 लाख तक का 3 BHK फ़्लैट ख़रीदना है।"],
      ["सैटेलाइट में किराये पर 2 BHK", "मुझे सैटेलाइट में किराये पर 2 BHK चाहिए, 30 हज़ार महीने तक।"],
      ["70 लाख के लोन की EMI", "70 लाख के होम लोन पर 20 साल के लिए EMI कितनी होगी?"],
      ["कल 11 बजे विज़िट बुक करें", "मुझे कल सुबह 11 बजे सपना ग्रीन्स देखना है। मेरा नाम आशा है और नंबर 98765 43210 है।"],
      ["मेरी बुकिंग देखें", "मेरी साइट विज़िट बुकिंग चेक कर दीजिए, मेरा नंबर 98765 43210 है।"],
      ["ऑप्शन WhatsApp पर भेजें", "ये ऑप्शन मेरे WhatsApp पर भेज दीजिए, मेरा नंबर 98765 43210 है।"],
    ],
  },
};

const $ = (sel) => document.querySelector(sel);
const els = {
  callBtn: $("#call-btn"),
  callBtnText: $("#call-btn-text"),
  status: $("#status"),
  statusText: $("#status-text"),
  orbWrap: $("#orb-wrap"),
  orb: $("#orb"),
  transcript: $("#transcript"),
  transcriptEmpty: $("#transcript-empty"),
  results: $("#results"),
  resultsEmpty: $("#results-empty"),
  toollog: $("#toollog"),
  toollogCount: $("#toollog-count"),
  latency: $("#latency"),
  latencyValue: $("#latency-value"),
  latencyStages: $("#latency-stages"),
  langBadge: $("#lang-badge"),
  langPicker: $("#lang-picker"),
  audio: $("#bot-audio"),
  toasts: $("#toasts"),
  banner: $("#config-banner"),
  stackChip: $("#stack-chip"),
  suggestions: $("#suggestions"),
  summary: $("#summary"),
  summaryBody: $("#summary-body"),
};

const state = {
  lang: localStorageGet("aditi-lang") || "en",
  status: "idle",
  client: null,
  inCall: false,
  userSpeaking: false,
  botSpeaking: false,
  userStoppedAt: null,
  latencies: [],
  userMsg: null,
  botMsg: null,
  toolCount: 0,
  languageLocked: false,
  stages: { stt: null, llm: null, tts: null },
  localLevel: 0,
  remoteLevel: 0,
  pendingAsk: null,
  greeted: false,
  session: null,
};

function newSession() {
  return { start: Date.now(), searches: [], homes: new Map(), emi: null, visits: new Map(), followup: null, languages: new Set([state.lang]) };
}

function t(key) {
  return STRINGS[state.lang][key] ?? STRINGS.en[key] ?? key;
}

function localStorageGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}
function localStorageSet(key, value) {
  try { localStorage.setItem(key, value); } catch { /* private mode */ }
}

function applyLanguage(lang) {
  state.lang = lang === "hi" ? "hi" : "en";
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const value = t(el.dataset.i18n);
    if (typeof value === "string") el.textContent = value;
  });
  els.langPicker.querySelectorAll("button").forEach((b) => {
    b.setAttribute("aria-checked", String(b.dataset.lang === state.lang));
  });
  els.langBadge.textContent = state.lang === "hi" ? "हिंदी" : "English";
  els.callBtnText.textContent = state.inCall ? t("end") : t("start");
  setStatus(state.status);
  if (!els.toollog.children.length || els.toollog.querySelector(".empty-log")) renderEmptyLog();
  renderSuggestions();
}

// ---------------------------------------------------------------------------
// Status + voice visual
// ---------------------------------------------------------------------------

function setStatus(next) {
  state.status = next;
  els.status.dataset.state = next;
  els.statusText.textContent = t("status")[next] ?? next;
  els.orbWrap.dataset.mode = next;
}

function refreshStatus() {
  if (!state.inCall) return;
  if (state.botSpeaking) setStatus("speaking");
  else if (state.userSpeaking) setStatus("listening");
  else if (state.status !== "thinking" && state.status !== "connecting") setStatus("listening");
}

// A thin ring with a single waveform inside: bronze when Aditi speaks, green
// when the caller speaks, a slow arc while thinking or connecting.
const COLORS = {
  ink: [29, 28, 26],
  line: [212, 204, 190],
  accent: [156, 122, 75],
  user: [47, 79, 70],
  muted: [138, 133, 123],
};

function startVisual() {
  const canvas = els.orb;
  const ctx = canvas.getContext("2d");
  const size = canvas.width;
  const c = size / 2;
  const radius = size * 0.44;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let energy = 0;
  let color = [...COLORS.muted];
  let arc = 0;

  const rgba = (rgb, a) => `rgba(${rgb.map(Math.round).join(",")},${a})`;

  function frame(now) {
    const time = reduceMotion ? 0 : now / 1000;
    const mode = state.inCall ? state.status : state.status === "connecting" ? "connecting" : "idle";
    const target = mode === "speaking" ? COLORS.accent : mode === "listening" ? COLORS.user : COLORS.muted;
    color = color.map((v, i) => v + (target[i] - v) * 0.08);

    let level = 0;
    if (mode === "speaking") level = 0.25 + state.remoteLevel * 2.2;
    else if (mode === "listening") level = 0.04 + state.localLevel * 3;
    energy += (Math.min(level, 1) - energy) * 0.18;

    ctx.clearRect(0, 0, size, size);

    // Soft fill that breathes with the voice.
    ctx.beginPath();
    ctx.arc(c, c, radius, 0, Math.PI * 2);
    ctx.fillStyle = rgba(color, 0.04 + energy * 0.08);
    ctx.fill();

    // Ring
    ctx.lineWidth = 2;
    ctx.strokeStyle = rgba(COLORS.line, 1);
    ctx.stroke();

    // Thinking / connecting: a slow arc travelling around the ring.
    if (mode === "thinking" || mode === "connecting") {
      arc += reduceMotion ? 0 : 0.035;
      ctx.beginPath();
      ctx.arc(c, c, radius, arc, arc + Math.PI * 0.45);
      ctx.strokeStyle = rgba(mode === "thinking" ? COLORS.accent : COLORS.muted, 0.9);
      ctx.lineWidth = 3;
      ctx.lineCap = "round";
      ctx.stroke();
    }

    // Waveform across the middle, tapered at both ends.
    const width = radius * 1.3;
    const left = c - width / 2;
    const amp = radius * 0.32 * energy;
    const layers = [
      { phase: 0, alpha: 0.95, freq: 2.2, speed: 2.4, scale: 1 },
      { phase: 1.7, alpha: 0.35, freq: 3.1, speed: 1.7, scale: 0.7 },
    ];
    for (const layer of layers) {
      ctx.beginPath();
      for (let i = 0; i <= 120; i++) {
        const x = i / 120;
        const taper = Math.sin(Math.PI * x) ** 2;
        const y =
          Math.sin(x * Math.PI * 2 * layer.freq + time * layer.speed + layer.phase) * 0.7 +
          Math.sin(x * Math.PI * 2 * layer.freq * 1.9 - time * layer.speed * 1.3) * 0.3;
        const px = left + x * width;
        const py = c + y * amp * taper * layer.scale;
        i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
      }
      ctx.strokeStyle = rgba(color, layer.alpha);
      ctx.lineWidth = 2.5;
      ctx.lineCap = "round";
      ctx.stroke();
    }

    state.localLevel *= 0.88;
    state.remoteLevel *= 0.88;
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

// ---------------------------------------------------------------------------
// Transcript
// ---------------------------------------------------------------------------

function hideTranscriptEmpty() {
  els.transcriptEmpty?.remove();
}

function scrollTranscript() {
  els.transcript.scrollTop = els.transcript.scrollHeight;
}

function nowLabel() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function createMessage(role) {
  hideTranscriptEmpty();
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = `${role === "bot" ? t("agent") : t("you")} · ${nowLabel()}`;
  const text = document.createElement("div");
  text.className = "text";
  wrap.append(who, text);
  els.transcript.append(wrap);
  scrollTranscript();
  return { wrap, bubble: text, finalText: "", segments: new Map(), autoId: 0, interrupted: false };
}

function systemLine(text) {
  hideTranscriptEmpty();
  const line = document.createElement("div");
  line.className = "system-line";
  line.textContent = text;
  els.transcript.append(line);
  scrollTranscript();
}

function onUserTranscript(data) {
  const text = (data?.text || "").trim();
  if (!text) return;
  if (!state.userMsg) state.userMsg = createMessage("user");
  const msg = state.userMsg;
  if (data.final) {
    msg.finalText = (msg.finalText ? msg.finalText + " " : "") + text;
    msg.bubble.textContent = msg.finalText;
    // A new user turn means Aditi's next words go in a new message.
    state.botMsg = null;
  } else {
    msg.bubble.innerHTML = "";
    if (msg.finalText) msg.bubble.append(document.createTextNode(msg.finalText + " "));
    const interim = document.createElement("span");
    interim.className = "interim";
    interim.textContent = text;
    msg.bubble.append(interim);
  }
  scrollTranscript();
}

function renderBotMessage(msg) {
  msg.bubble.innerHTML = "";
  for (const seg of msg.segments.values()) {
    const spoken = seg.spoken || "";
    if (spoken && seg.text.startsWith(spoken)) {
      msg.bubble.append(document.createTextNode(spoken));
      const rest = seg.text.slice(spoken.length);
      if (rest) {
        const span = document.createElement("span");
        span.className = "pending";
        span.textContent = rest;
        msg.bubble.append(span);
      }
    } else if (seg.done) {
      msg.bubble.append(document.createTextNode(seg.text));
    } else {
      const span = document.createElement("span");
      span.className = "pending";
      span.textContent = seg.text;
      msg.bubble.append(span);
    }
    msg.bubble.append(document.createTextNode(" "));
  }
  if (msg.interrupted) {
    const tag = document.createElement("span");
    tag.className = "interrupted-tag";
    tag.textContent = t("interrupted");
    msg.bubble.append(tag);
  }
}

function looseText(text) {
  return String(text || "").replace(/[\s\-*•#_]+/g, " ").trim().toLowerCase();
}

function onBotOutput(data) {
  if (!data || data.will_be_spoken === false) return;
  const text = data.text || "";
  if (!state.botMsg) {
    state.botMsg = createMessage("bot");
    state.userMsg = null;
  }
  const msg = state.botMsg;
  const agg = data.aggregated_by;
  if (agg === "word" || agg === "token") {
    // Older servers stream words; append them to a single running segment.
    const seg = msg.segments.get("words") || { text: "", spoken: "", done: true };
    seg.text = (seg.text + " " + text).trim();
    seg.spoken = seg.text;
    msg.segments.set("words", seg);
  } else {
    // Pipecat announces each sentence before it's spoken ("new") and again once
    // spoken ("completed"), and the two can carry different segment ids, so fall
    // back to matching the pending sentence by its text.
    const id = data.segment_id ?? `auto-${msg.autoId++}`;
    // The spoken copy can also differ slightly (bullets, markdown and Hindi fixes are
    // cleaned before speech), so compare loosely and otherwise take the oldest
    // sentence still waiting: sentences are spoken in order.
    let seg = msg.segments.get(id);
    if (!seg && text) {
      const loose = looseText(text);
      const pending = [...msg.segments.values()].filter((c) => !c.done);
      seg = pending.find((c) => looseText(c.text) === loose);
      if (!seg && data.spoken_status === "completed") seg = pending[0];
    }
    if (!seg) {
      seg = { text: "", spoken: "", done: false };
      msg.segments.set(id, seg);
    }
    if (text) seg.text = text;
    if (data.spoken_status === "completed" || data.spoken_status === undefined) {
      seg.done = true;
      seg.spoken = seg.text;
    } else if (data.spoken_progress) {
      seg.spoken = data.spoken_progress.accumulated_text || "";
    }
  }
  renderBotMessage(msg);
  scrollTranscript();
}

function markInterrupted() {
  if (state.botMsg && state.botSpeaking) {
    state.botMsg.interrupted = true;
    renderBotMessage(state.botMsg);
    state.botMsg = null;
  }
}

// ---------------------------------------------------------------------------
// Shortlist panel
// ---------------------------------------------------------------------------

// Line drawings, stroked in ink: tower, villa, bungalow.
const ICONS = {
  apartment: '<svg viewBox="0 0 32 32"><path d="M8 28V6h11v22M19 12h5v16M5 28h22M11.5 10h1M15 10h1M11.5 14h1M15 14h1M11.5 18h1M15 18h1M11.5 22h1M15 22h1M21.5 16h.5M21.5 20h.5"/></svg>',
  villa: '<svg viewBox="0 0 32 32"><path d="M4 15 16 6l12 9M7 13v15h18V13M5 28h22M13 28v-7h6v7M10 17h3M19 17h3"/></svg>',
  bungalow: '<svg viewBox="0 0 32 32"><path d="M3 17 16 8l13 9M6 15v13h20V15M4 28h24M14 28v-6h4v6M9 19h3M20 19h3"/></svg>',
};

function typeIcon(type) {
  const key = String(type || "").toLowerCase();
  if (key.includes("villa") || key.includes("विला")) return ICONS.villa;
  if (key.includes("bungalow") || key.includes("बंगला")) return ICONS.bungalow;
  return ICONS.apartment;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function addGroup(node) {
  els.resultsEmpty?.remove();
  els.results.prepend(node);
  els.results.scrollTop = 0;
  while (els.results.children.length > 8) els.results.lastElementChild.remove();
}

function group(title, extra = "") {
  const node = document.createElement("section");
  node.className = "group";
  if (title) node.innerHTML = `<div class="group-head"><span class="group-title">${escapeHtml(title)}</span>${extra}</div>`;
  return node;
}

function propertyCard(item, index = 0) {
  const card = document.createElement("article");
  card.className = "card prop";
  card.dataset.id = item.id;
  card.style.animationDelay = `${index * 80}ms`;
  const amenities = (item.amenities || []).slice(0, 3).map(escapeHtml).join(" · ");
  card.innerHTML = `
    <div class="prop-art">
      ${typeIcon(item.type)}
      <span class="bhk">${escapeHtml(item.bhk)} BHK</span>
    </div>
    <div class="prop-body">
      <div class="prop-top">
        <div class="prop-title">${escapeHtml(item.title)}</div>
        <span class="prop-id">${escapeHtml(item.id)}</span>
      </div>
      <div class="prop-loc">${escapeHtml(item.area)} · ${escapeHtml(item.type)}</div>
      <div class="prop-price-row">
        <span class="prop-price">${escapeHtml(item.price)}</span>
        <span class="tag">${item.purpose === "rent" ? t("forRent") : t("forSale")}</span>
      </div>
      <div class="prop-meta">${Number(item.size_sqft).toLocaleString("en-IN")} ${t("sqft")} · ${escapeHtml(item.furnishing)} · ${escapeHtml(item.possession)}</div>
      ${amenities ? `<div class="chips">${amenities}</div>` : ""}
    </div>`;
  return card;
}

function showProperties(msg) {
  const pill = `<span class="pill ${msg.exact ? "exact" : "closest"}">${msg.exact ? t("exact") : t("closest")}</span>`;
  const node = group(msg.query, pill);
  const cards = document.createElement("div");
  cards.className = "cards";
  (msg.items || []).forEach((item, i) => cards.append(propertyCard(item, i)));
  node.append(cards);
  addGroup(node);
}

function showPropertyDetail(msg) {
  const id = msg.item?.id;
  document.querySelectorAll(".card.highlight").forEach((c) => c.classList.remove("highlight"));
  const existing = id && els.results.querySelector(`.card.prop[data-id="${CSS.escape(id)}"]`);
  if (existing) {
    existing.classList.add("highlight");
    existing.scrollIntoView({ behavior: "smooth", block: "nearest" });
    return;
  }
  const node = group(t("details"));
  const card = propertyCard(msg.item);
  card.classList.add("highlight");
  node.append(card);
  addGroup(node);
}

function showEmi(msg) {
  const node = group("");
  node.innerHTML = `
    <article class="card emi">
      <div class="label">${t("emiTitle")}</div>
      <div class="emi-value">${escapeHtml(msg.emi)} <small>${t("perMonth")}</small></div>
      <div class="figures">
        <div><span>${t("loan")}</span><b>${escapeHtml(msg.loan)}</b></div>
        <div><span>${t("rate")}</span><b>${escapeHtml(msg.rate)}%</b></div>
        <div><span>${t("tenure")}</span><b>${escapeHtml(msg.years)} ${t("years")}</b></div>
      </div>
      <div class="emi-foot">${t("totalInterest")} ${escapeHtml(msg.total_interest)}</div>
    </article>`;
  addGroup(node);
}

function bookingLabel(status) {
  if (status === "rescheduled") return t("visitRescheduled");
  if (status === "cancelled") return t("visitCancelled");
  return t("bookingTitle");
}

function showVisits(msg) {
  const node = group(t("yourVisits"));
  const cards = document.createElement("div");
  cards.className = "cards";
  if (!msg.items?.length) {
    cards.innerHTML = `<article class="card slot"><p>${t("noVisits")}</p></article>`;
  }
  for (const item of msg.items || []) {
    const card = document.createElement("article");
    card.className = "card booking compact";
    card.innerHTML = `
      <div class="booking-code small">${escapeHtml(item.code)}</div>
      <div>${escapeHtml(item.property)}, ${escapeHtml(item.area)}</div>
      <div class="muted">${escapeHtml(item.date)} · ${escapeHtml(item.time)}</div>`;
    cards.append(card);
  }
  node.append(cards);
  addGroup(node);
}

function showBooking(msg) {
  const node = group("");
  node.innerHTML = `
    <article class="card booking ${escapeHtml(msg.status || "confirmed")}">
      <div class="label">${bookingLabel(msg.status)}</div>
      <div class="booking-code">${escapeHtml(msg.code)}</div>
      <dl>
        <dt>${t("property")}</dt><dd>${escapeHtml(msg.property)}, ${escapeHtml(msg.area)}</dd>
        <dt>${t("date")}</dt><dd>${escapeHtml(msg.date)}</dd>
        <dt>${t("time")}</dt><dd>${escapeHtml(msg.time)}</dd>
        <dt>${t("name")}</dt><dd>${escapeHtml(msg.name)}</dd>
        <dt>${t("phone")}</dt><dd>${escapeHtml(msg.phone)}</dd>
      </dl>
    </article>`;
  addGroup(node);
}

function showFollowup(msg) {
  const node = group("");
  const label = msg.status === "sent" ? t("followupSent") : msg.status === "failed" ? t("followupFailed") : t("followupPreview");
  node.innerHTML = `
    <article class="card followup ${escapeHtml(msg.status)}">
      <div class="label">${label} ${t("followupTo")} ${escapeHtml(msg.phone)}</div>
      <div class="wa-bubble">${escapeHtml(msg.text)}</div>
      ${msg.status === "failed" && msg.detail ? `<p class="muted">${escapeHtml(msg.detail)}</p>` : ""}
      ${msg.status !== "sent" ? `<a class="wa-link" href="${escapeHtml(msg.link)}" target="_blank" rel="noopener">${t("openWhatsapp")}</a>` : ""}
    </article>`;
  addGroup(node);
}

function showSlotTaken(msg) {
  const node = group("");
  const alts = (msg.alternatives || []).map((a) => `<li>${escapeHtml(a)}</li>`).join("");
  node.innerHTML = `
    <article class="card slot">
      <div class="label">${t("slotTaken")}</div>
      <p>${escapeHtml(msg.property_id)} · ${escapeHtml(msg.requested)}</p>
      ${alts ? `<p>${t("tryInstead")}</p><ul>${alts}</ul>` : ""}
    </article>`;
  addGroup(node);
}

// ---------------------------------------------------------------------------
// Activity log, toasts, latency
// ---------------------------------------------------------------------------

function renderEmptyLog() {
  els.toollog.innerHTML = `<li class="empty-log">${t("noLog")}</li>`;
}

function logTool(msg) {
  els.toollog.querySelector(".empty-log")?.remove();
  const li = document.createElement("li");
  if (msg.ok === false) li.className = "err";
  li.innerHTML = `<time>${nowLabel()}</time><span class="fn">${escapeHtml(msg.name)}</span> → ${escapeHtml(msg.summary)}`;
  els.toollog.prepend(li);
  state.toolCount += 1;
  els.toollogCount.textContent = String(state.toolCount);
}

function toast(text, level = "info") {
  const el = document.createElement("div");
  el.className = `toast ${level}`;
  el.textContent = text;
  els.toasts.append(el);
  setTimeout(() => el.remove(), level === "error" ? 7000 : 4000);
}

function recordLatency(ms) {
  if (ms < 50 || ms > 20000) return;
  state.latencies.push(ms);
  if (state.latencies.length > 5) state.latencies.shift();
  els.latencyValue.textContent = `${(ms / 1000).toFixed(1)} s`;
  els.latency.classList.remove("good", "ok", "slow");
  els.latency.classList.add(ms < 1500 ? "good" : ms < 3000 ? "ok" : "slow");
  const avg = state.latencies.reduce((a, b) => a + b, 0) / state.latencies.length;
  els.latency.title = `Last: ${Math.round(ms)} ms · Avg of last ${state.latencies.length}: ${Math.round(avg)} ms\n(end of your speech → start of Aditi's voice)`;
}

function onMetrics(data) {
  for (const item of data?.ttfb || []) {
    const name = String(item.processor || "");
    const stage = /STT/i.test(name) ? "stt" : /LLM|Switcher/i.test(name) ? "llm" : /TTS/i.test(name) ? "tts" : null;
    if (stage && item.value > 0) state.stages[stage] = item.value;
  }
  const fmt = (v) => (v == null ? "–" : `${v.toFixed(1)}s`);
  const { stt, llm, tts } = state.stages;
  els.latencyStages.textContent = `STT ${fmt(stt)} · LLM ${fmt(llm)} · TTS ${fmt(tts)}`;
}

// ---------------------------------------------------------------------------
// Server messages
// ---------------------------------------------------------------------------

function recordForSummary(msg) {
  const ses = state.session;
  if (!ses) return;
  if (msg.type === "properties") {
    if (msg.query && !ses.searches.includes(msg.query)) ses.searches.push(msg.query);
    for (const item of msg.items || []) ses.homes.set(item.id, item);
  } else if (msg.type === "property_detail" && msg.item) {
    ses.homes.set(msg.item.id, msg.item);
  } else if (msg.type === "emi") {
    ses.emi = msg;
  } else if (msg.type === "booking") {
    ses.visits.set(msg.code, msg);
  } else if (msg.type === "followup") {
    ses.followup = msg;
  } else if (msg.type === "language") {
    ses.languages.add(msg.language);
  }
}

function onServerMessage(msg) {
  if (!msg || typeof msg !== "object") return;
  recordForSummary(msg);
  switch (msg.type) {
    case "properties": return showProperties(msg);
    case "property_detail": return showPropertyDetail(msg);
    case "emi": return showEmi(msg);
    case "booking": return showBooking(msg);
    case "visits": return showVisits(msg);
    case "followup": return showFollowup(msg);
    case "slot_taken": return showSlotTaken(msg);
    case "tool": return logTool(msg);
    case "language":
      applyLanguage(msg.language);
      localStorageSet("aditi-lang", state.lang);
      systemLine(t("switchedTo"));
      return;
    case "notice": return toast(msg.text, msg.level === "error" ? "error" : "info");
    case "llm":
      els.stackChip.textContent = els.stackChip.textContent.replace(/LLM [^·]+/, `LLM ${msg.model} `);
      return toast(`${t("backupModel")}: ${msg.model}`, "info");
    default: console.debug("Unhandled server message", msg);
  }
}

// ---------------------------------------------------------------------------
// Example questions and the end-of-call summary
// ---------------------------------------------------------------------------

function renderSuggestions() {
  els.suggestions.innerHTML = `<span class="suggestions-label">${t("tryAsking")}</span>`;
  for (const [label, text] of t("suggestions")) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "suggestion";
    chip.textContent = label;
    chip.addEventListener("click", () => ask(text));
    els.suggestions.append(chip);
  }
}

function ask(text) {
  if (state.inCall && state.client) {
    state.botMsg = null;
    const msg = createMessage("user");
    msg.bubble.textContent = text;
    state.userMsg = null;
    state.userStoppedAt = performance.now();
    setStatus("thinking");
    state.client.sendClientMessage("ask", { text });
  } else if (!state.client) {
    // Start the call; the question goes out once Aditi has finished her greeting.
    state.pendingAsk = text;
    startCall();
  }
}

function formatDuration(ms) {
  const total = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function showSummary() {
  const ses = state.session;
  state.session = null;
  if (!ses) return;
  const rows = [];
  const langNames = [...ses.languages].map((l) => (l === "hi" ? "हिंदी" : "English")).join(", ");
  rows.push([t("duration"), formatDuration(Date.now() - ses.start)]);
  rows.push([t("language"), langNames]);
  if (ses.searches.length) rows.push([t("searched"), ses.searches.map(escapeHtml).join("<br>")]);
  if (ses.homes.size) {
    rows.push([t("shortlisted"), [...ses.homes.values()].map((h) => `${escapeHtml(h.title)} · ${escapeHtml(h.price)}`).join("<br>")]);
  }
  if (ses.emi) rows.push([t("emiLine"), `${escapeHtml(ses.emi.emi)} ${t("perMonth")} · ${escapeHtml(ses.emi.loan)}, ${escapeHtml(ses.emi.years)} ${t("years")}`]);
  if (ses.visits.size) {
    rows.push([t("visitsLine"), [...ses.visits.values()].map((v) =>
      `${escapeHtml(v.code)} · ${escapeHtml(v.property)}, ${escapeHtml(v.date)} ${escapeHtml(v.time)}${v.status === "cancelled" ? ` (${t("visitCancelled")})` : ""}`).join("<br>")]);
  }
  if (ses.followup) {
    const f = ses.followup;
    const label = f.status === "sent" ? t("followupSent") : f.status === "failed" ? t("followupFailed") : t("followupPreview");
    rows.push([t("followupLine"), `${label} · ${escapeHtml(f.phone)}`]);
  }
  const empty = ses.searches.length || ses.emi || ses.visits.size || ses.followup ? "" : `<p class="summary-empty">${t("nothingYet")}</p>`;
  els.summaryBody.innerHTML = `
    <p class="eyebrow">${t("summaryTitle")}</p>
    <h2 class="summary-title">Tatsat · ${t("agent")}</h2>
    <dl class="summary-list">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>
    ${empty}
    <button type="button" class="call-btn summary-close" id="summary-close">${t("close")}</button>`;
  $("#summary-close").addEventListener("click", () => els.summary.close());
  if (typeof els.summary.showModal === "function") els.summary.showModal();
}

// ---------------------------------------------------------------------------
// Call lifecycle
// ---------------------------------------------------------------------------

function lockLanguage(locked) {
  state.languageLocked = locked;
  els.langPicker.querySelectorAll("button").forEach((b) => (b.disabled = locked));
}

function setInCall(inCall) {
  state.inCall = inCall;
  els.callBtn.classList.toggle("in-call", inCall);
  els.callBtnText.textContent = inCall ? t("end") : t("start");
  lockLanguage(inCall || state.status === "connecting");
}

async function startCall() {
  // Check setup first so a missing key gives a clear message, not "status 400".
  const cfg = await loadConfig();
  if (cfg?.problems?.length) {
    toast(t("setupError"), "error");
    return;
  }
  els.callBtn.disabled = true;
  lockLanguage(true);
  setStatus("connecting");
  state.greeted = false;
  state.userMsg = null;
  state.botMsg = null;

  const client = new PipecatClient({
    transport: new SmallWebRTCTransport(),
    enableMic: true,
    enableCam: false,
    callbacks: {
      onConnected: () => console.info("Transport connected"),
      onBotReady: () => {
        setInCall(true);
        state.session = newSession();
        els.callBtn.disabled = false;
        setStatus("listening");
      },
      onDisconnected: () => endedUi(),
      onTrackStarted: (track, participant) => {
        if (participant?.local || track.kind !== "audio") return;
        els.audio.srcObject = new MediaStream([track]);
        els.audio.play().catch(() => {});
      },
      onUserStartedSpeaking: () => {
        markInterrupted();
        state.userSpeaking = true;
        refreshStatus();
      },
      onUserStoppedSpeaking: () => {
        state.userSpeaking = false;
        state.userStoppedAt = performance.now();
        if (!state.botSpeaking) setStatus("thinking");
      },
      onBotStartedSpeaking: () => {
        state.botSpeaking = true;
        if (state.userStoppedAt) {
          recordLatency(performance.now() - state.userStoppedAt);
          state.userStoppedAt = null;
        }
        setStatus("speaking");
      },
      onBotStoppedSpeaking: () => {
        state.botSpeaking = false;
        if (state.status === "speaking") setStatus("listening");
        if (!state.greeted) {
          state.greeted = true;
          if (state.pendingAsk) {
            const text = state.pendingAsk;
            state.pendingAsk = null;
            ask(text);
          }
        }
      },
      onLLMFunctionCallInProgress: () => {
        if (!state.botSpeaking) setStatus("thinking");
      },
      onUserTranscript: onUserTranscript,
      onBotOutput: onBotOutput,
      onServerMessage: onServerMessage,
      onMetrics: onMetrics,
      onLocalAudioLevel: (level) => { state.localLevel = Math.max(state.localLevel, level); },
      onRemoteAudioLevel: (level) => { state.remoteLevel = Math.max(state.remoteLevel, level); },
      onError: (message) => {
        // Technical details stay in the console and server log; the viewer gets a short note.
        console.error("RTVI error", message);
        if (message?.data?.fatal) toast(t("connectError"), "error");
      },
      onDeviceError: (err) => {
        console.error("Device error", err);
        toast(t("micError"), "error");
      },
    },
  });
  state.client = client;

  try {
    await client.connect({
      webrtcRequestParams: { endpoint: "/api/offer", requestData: { language: state.lang } },
    });
  } catch (err) {
    console.error(err);
    const msg = String(err?.message || err);
    if (/permission|denied|notallowed/i.test(msg)) toast(t("micError"), "error");
    else if (/400/.test(msg)) toast(t("setupError"), "error");
    else toast(t("connectError"), "error");
    await safeDisconnect();
    endedUi(true);
  } finally {
    els.callBtn.disabled = false;
  }
}

async function safeDisconnect() {
  const client = state.client;
  state.client = null;
  if (!client) return;
  try { await client.disconnect(); } catch { /* already closed */ }
}

function endedUi(failed = false) {
  lockLanguage(false);
  state.pendingAsk = null;
  if (!state.inCall && !failed && state.status === "idle") return;
  const wasInCall = state.inCall;
  state.client = null;
  if (wasInCall) showSummary();
  setInCall(false);
  state.userSpeaking = state.botSpeaking = false;
  setStatus(wasInCall ? "ended" : "idle");
  setTimeout(() => { if (!state.inCall && state.status === "ended") setStatus("idle"); }, 2500);
}

async function endCall() {
  els.callBtn.disabled = true;
  await safeDisconnect();
  endedUi();
  els.callBtn.disabled = false;
}

els.callBtn.addEventListener("click", () => (state.inCall || state.client ? endCall() : startCall()));

els.langPicker.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-lang]");
  if (!button || state.inCall || state.languageLocked) return;
  applyLanguage(button.dataset.lang);
  localStorageSet("aditi-lang", state.lang);
});

async function loadConfig() {
  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();
    const tts = cfg.tts_fallback ? `${cfg.tts}→${cfg.tts_fallback}` : cfg.tts;
    const backups = cfg.llm_backups ? `+${cfg.llm_backups}` : "";
    els.stackChip.textContent = `Pipecat · STT ${cfg.stt} · LLM ${cfg.llm}${backups} · TTS ${tts}`;
    els.stackChip.title = cfg.llm_chain ? `LLM chain: ${cfg.llm_chain.join(" → ")}` : "";
    els.banner.hidden = !cfg.problems?.length;
    if (cfg.problems?.length) {
      els.banner.textContent = `Setup needed: open the .env file, paste your API keys, save, then reload this page. (${cfg.problems.join(" · ")})`;
    }
    return cfg;
  } catch {
    toast(t("serverDown"), "error");
    return null;
  }
}

// ?debug exposes the event handlers so the UI can be exercised without a call.
if (new URLSearchParams(location.search).has("debug")) {
  window.aditiDebug = {
    onServerMessage, onUserTranscript, onBotOutput, setStatus, applyLanguage, recordLatency, onMetrics, state,
    // Type to Aditi instead of speaking (for testing without a microphone).
    say: (text) => ask(text),
    showSummary,
  };
}

applyLanguage(state.lang);
setStatus("idle");
els.summary.addEventListener("click", (event) => {
  if (event.target === els.summary) els.summary.close(); // click outside the card
});
startVisual();
loadConfig();
