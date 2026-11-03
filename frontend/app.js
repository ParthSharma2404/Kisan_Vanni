// =====================================================================
// KISAN-VAANI: CHAT-CUM-VOICE HYBRID AGENTIC AI BUDDY
// Turn-Taking Mic Orchestration, 24-Hour Ephemeral Storage, WhatsApp Summary
// =====================================================================

const API_BASE = window.location.protocol.startsWith("http") ? window.location.origin : "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

let activePhone = "";
let sessionId = "";
let socket = null;
let currentAudio = null;

// User Preferred Language (Default: English)
let currentLanguage = localStorage.getItem("kisan_preferred_language") || "en-US";

const LANGUAGE_LABELS = {
  "en-US": "English",
  "hi-IN": "हिन्दी",
  "hinglish": "Hinglish",
  "pa-IN": "ਪੰਜਾਬੀ",
  "mr-IN": "मराठी",
  "te-IN": "తెలుగు",
  "ta-IN": "தமிழ்",
  "gu-IN": "ગુજરાતી",
  "bn-IN": "বাংলা"
};

// Microphone & VAD State
let isRecording = false;
let isAiSpeaking = false;
let audioContext = null;
let mediaStream = null;
let audioSource = null;
let audioProcessor = null;

// VAD Parameters
let isSpeaking = false;
let silenceStartTime = 0;
let speechStartTime = 0;
let audioBufferChunks = [];
let preRollBuffer = [];
const MAX_PRE_ROLL = 12;
let ambientNoiseFloor = 0.008;
const SILENCE_TIMEOUT_MS = 1800; // 1.8s silence window to accommodate natural pauses in Indian speech
const MIN_SPEECH_DURATION_MS = 200;

// DOM Elements
const loginModalOverlay = document.getElementById("loginModalOverlay");
const loginPhoneForm = document.getElementById("loginPhoneForm");
const loginPhoneInput = document.getElementById("loginPhoneInput");
const topUserBadge = document.getElementById("topUserBadge");
const topUserPhoneText = document.getElementById("topUserPhoneText");
const globalStatusDot = document.getElementById("globalStatusDot");
const activeStatusText = document.getElementById("activeStatusText");
const headerWhatsAppBtn = document.getElementById("headerWhatsAppBtn");

const chatFeed = document.getElementById("chatFeed");
const dynamicMessagesContainer = document.getElementById("dynamicMessagesContainer");
const reasoningIndicator = document.getElementById("reasoningIndicator");
const reasoningBadgeText = document.getElementById("reasoningBadgeText");

const turnStatusBar = document.getElementById("turnStatusBar");
const turnIndicatorDot = document.getElementById("turnIndicatorDot");
const turnStatusText = document.getElementById("turnStatusText");

const chatTextForm = document.getElementById("chatTextForm");
const chatTextInput = document.getElementById("chatTextInput");
const sendTextBtn = document.getElementById("sendTextBtn");
const mainMicBtn = document.getElementById("mainMicBtn");
const micIconHolder = document.getElementById("micIconHolder");

const waSummaryModal = document.getElementById("waSummaryModal");
const waSummaryText = document.getElementById("waSummaryText");
const waDirectSendBtn = document.getElementById("waDirectSendBtn");
const waCloseBtn = document.getElementById("waCloseBtn");

// Onboarding & Permissions Gate Elements
const loginNameInput = document.getElementById("loginNameInput");
const btnAllowLocation = document.getElementById("btnAllowLocation");
const permLocationDesc = document.getElementById("permLocationDesc");
const permLocationCard = document.getElementById("permLocationCard");
const btnAllowMic = document.getElementById("btnAllowMic");
const permMicDesc = document.getElementById("permMicDesc");
const permMicCard = document.getElementById("permMicCard");
const skeletonFeed = document.getElementById("skeletonFeed");

// Hyperlocal Weather & Soil Agronomy Elements
const headerWeatherBtn = document.getElementById("headerWeatherBtn");
const weatherHeaderTemp = document.getElementById("weatherHeaderTemp");
const weatherAgronomyModal = document.getElementById("weatherAgronomyModal");
const weatherCloseBtn = document.getElementById("weatherCloseBtn");
const weatherLocSub = document.getElementById("weatherLocSub");
const tileTemp = document.getElementById("tileTemp");
const tileHumidity = document.getElementById("tileHumidity");
const tileWind = document.getElementById("tileWind");
const tileSoilTemp = document.getElementById("tileSoilTemp");
const tileSoilMoisture = document.getElementById("tileSoilMoisture");
const agronomyCardsGrid = document.getElementById("agronomyCardsGrid");

// Multimodal Leaf Disease Scanner Elements
const btnUploadLeaf = document.getElementById("btnUploadLeaf");
const leafFileInput = document.getElementById("leafFileInput");

let activeFarmerName = localStorage.getItem("kisan_auth_name") || "Parth";
let activeLocation = localStorage.getItem("kisan_auth_location") || "Hardaspur, Punjab";
let activeLat = parseFloat(localStorage.getItem("kisan_lat") || "31.2240");
let activeLon = parseFloat(localStorage.getItem("kisan_lon") || "75.7708");

// Strict Anti-Urdu Unicode Firewall (Arabic/Urdu script blocks)
const URDU_ARABIC_REGEX = /[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]/g;

function sanitizeAntiUrdu(text) {
  if (!text) return "";
  return text.replace(URDU_ARABIC_REGEX, "").trim();
}

function showSkeletonFeed() {
  if (skeletonFeed) skeletonFeed.style.display = "flex";
}

function hideSkeletonFeed() {
  if (skeletonFeed) skeletonFeed.style.display = "none";
}

// SVG Icons
const MIC_IDLE_SVG = `
  <svg class="mic-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
    <line x1="12" y1="19" x2="12" y2="23"/>
    <line x1="8" y1="23" x2="16" y2="23"/>
  </svg>
`;

const MIC_LOCKED_SVG = `
  <svg class="mic-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
    <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
  </svg>
`;

// =====================================================================
// SOUND EFFECTS ENGINE (Zero-Latency Web Audio API Synthesizer)
// =====================================================================
const SoundFX = {
  ctx: null,

  init() {
    try {
      if (!this.ctx) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) this.ctx = new AudioCtx();
      }
      if (this.ctx && this.ctx.state === "suspended") {
        this.ctx.resume().catch(() => {});
      }
    } catch (e) {}
  },

  // Tactile, crisp modern pop on user message dispatch
  playSend() {
    try {
      this.init();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(360, now);
      osc.frequency.exponentialRampToValueAtTime(620, now + 0.08);

      gain.gain.setValueAtTime(0.001, now);
      gain.gain.linearRampToValueAtTime(0.12, now + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.11);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start(now);
      osc.stop(now + 0.12);
    } catch (e) {
      console.debug("[SoundFX] playSend error:", e);
    }
  },

  // Gentle, soothing melodic chord on AI response arrival
  playReceive() {
    try {
      this.init();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;

      // Note 1: E5 (659.25 Hz)
      const osc1 = this.ctx.createOscillator();
      const gain1 = this.ctx.createGain();
      osc1.type = "sine";
      osc1.frequency.setValueAtTime(659.25, now);
      gain1.gain.setValueAtTime(0.001, now);
      gain1.gain.linearRampToValueAtTime(0.10, now + 0.02);
      gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.22);
      osc1.connect(gain1);
      gain1.connect(this.ctx.destination);
      osc1.start(now);
      osc1.stop(now + 0.23);

      // Note 2: A5 (880.00 Hz) - staggered slightly (70ms) for warm harmonic lift
      const osc2 = this.ctx.createOscillator();
      const gain2 = this.ctx.createGain();
      osc2.type = "sine";
      osc2.frequency.setValueAtTime(880.0, now + 0.07);
      gain2.gain.setValueAtTime(0.001, now + 0.07);
      gain2.gain.linearRampToValueAtTime(0.09, now + 0.09);
      gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.32);
      osc2.connect(gain2);
      gain2.connect(this.ctx.destination);
      osc2.start(now + 0.07);
      osc2.stop(now + 0.33);
    } catch (e) {
      console.debug("[SoundFX] playReceive error:", e);
    }
  }
};

// =====================================================================
// 0. MULTI-LINGUAL PREFERENCE & SELECTOR
// =====================================================================
function initLanguageSelector() {
  const langSelectorBtn = document.getElementById("langSelectorBtn");
  const langDropdownMenu = document.getElementById("langDropdownMenu");
  const currentLangLabel = document.getElementById("currentLangLabel");
  const langOptions = document.querySelectorAll(".lang-option");

  // Sync initial UI with stored preference
  if (currentLangLabel) {
    currentLangLabel.innerText = LANGUAGE_LABELS[currentLanguage] || "English";
  }

  langOptions.forEach(opt => {
    if (opt.getAttribute("data-lang") === currentLanguage) {
      opt.classList.add("active");
    } else {
      opt.classList.remove("active");
    }
  });

  if (langSelectorBtn && langDropdownMenu) {
    langSelectorBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const isVisible = langDropdownMenu.style.display === "flex";
      langDropdownMenu.style.display = isVisible ? "none" : "flex";
    });

    document.addEventListener("click", (e) => {
      if (!langSelectorBtn.contains(e.target) && !langDropdownMenu.contains(e.target)) {
        langDropdownMenu.style.display = "none";
      }
    });

    langOptions.forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const prevLang = currentLanguage;
        const selectedLang = btn.getAttribute("data-lang");
        const label = btn.getAttribute("data-label") || LANGUAGE_LABELS[selectedLang] || selectedLang;
        
        currentLanguage = selectedLang;
        localStorage.setItem("kisan_preferred_language", currentLanguage);
        
        if (currentLangLabel) currentLangLabel.innerText = label;
        langOptions.forEach(o => o.classList.toggle("active", o === btn));
        langDropdownMenu.style.display = "none";

        stopAnyCurrentAudio();

        // Dispatch set_language to backend WebSocket
        if (socket && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({
            type: "set_language",
            language: currentLanguage
          }));
        }

        console.log(`[Language] User preferred language updated to: ${currentLanguage}`);

        // Always trigger conversation transition so any mixed-language turns are fully harmonized
        transitionConversationLanguage(selectedLang);
      });
    });
  }
}

// =====================================================================
// DYNAMIC CONVERSATION LANGUAGE TRANSITION
// =====================================================================
function showLanguageToast(msg) {
  let toast = document.getElementById("langToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "langToast";
    toast.className = "lang-transition-toast";
    document.body.appendChild(toast);
  }
  toast.innerText = msg;
  toast.classList.add("visible");
  setTimeout(() => {
    toast.classList.remove("visible");
  }, 2600);
}

function renderMessagesInPlace(messages) {
  if (!dynamicMessagesContainer) return;
  dynamicMessagesContainer.innerHTML = "";
  for (const msg of messages) {
    if (msg.role === "user") {
      renderUserMessage(msg.text, false);
    } else {
      renderAiCard(msg.text, msg.extra || {}, false);
    }
  }
  scrollToBottom();
}

async function transitionConversationLanguage(targetLang) {
  const langLabel = LANGUAGE_LABELS[targetLang] || targetLang;
  const todayKey = getTodayDateKey();
  const effectivePhone = activePhone || localStorage.getItem("kisan_auth_phone") || "guest";
  const storageKey = `kisan_chat_${effectivePhone}_${todayKey}`;

  // 1. Gather all currently visible message rows from DOM
  const rows = dynamicMessagesContainer ? Array.from(dynamicMessagesContainer.querySelectorAll(".chat-message-row")) : [];
  if (rows.length === 0) {
    showLanguageToast(`Language switched to ${langLabel}`);
    return;
  }

  showLanguageToast(`Translating conversation to ${langLabel}...`);
  rows.forEach(r => r.classList.add("translating"));

  // Read existing history to retain timestamps, clean original texts, and rich widgets metadata (extra)
  let history = [];
  try {
    const raw = localStorage.getItem(storageKey);
    if (raw) history = JSON.parse(raw);
  } catch(e) { history = []; }

  // Extract turn texts directly from clean stored history if available, else from visible DOM elements
  const turnsPayload = rows.map((r, i) => {
    let isUser = r.classList.contains("user-row");
    let text = "";
    let extra = {};

    if (history[i] && history[i].text) {
      isUser = history[i].role === "user";
      text = history[i].text.trim();
      extra = history[i].extra || {};
    } else if (isUser) {
      const bubble = r.querySelector(".user-bubble");
      text = bubble ? bubble.innerText.trim() : r.innerText.trim();
    } else {
      const audioBtn = r.querySelector(".btn-card-audio");
      if (audioBtn && audioBtn.getAttribute("data-text")) {
        text = audioBtn.getAttribute("data-text").trim();
      } else {
        const ps = r.querySelectorAll(".card-p");
        if (ps.length > 0) {
          text = Array.from(ps).map(p => p.innerText.trim()).join("\n");
        } else {
          text = r.innerText.trim();
        }
      }
    }
    return {
      id: i,
      role: isUser ? "user" : "assistant",
      text: text,
      extra: extra
    };
  });

  // Request batch translation from backend
  try {
    const currentSession = sessionId || `call_${effectivePhone}_${todayKey.replace(/-/g, '')}`;
    const res = await fetch(`${API_BASE}/api/session/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSession,
        target_language: targetLang,
        turns: turnsPayload
      })
    });

    if (res.ok) {
      const data = await res.json();
      if (data.status === "success" && data.translated_turns) {
        const translated = data.translated_turns;
        const updatedHistory = turnsPayload.map((t, i) => {
          const match = translated.find(m => m.id === i);
          const newText = match && match.text ? match.text : t.text;
          return {
            role: t.role,
            text: newText,
            time: (history[i] && history[i].time) || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            extra: t.extra || {}
          };
        });

        // Re-render chat container with translated turns & preserved widgets
        renderMessagesInPlace(updatedHistory);
        try { localStorage.setItem(storageKey, JSON.stringify(updatedHistory)); } catch(e) {}

        showLanguageToast(`Conversation switched to ${langLabel}`);
      }
    }
  } catch (err) {
    console.warn("[Translation] Fetch error:", err);
  } finally {
    const newRows = dynamicMessagesContainer ? dynamicMessagesContainer.querySelectorAll(".chat-message-row") : [];
    newRows.forEach(r => r.classList.remove("translating"));
  }
}

// =====================================================================
// 1. 24-HOUR EPHEMERAL STORAGE & AUTHENTICATION
function getTodayDateKey() {
  // Explicitly locked to Indian Standard Time (IST / Asia/Kolkata / UTC+5:30)
  try {
    const formatter = new Intl.DateTimeFormat('en-CA', { 
      timeZone: 'Asia/Kolkata', 
      year: 'numeric', 
      month: '2-digit', 
      day: '2-digit' 
    });
    return formatter.format(new Date()); // Always returns "YYYY-MM-DD" matching 12:00 AM IST midnight
  } catch (e) {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
}

function initSessionAndStorage() {
  const savedPhone = localStorage.getItem("kisan_auth_phone");
  const savedLoc = localStorage.getItem("kisan_auth_location");
  const todayKey = getTodayDateKey();

  // Purge any stored chat histories from previous days (24h retention)
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && key.startsWith("kisan_chat_") && !key.endsWith(todayKey)) {
      localStorage.removeItem(key);
    }
  }

  // Strict Onboarding Gate: If new user or missing phone, FREEZE EVERYTHING in background!
  if (!savedPhone || savedPhone.length !== 10) {
    console.log("[Gate] Unregistered user. Freezing background activity until onboarded.");
    if (loginModalOverlay) loginModalOverlay.style.display = "flex";
    if (loginPhoneInput) loginPhoneInput.focus();
    return;
  }

  // Existing verified user
  activePhone = savedPhone;
  activeFarmerName = localStorage.getItem("kisan_auth_name") || "Parth";
  activeLocation = savedLoc || "Hardaspur, Punjab";
  activeLat = parseFloat(localStorage.getItem("kisan_lat") || "31.2240");
  activeLon = parseFloat(localStorage.getItem("kisan_lon") || "75.7708");
  sessionId = `call_${activePhone}_${todayKey.replace(/-/g, '')}`;

  if (topUserPhoneText) topUserPhoneText.innerText = `+91 ${activePhone}`;
  if (loginModalOverlay) loginModalOverlay.style.display = "none";

  // Show varied skeletons while loading and connecting
  showSkeletonFeed();

  loadTodayChatHistory();
  connectWebSocket();
}

function saveTodayChatMessage(role, text, extra = {}) {
  const todayKey = getTodayDateKey();
  const storageKey = `kisan_chat_${activePhone}_${todayKey}`;
  let history = [];
  try {
    const existing = localStorage.getItem(storageKey);
    if (existing) history = JSON.parse(existing);
  } catch (e) { history = []; }

  // Prevent consecutive duplicate identical entries
  if (history.length > 0) {
    const last = history[history.length - 1];
    if (last.role === role && (last.text || "").trim() === (text || "").trim()) {
      return;
    }
  }

  // Lightweight storage: store only text and metadata, never raw base64 audio
  history.push({ 
    role, 
    text, 
    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), 
    extra: extra || {} 
  });

  try {
    localStorage.setItem(storageKey, JSON.stringify(history));
  } catch (e) {
    console.warn("[Storage] localStorage quota reached or write error:", e);
  }
}

async function loadTodayChatHistory() {
  const todayKey = getTodayDateKey();
  const storageKey = `kisan_chat_${activePhone}_${todayKey}`;
  let renderedLocally = false;

  try {
    const existing = localStorage.getItem(storageKey);
    if (existing) {
      const messages = JSON.parse(existing);
      if (dynamicMessagesContainer) dynamicMessagesContainer.innerHTML = "";
      
      let hasGreeting = false;
      const cleanMessages = [];
      for (const msg of messages) {
        const isGreeting = msg.text && (msg.text.includes("Namaste Kisan") || msg.text.includes("Welcome to Kisan-Vaani"));
        if (isGreeting) {
          if (!hasGreeting) {
            hasGreeting = true;
            cleanMessages.push(msg);
          }
        } else {
          cleanMessages.push(msg);
        }
      }

      for (const msg of cleanMessages) {
        if (msg.role === "user") {
          renderUserMessage(msg.text, false);
        } else {
          renderAiCard(msg.text, msg.extra || {}, false);
        }
      }
      if (cleanMessages.length > 0) renderedLocally = true;
      scrollToBottom();
    }
  } catch (e) {
    console.warn("[Storage] Local load error:", e);
  }

  // Synchronize with server session history to ensure zero loss
  if (sessionId) {
    try {
      const res = await fetch(`${API_BASE}/api/session/history/${sessionId}`);
      if (res.ok) {
        const serverData = await res.json();
        const serverHistory = serverData.chat_history || [];
        if (!renderedLocally && serverHistory.length > 0) {
          if (dynamicMessagesContainer) dynamicMessagesContainer.innerHTML = "";
          for (const item of serverHistory) {
            if (item.role === "user") {
              renderUserMessage(item.content, false);
            } else if (item.role === "assistant") {
              renderAiCard(item.content, item.extra || {}, false);
            }
          }
          scrollToBottom();
        }
      }
    } catch (err) {
      console.debug("[Storage] Server history sync note:", err);
    }
  }
}

// =====================================================================
// 2. TURN-TAKING MIC STATE MACHINE
// =====================================================================
function setTurnState(state, message = "") {
  if (turnStatusBar) {
    turnStatusBar.className = `turn-status-bar ${state}`;
  }

  if (state === "speaking") {
    // AI is speaking -> Mic MUST be safely locked to avoid echo & noise
    isAiSpeaking = true;
    if (turnStatusText) turnStatusText.innerText = message || "AI Buddy speaking... (Mic muted)";
    if (mainMicBtn) {
      mainMicBtn.className = "dock-mic-btn locked";
      mainMicBtn.setAttribute("title", "AI is speaking...");
    }
    if (micIconHolder) micIconHolder.innerHTML = MIC_LOCKED_SVG;
    if (activeStatusText) activeStatusText.innerText = "Speaking...";
  } 
  else if (state === "reasoning") {
    // AI is computing/reasoning -> Mic locked
    isAiSpeaking = true;
    if (turnStatusText) turnStatusText.innerText = message || "AI reasoning...";
    if (mainMicBtn) {
      mainMicBtn.className = "dock-mic-btn locked";
      mainMicBtn.setAttribute("title", "AI reasoning...");
    }
    if (micIconHolder) micIconHolder.innerHTML = MIC_LOCKED_SVG;
    if (activeStatusText) activeStatusText.innerText = "Reasoning...";
    if (reasoningIndicator) reasoningIndicator.style.display = "flex";
    if (reasoningBadgeText) reasoningBadgeText.innerText = message || "AI reasoning...";
    scrollToBottom();
  } 
  else if (state === "recording") {
    // Farmer is actively speaking
    isAiSpeaking = false;
    if (reasoningIndicator) reasoningIndicator.style.display = "none";
    if (turnStatusText) turnStatusText.innerText = message || "🎙️ Listening... speak now (tap to stop or pause for 2s)";
    if (mainMicBtn) {
      mainMicBtn.className = "dock-mic-btn recording";
      mainMicBtn.setAttribute("title", "Tap when finished speaking");
    }
    if (micIconHolder) micIconHolder.innerHTML = MIC_IDLE_SVG;
    if (activeStatusText) activeStatusText.innerText = "Listening...";
  } 
  else {
    // READY: AI has ended speech -> Mic unlocked and ready
    isAiSpeaking = false;
    if (reasoningIndicator) reasoningIndicator.style.display = "none";
    if (turnStatusText) turnStatusText.innerText = "Mic ready • Tap to speak or type";
    if (mainMicBtn) {
      mainMicBtn.className = "dock-mic-btn ready";
      mainMicBtn.setAttribute("title", "Tap to speak");
    }
    if (micIconHolder) micIconHolder.innerHTML = MIC_IDLE_SVG;
    if (activeStatusText) activeStatusText.innerText = "Online • Ready";
  }
}

// =====================================================================
// 3. CHAT FEED RENDERING
// =====================================================================
function scrollToBottom() {
  if (chatFeed) {
    setTimeout(() => {
      chatFeed.scrollTo({
        top: chatFeed.scrollHeight,
        behavior: "smooth"
      });
    }, 40);
  }
}

function renderUserMessage(text, save = true) {
  if (!dynamicMessagesContainer || !text) return;
  hideSkeletonFeed();

  // Deduplicate consecutive identical user messages in the DOM
  const lastMsg = dynamicMessagesContainer.lastElementChild;
  if (lastMsg && lastMsg.classList.contains("user-row")) {
    const bubble = lastMsg.querySelector(".user-bubble");
    if (bubble && bubble.innerText.trim() === text.trim()) {
      return;
    }
  }

  const row = document.createElement("div");
  row.className = "chat-message-row user-row";
  row.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
  dynamicMessagesContainer.appendChild(row);
  scrollToBottom();

  if (save) saveTodayChatMessage("user", text);
}

function capitalize(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1);
}

const CROP_ICONS = {
  soyabean: "🌱", soybean: "🌱",
  cotton: "🌾", kapas: "🌾",
  groundnut: "🥜", mungfali: "🥜",
  tomato: "🍅", tamatar: "🍅",
  onion: "🧅", pyaaz: "🧅",
  potato: "🥔", aloo: "🥔",
  wheat: "🌾", gehun: "🌾",
  mustard: "🌼", sarson: "🌼",
  chana: "🧆", gram: "🧆",
  chilli: "🌶️", mirch: "🌶️",
  garlic: "🧄", lahsun: "🧄",
  maize: "🌽", makka: "🌽",
  paddy: "🌾", dhan: "🌾"
};

const CROP_DISPLAY_NAMES = {
  soyabean: "सोयाबीन (Soybean)",
  soybean: "सोयाबीन (Soybean)",
  cotton: "कपास (Cotton)",
  groundnut: "मूंगफली (Groundnut)",
  tomato: "टमाटर (Tomato)",
  onion: "प्याज (Onion)",
  potato: "आलू (Potato)",
  wheat: "गेहूं (Wheat)",
  mustard: "सरसों (Mustard)",
  chana: "चना (Gram)",
  chilli: "हरी मिर्च (Chilli)",
  garlic: "लहसुन (Garlic)",
  maize: "मक्का (Maize)",
  paddy: "धान (Paddy)"
};

function buildMandiHeroWidget(extra) {
  if (!extra || !extra.evaluated_mandis || !extra.evaluated_mandis.length) return "";
  const mandis = extra.evaluated_mandis;
  const top = mandis[0];
  if (!top || !top.mandi_name) return "";

  const isViable = top.is_viable !== false && (top.net_in_hand > 0);
  const commName = extra.commodity ? capitalize(extra.commodity) : "Crop";
  const modalFormatted = Math.round(top.modal_price || 0).toLocaleString('en-IN');
  const netFormatted = Math.round(top.net_rate_per_quintal || top.modal_price || 0).toLocaleString('en-IN');
  const netInHandFormatted = Math.round(top.net_in_hand || 0).toLocaleString('en-IN');
  const dist = top.distance_km ? `${top.distance_km} km` : "Local Mandi";
  const locDisplay = `${top.mandi_name}${top.district ? ' (' + top.district + ')' : ''}`;

  const pillHtml = isViable
    ? `<span class="mandi-top-pill">Best Realization</span>`
    : `<span class="mandi-top-pill mandi-warning-pill">Unviable for Distant Mandi</span>`;

  const inHandChip = isViable
    ? `<div class="mandi-stat-chip emerald">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
        <span>In-hand: ₹${netFormatted}/qtl</span>
      </div>`
    : `<div class="mandi-stat-chip amber">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
        <span>Logistics Deficit: -₹${Math.round(Math.abs(top.net_in_hand)).toLocaleString('en-IN')}</span>
      </div>`;

  const totalChip = extra.quantity_quintals
    ? (isViable
        ? `<div class="mandi-stat-chip"><span>Est. Total: ₹${netInHandFormatted} (${extra.quantity_quintals} qtl)</span></div>`
        : `<div class="mandi-stat-chip"><span>Est. Net: Deficit of ₹${Math.round(Math.abs(top.net_in_hand)).toLocaleString('en-IN')} (${extra.quantity_quintals} qtl)</span></div>`)
    : '';

  let secondaryHtml = "";
  if (mandis.length > 1) {
    const others = mandis.slice(1, 3);
    const rows = others.map(m => {
      const viable = m.is_viable !== false && (m.net_in_hand > 0);
      const netText = viable
        ? `In-hand: ₹${Math.round(m.net_rate_per_quintal).toLocaleString('en-IN')}`
        : `Deficit: -₹${Math.round(Math.abs(m.net_in_hand)).toLocaleString('en-IN')}`;
      return `
        <div class="mandi-compare-row">
          <span class="mandi-compare-name">${escapeHtml(m.mandi_name || 'APMC')}</span>
          <span class="mandi-compare-rate">₹${Math.round(m.modal_price).toLocaleString('en-IN')} <span class="sub-rate">(${m.distance_km}km)</span></span>
          <span class="mandi-compare-net ${viable ? '' : 'deficit-text'}">${netText}</span>
        </div>
      `;
    }).join("");

    secondaryHtml = `
      <div class="mandi-compare-grid">
        <div class="mandi-compare-title">Compare with nearby mandis:</div>
        ${rows}
      </div>
    `;
  }

  return `
    <div class="mandi-hero-card">
      <div class="mandi-hero-header">
        <div class="mandi-hero-location">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
          <span>${escapeHtml(locDisplay)}</span>
        </div>
        ${pillHtml}
      </div>

      <div class="mandi-hero-price-row">
        <span class="mandi-hero-price">₹${modalFormatted}</span>
        <span class="mandi-hero-unit">/ quintal (${escapeHtml(commName)} modal rate)</span>
      </div>

      <div class="mandi-stats-chips">
        ${inHandChip}
        <div class="mandi-stat-chip">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
          <span>Distance: ${dist}</span>
        </div>
        ${totalChip}
      </div>

      ${secondaryHtml}
    </div>
  `;
}

function buildMultiCropWidget(extra) {
  if (!extra) return "";
  const multiRates = extra.multi_crop_rates || {};
  const crops = extra.crops || [];
  
  if (Object.keys(multiRates).length === 0 && crops.length <= 1) return "";

  const cropKeys = Object.keys(multiRates).length > 0 ? Object.keys(multiRates) : crops;
  if (cropKeys.length <= 1) return "";

  const cardsHtml = cropKeys.map(crop => {
    const icon = CROP_ICONS[crop.toLowerCase()] || "🌱";
    const displayName = capitalize(crop);
    const rates = multiRates[crop];
    let priceText = "Check Rate";
    let subText = "Tap to view";
    if (rates && rates.length > 0) {
      priceText = `₹${Math.round(rates[0].modal_price).toLocaleString('en-IN')}`;
      subText = `${rates[0].market || 'APMC'} /qtl`;
    }

    return `
      <div class="crop-rate-card" onclick="handleQuickChipClick('What is the current mandi rate of ${escapeHtml(crop)}?')">
        <div class="crop-card-top">
          <span class="crop-card-emoji">${icon}</span>
          <span class="crop-card-name">${escapeHtml(displayName)}</span>
        </div>
        <div class="crop-card-rate">${priceText}</div>
        <div class="crop-card-sub">${subText}</div>
      </div>
    `;
  }).join("");

  return `
    <div class="multi-crop-container">
      <div class="multi-crop-title">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
        <span>Live Crop Price Comparison:</span>
      </div>
      <div class="multi-crop-grid">
        ${cardsHtml}
      </div>
    </div>
  `;
}

function renderUserImage(imgUrl, caption = "Leaf photo uploaded") {
  if (!dynamicMessagesContainer || !imgUrl) return;
  hideSkeletonFeed();
  const row = document.createElement("div");
  row.className = "chat-message-row user-row";
  row.innerHTML = `
    <div class="user-bubble user-img-bubble">
      <img src="${imgUrl}" alt="${escapeHtml(caption)}" class="user-img-preview" />
      <div style="font-size: 11px; margin-top: 4px; opacity: 0.9;">📷 ${escapeHtml(caption)}</div>
    </div>
  `;
  dynamicMessagesContainer.appendChild(row);
  scrollToBottom();
}

function buildLeafDiagnosticWidget(extra) {
  if (!extra || !extra.leaf_diagnosis) return "";
  const diag = extra.leaf_diagnosis;
  const thumbUrl = extra.leaf_thumbnail || "";
  const crop = diag.crop || "Crop";
  const disease = diag.disease_name || "Leaf Disease";
  const pathogen = diag.pathogen || "";
  const conf = diag.confidence_score || 96.5;
  const severity = diag.severity_level || "Moderate";
  const chemical = diag.chemical_cure || "";
  const organic = diag.organic_remedy || "";
  const waiting = diag.waiting_period_days || 7;
  const icarRef = diag.icar_standard_reference || "ICAR POP Standard";

  return `
    <div class="leaf-diagnostic-card">
      <div class="leaf-diag-header">
        ${thumbUrl ? `<img src="${thumbUrl}" alt="Leaf" class="leaf-thumbnail-preview" />` : ''}
        <div class="leaf-diag-title-area">
          <div class="leaf-diag-crop">${escapeHtml(crop)}</div>
          <div class="leaf-diag-disease">${escapeHtml(disease)}</div>
          <div class="leaf-diag-badges">
            <span class="leaf-badge confidence">${conf}% Confidence</span>
            <span class="leaf-badge severity-high">${escapeHtml(severity)}</span>
          </div>
        </div>
      </div>

      <div class="leaf-treatment-box">
        ${pathogen ? `
        <div class="leaf-treatment-row">
          <span class="leaf-treatment-label">Causal Pathogen</span>
          <span class="leaf-treatment-text" style="font-style: italic;">${escapeHtml(pathogen)}</span>
        </div>` : ''}

        ${chemical ? `
        <div class="leaf-treatment-row">
          <span class="leaf-treatment-label">🧪 ICAR Prescribed Chemical Cure</span>
          <span class="leaf-treatment-text">${escapeHtml(chemical)}</span>
        </div>` : ''}

        ${organic ? `
        <div class="leaf-treatment-row">
          <span class="leaf-treatment-label">🌿 Biological / Organic Remedy</span>
          <span class="leaf-treatment-text">${escapeHtml(organic)}</span>
        </div>` : ''}

        <div class="leaf-treatment-row" style="flex-direction: row; justify-content: space-between; border-top: 1px dashed #e2e8f0; padding-top: 6px; margin-top: 2px;">
          <span style="font-size: 11px; color: #64748b;">Waiting Period: <strong>${waiting} days</strong></span>
          <span style="font-size: 10.5px; color: #15803d; font-weight: 600;">✓ ${escapeHtml(icarRef)}</span>
        </div>
      </div>
    </div>
  `;
}

let lastAgronomyWeather = null;

async function fetchAndRenderWeather(lat, lon, locName) {
  const effectiveLat = lat || activeLat || 31.2240;
  const effectiveLon = lon || activeLon || 75.7708;
  const effectiveLoc = locName || activeLocation || "Hardaspur, Punjab";

  if (weatherLocSub) {
    weatherLocSub.innerText = `Live Sensor Feed • ${effectiveLoc}`;
  }

  try {
    const res = await fetch(`${API_BASE}/api/weather/agronomy?lat=${effectiveLat}&lon=${effectiveLon}&location=${encodeURIComponent(effectiveLoc)}`);
    if (!res.ok) throw new Error("Weather request failed");
    const data = await res.json();
    lastAgronomyWeather = data;

    const metrics = data.current_metrics || {};
    const airTemp = Math.round(metrics.air_temperature_c || 25);
    const humidity = Math.round(metrics.relative_humidity_pct || 65);
    const wind = Math.round(metrics.wind_speed_kmh || 8);
    const soilTemp = Math.round(metrics.soil_temperature_c || (airTemp - 2));
    const soilMoisture = Math.round(metrics.soil_moisture_pct || 24);

    if (weatherHeaderTemp) {
      weatherHeaderTemp.innerText = `${airTemp}°C`;
    }

    if (tileTemp) tileTemp.innerText = `${airTemp}°C`;
    if (tileHumidity) tileHumidity.innerText = `${humidity}%`;
    if (tileWind) tileWind.innerText = `${wind} km/h`;
    if (tileSoilTemp) tileSoilTemp.innerText = `${soilTemp}°C`;
    if (tileSoilMoisture) tileSoilMoisture.innerText = `${soilMoisture}%`;

    if (agronomyCardsGrid && data.decision_cards) {
      agronomyCardsGrid.innerHTML = data.decision_cards.map(card => {
        const iconSvg = getAgronomyCardIcon(card.icon || card.domain_id);
        const statusClass = (card.css_class || "safe").toLowerCase();
        return `
          <div class="agri-decision-card">
            <div class="agri-card-header">
              <div class="agri-card-title-wrap">
                ${iconSvg}
                <span>${escapeHtml(card.title)}</span>
              </div>
              <span class="agri-card-status-badge ${statusClass}">${escapeHtml(card.badge)}</span>
            </div>
            <div class="agri-card-advice">
              ${escapeHtml(card.advisory)}
            </div>
          </div>
        `;
      }).join("");
    }
  } catch (err) {
    console.warn("[Weather] Load error:", err);
  }
}

function getAgronomyCardIcon(iconName) {
  switch (iconName) {
    case "seedling":
      return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 10v12"/><path d="M12 10a6 6 0 0 1 6-6c0 3.3-2.7 6-6 6z"/><path d="M12 14a6 6 0 0 0-6-6c0 3.3 2.7 6 6 6z"/></svg>`;
    case "droplet":
      return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/></svg>`;
    case "flask":
      return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9333ea" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v7.31L4.65 19.43A2 2 0 0 0 6.37 22h11.26a2 2 0 0 0 1.72-2.57L14 9.31V2"/><line x1="8.5" y1="2" x2="15.5" y2="2"/></svg>`;
    case "shield-alert":
      return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#dc2626" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;
    case "sun":
      return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#eab308" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`;
    case "wind":
      return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0284c7" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.59 4.59A2 2 0 1 1 11 8H2"/><path d="M12.59 19.41A2 2 0 1 0 14 16H2"/><path d="M17.73 7.73A2.5 2.5 0 1 1 19.5 12H2"/></svg>`;
    default:
      return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>`;
  }
}

async function handleLeafPhotoUpload(file) {
  if (!file) return;

  const tempImgUrl = URL.createObjectURL(file);
  renderUserImage(tempImgUrl, "Leaf photo for diagnosis");
  SoundFX.playSend();
  setTurnState("reasoning", "Scanning leaf pathology & ICAR POP database...");

  const formData = new FormData();
  formData.append("image_file", file);
  formData.append("crop_hint", "");
  formData.append("language", currentLanguage);

  try {
    const res = await fetch(`${API_BASE}/api/crop/diagnose-image`, {
      method: "POST",
      body: formData
    });

    if (!res.ok) throw new Error("Diagnosis request failed");
    const data = await res.json();
    const diag = data.diagnosis || {};

    const extra = {
      leaf_diagnosis: diag,
      leaf_thumbnail: tempImgUrl,
      diagnostic_mode: true
    };

    const aiSpeech = diag.voice_summary || `${diag.disease_name} identified with ${diag.confidence_score}% confidence. Treatment: ${diag.chemical_cure}`;

    SoundFX.playReceive();
    renderAiCard(aiSpeech, extra, true, data.audio_base64 || "");
    setTurnState("ready");

    if (data.audio_base64) {
      playGnaniAudio(aiSpeech, data.audio_base64);
    }
  } catch (err) {
    console.error("[LeafDiagnosis] Error:", err);
    renderAiCard("Sorry Kisan Bhai, I encountered an issue analyzing the leaf image. Please ensure the leaf is clearly lit and retry.", {}, true);
    setTurnState("ready");
  }
}

function buildIcarWidget(extra) {
  if (!extra || !extra.icar_facts) return "";
  const facts = extra.icar_facts;
  if (!facts.chemical_cure && !facts.organic_cure && !facts.topic) return "";

  const topic = facts.topic || extra.issue || "Crop Advisory";
  const organic = facts.organic_cure;
  const chemical = facts.chemical_cure;
  const dosage = facts.dosage;
  const waiting = facts.waiting_period_days;

  return `
    <div class="icar-rx-card">
      <div class="icar-rx-header">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        <span>ICAR Scientific Diagnosis</span>
      </div>
      <div class="icar-rx-title">${escapeHtml(topic)}</div>
      <div class="icar-rx-boxes">
        ${organic ? `
        <div class="icar-rx-box">
          <strong>🌿 Organic Treatment:</strong> ${escapeHtml(organic)}
        </div>` : ''}
        ${chemical ? `
        <div class="icar-rx-box chemical">
          <strong>🧪 Chemical Remedy:</strong> ${escapeHtml(chemical)} ${dosage ? `(${escapeHtml(dosage)})` : ''}
        </div>` : ''}
      </div>
      ${waiting ? `
      <div class="icar-rx-footer">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"></polyline></svg>
        <span>Waiting Period: <strong>${waiting} days</strong></span>
      </div>` : ''}
    </div>
  `;
}

function buildQuickChips(extra, text) {
  const chips = [];
  const multiRates = extra.multi_crop_rates || {};
  const crops = extra.crops || [];
  const cropKeys = Object.keys(multiRates).length > 0 ? Object.keys(multiRates) : crops;

  if (cropKeys.length > 1) {
    for (const c of cropKeys.slice(0, 3)) {
      const icon = CROP_ICONS[c.toLowerCase()] || "🔍";
      const name = capitalize(c);
      chips.push({ label: `${icon} ${name} Rate`, query: `What is the current mandi rate of ${c}?` });
    }
  }

  if (extra.evaluated_mandis && extra.evaluated_mandis.length > 0) {
    chips.push({ label: "📄 Send Mandi Slip", query: "send today's mandi receipt summary" });
    chips.push({ label: "⚖️ eNAM 0% Rights", query: "what is farmer zero percent commission right under eNAM?" });
  }

  if (extra.icar_facts && (extra.icar_facts.chemical_cure || extra.icar_facts.organic_cure)) {
    chips.push({ label: "🌿 Organic Spray Guide", query: "how to apply organic treatment?" });
    chips.push({ label: "⏱️ Best Spray Time", query: "what is the ideal time for spraying?" });
  }

  if (chips.length === 0) {
    return "";
  }

  const chipsHtml = chips.map(c => `
    <button class="quick-chip" onclick="handleQuickChipClick('${escapeHtml(c.query)}')">
      <span>${escapeHtml(c.label)}</span>
    </button>
  `).join("");

  return `<div class="quick-action-chips">${chipsHtml}</div>`;
}

window.handleQuickChipClick = function(chipText) {
  if (!chipText) return;
  stopAnyCurrentAudio();
  if (chatTextInput) {
    chatTextInput.value = chipText;
    submitUserText();
  }
};

function renderAiCard(text, extra = {}, save = true, audioBase64 = "") {
  if (!dynamicMessagesContainer || !text) return;
  hideSkeletonFeed();
  if (reasoningIndicator) reasoningIndicator.style.display = "none";

  const row = document.createElement("div");
  row.className = "chat-message-row ai-row";

  const formattedSpeech = formatMarkdownText(text, extra);
  const mandiHero = buildMandiHeroWidget(extra);
  const multiCrops = buildMultiCropWidget(extra);
  const icarWidget = buildIcarWidget(extra);
  const leafDiagWidget = buildLeafDiagnosticWidget(extra);
  const quickChips = buildQuickChips(extra, text);

  row.innerHTML = `
    <div class="msg-card ai-card">
      <div class="ai-card-meta">
        <div class="ai-brand-pill">
          <img src="assets/logo_emblem_carbon.png" alt="KV" class="ai-emblem-mini">
          <span class="ai-brand-name">KISAN VAANI</span>
        </div>
      </div>
      <div class="card-content">
        ${formattedSpeech}
        ${mandiHero}
        ${multiCrops}
        ${icarWidget}
        ${leafDiagWidget}
      </div>
      ${quickChips}
      <div class="card-actions">
        <button class="btn-card-audio" onclick="replayAiText(this)" data-text="${escapeHtml(text)}" data-audio="${audioBase64 || ''}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
          <span>Listen again</span>
        </button>
      </div>
    </div>
  `;
  dynamicMessagesContainer.appendChild(row);
  scrollToBottom();

  if (save) saveTodayChatMessage("assistant", text, extra);
}

function formatMarkdownText(raw, extra = {}) {
  if (!raw) return "";
  let text = escapeHtml(raw);

  // 1. Highlight currency amounts in neon lime
  text = text.replace(/₹([\d,]+(?:\.\d+)?)/g, '<strong class="hl-currency">₹$1</strong>');
  text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

  // 2. Highlight key units (quintal, kg, etc.)
  text = text.replace(/\b(\d+(?:\.\d+)?)\s*(quintal|kilo|kg|क्विंटल|किलो|टन|ton|bori|बोरी)\b/gi, '<span class="hl-metric">$1 $2</span>');

  // 3. Extract eNAM Statutory Advisory (0% Commission Guarantee)
  let enamBanner = "";
  const enamRegex = /(?:Aur\s+)?eNAM\s+kanoon[^\n.!।?]+(?:commission\s+nahi\s+kaat\s+sakta|zero\s+percent[^\n.!।?]*)[.!।]?/i;
  const enamMatch = text.match(enamRegex);
  if (enamMatch) {
    text = text.replace(enamMatch[0], "").trim();
    enamBanner = `
      <div class="card-enam-banner">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        <span><strong>eNAM अधिकार:</strong> 0% कमीशन कानूनी संरक्षण — आढ़तिया कमीशन नहीं काट सकता।</span>
      </div>
    `;
  }

  // 4. Extract Arbitrage Gain / Direct Profit Highlight
  let profitPill = "";
  const profitRegex = /([^\n.!।?]*?(?:seedha\s+munafa\s+zyada\s+hoga|munafa\s+zyada\s+hoga|seedha\s+fayda)[^\n.!।?]*[.!।]?)/i;
  const profitMatch = text.match(profitRegex);
  if (profitMatch) {
    profitPill = `
      <div class="card-profit-callout">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>
        <span>${profitMatch[0].trim()}</span>
      </div>
    `;
    text = text.replace(profitMatch[0], "").trim();
  }

  // 5. Extract Follow-up Questions at the end
  let questionBox = "";
  const questionMatches = text.match(/([^\n.!।?]+?\?)\s*$/i);
  if (questionMatches && questionMatches[0]) {
    const qText = questionMatches[0].trim();
    text = text.slice(0, text.length - questionMatches[0].length).trim();
    questionBox = `
      <div class="card-question-callout">
        <div class="question-icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        </div>
        <div class="question-text">${qText}</div>
      </div>
    `;
  }

  // 6. Numbered treatments (1) ... 2) ...)
  let rxStepsHtml = "";
  if (/1\)|1\./.test(text) && /2\)|2\./.test(text)) {
    const stepMatches = text.match(/(?:(?:^|\s)(?:[1-4]\)|[1-4]\.)\s*[\s\S]*?)(?=(?:[1-4]\)|[1-4]\.)|$)/g);
    if (stepMatches && stepMatches.length > 1) {
      rxStepsHtml = stepMatches.map((st, idx) => {
        const cleanContent = st.replace(/^(?:\s*[1-4]\)|[1-4]\.)\s*/, '').trim();
        return `
          <div class="rx-step">
            <span class="rx-badge">${idx + 1}</span>
            <span class="rx-content">${cleanContent}</span>
          </div>
        `;
      }).join("");
      text = text.replace(/(?:(?:^|\s)(?:[1-4]\)|[1-4]\.)\s*[\s\S]*?)(?=(?:[1-4]\)|[1-4]\.)|$)/g, "").trim();
    }
  }

  // 7. Bullet points: lines starting with •, -, *
  let bulletHtml = "";
  const rawLines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  const remainingParas = [];

  for (const line of rawLines) {
    if (/^[•\-\*]\s+/.test(line)) {
      const bContent = line.replace(/^[•\-\*]\s+/, '').trim();
      bulletHtml += `
        <div class="card-bullet-row">
          <div class="bullet-dot"></div>
          <div class="bullet-content">${bContent}</div>
        </div>
      `;
    } else {
      remainingParas.push(`<p class="card-p">${line.trim()}</p>`);
    }
  }

  return `${remainingParas.join("")}${profitPill}${bulletHtml}${rxStepsHtml}${enamBanner}${questionBox}`;
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// Replay Audio: Always uses official Gnani Timbre neural voice (Zero robotic voices)
window.replayAiText = function(btn) {
  const text = btn.getAttribute("data-text");
  const cachedAudio = btn.getAttribute("data-audio");
  if (text) {
    playGnaniAudio(text, cachedAudio, btn);
  }
};


// =====================================================================
// 4. WEBSOCKET REAL-TIME CONNECTION
// =====================================================================
function connectWebSocket() {
  if (socket && socket.readyState === WebSocket.OPEN) return;

  try {
    const wsUrl = `${WS_BASE}/ws/call`;
    console.log(`[WebSocket] Connecting to ${wsUrl}...`);
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log("[WebSocket] Connected successfully");
      socket.send(JSON.stringify({
        type: "start_call",
        session_id: sessionId,
        phone_number: activePhone,
        farmer_name: activeFarmerName,
        location: activeLocation,
        latitude: activeLat,
        longitude: activeLon,
        language: currentLanguage
      }));
      setTurnState("ready");
    };

    socket.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data);
        handleServerEvent(data);
      } catch (err) {
        console.error("[WebSocket] Parse error:", err);
      }
    };

    socket.onclose = () => {
      console.log("[WebSocket] Closed. Reconnecting in 3s...");
      setTurnState("ready", "Reconnecting...");
      setTimeout(connectWebSocket, 3000);
    };

    socket.onerror = (err) => {
      console.warn("[WebSocket] Error:", err);
    };
  } catch (e) {
    console.warn("[WebSocket] Exception:", e);
  }
}

function handleServerEvent(data) {
  const type = data.type;

  if (type === "call_connected") {
    setTurnState("ready");
  } 
  else if (type === "vad_state") {
    if (data.state === "reasoning") {
      setTurnState("reasoning", data.message);
    } else if (data.state === "listening") {
      setTurnState("ready");
    }
  } 
  else if (type === "transcript") {
    if (data.role === "user") {
      renderUserMessage(data.text);
      SoundFX.playSend();
    } else if (data.role === "agent") {
      const text = data.text || "";
      if (text) {
        if (pendingTextTimeout) {
          clearTimeout(pendingTextTimeout);
          pendingTextTimeout = null;
        }
        if (text.includes("Namaste Kisan Bhai ji, boliye") && dynamicMessagesContainer && dynamicMessagesContainer.children.length > 0) {
          return;
        }
        SoundFX.playReceive();
        renderAiCard(text, data.data || {}, true, "");
        setTurnState("ready");
      }
    }
  } 
  else if (type === "agent_audio") {
    const text = data.text || "";
    if (pendingTextTimeout) {
      clearTimeout(pendingTextTimeout);
      pendingTextTimeout = null;
    }
    // Avoid duplicate greetings on reconnect
    if (text.includes("Namaste Kisan Bhai ji, boliye") && dynamicMessagesContainer && dynamicMessagesContainer.children.length > 0) {
      return;
    }

    // Check if card was already rendered by transcript event
    const aiRows = dynamicMessagesContainer ? Array.from(dynamicMessagesContainer.querySelectorAll(".ai-row")) : [];
    let existingCard = null;
    for (let i = aiRows.length - 1; i >= 0; i--) {
      const p = aiRows[i].querySelector(".card-content");
      if (p && text && (p.innerText.includes(text.slice(0, 30)) || text.includes(p.innerText.slice(0, 30)))) {
        existingCard = aiRows[i];
        break;
      }
    }

    if (existingCard) {
      const audioBtn = existingCard.querySelector(".btn-card-audio");
      if (audioBtn && data.audio_base64) {
        audioBtn.setAttribute("data-audio", data.audio_base64);
        playGnaniAudio(text, data.audio_base64, audioBtn);
      }
    } else {
      SoundFX.playReceive();
      renderAiCard(text, data.data || {}, true, data.audio_base64 || "");
      if (data.audio_base64) {
        playGnaniAudio(text, data.audio_base64);
      } else {
        setTurnState("ready");
      }
    }

    // Check if daily summary was requested & delivered
    if (data.step === "DAILY_SUMMARY_DELIVERED" && data.data) {
      showDailySummaryModal(data.data.whatsapp_text, data.data.whatsapp_url);
    }
  }
}

// =====================================================================
// 5. UNIFIED GNANI TIMBRE NEURAL AUDIO ENGINE (Zero Robotic Voices)
// =====================================================================
const gnaniAudioCache = new Map();

async function playGnaniAudio(text, base64Wav = null, activeBtn = null) {
  stopAnyCurrentAudio();
  setTurnState("speaking");

  if (activeBtn) {
    activeBtn.classList.add("playing");
    activeBtn.innerHTML = `
      <div class="audio-wave-bars"><span></span><span></span><span></span><span></span></div>
      <span>Playing audio...</span>
    `;
  }

  // 1. If base64Wav audio is already provided, cache and play it immediately
  if (base64Wav && base64Wav.length > 50) {
    gnaniAudioCache.set(text, base64Wav);
    executePlayGnaniWav(base64Wav, activeBtn);
    return;
  }

  // 2. Check in-memory audio cache
  if (gnaniAudioCache.has(text)) {
    executePlayGnaniWav(gnaniAudioCache.get(text), activeBtn);
    return;
  }

  // 3. Synthesize via official Gnani Timbre v3.0 API
  try {
    const isEnglish = currentLanguage === "en-US" || currentLanguage === "en-IN";
    const voiceName = "Shivani"; // Official Timbre v3.0 neural voice supporting English (en-IN) and Indic
    const ttsLang = isEnglish ? "en-IN" : currentLanguage;

    const res = await fetch(`${API_BASE}/api/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: text,
        language: ttsLang,
        voice: voiceName
      })
    });

    if (res.ok) {
      const blob = await res.blob();
      const reader = new FileReader();
      reader.onloadend = () => {
        const rawBase64 = reader.result.split(",")[1];
        if (rawBase64 && rawBase64.length > 50) {
          gnaniAudioCache.set(text, rawBase64);
          if (activeBtn) activeBtn.setAttribute("data-audio", rawBase64);
          executePlayGnaniWav(rawBase64, activeBtn);
        } else {
          finishAudioPlayback(activeBtn);
        }
      };
      reader.readAsDataURL(blob);
    } else {
      finishAudioPlayback(activeBtn);
    }
  } catch (err) {
    console.warn("[GnaniTTS] Fetch error:", err);
    finishAudioPlayback(activeBtn);
  }
}

function executePlayGnaniWav(base64Wav, activeBtn) {
  try {
    currentAudio = new Audio("data:audio/wav;base64," + base64Wav);
    currentAudio.volume = 1.0;

    currentAudio.onended = () => {
      finishAudioPlayback(activeBtn);
    };

    currentAudio.onerror = () => {
      finishAudioPlayback(activeBtn);
    };

    const p = currentAudio.play();
    if (p !== undefined) {
      p.catch(() => {
        finishAudioPlayback(activeBtn);
      });
    }
  } catch (err) {
    finishAudioPlayback(activeBtn);
  }
}

function finishAudioPlayback(activeBtn) {
  currentAudio = null;
  if (activeBtn) {
    activeBtn.classList.remove("playing");
    activeBtn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
      <span>Listen again</span>
    `;
  }
  setTurnState("ready");
}

function stopAnyCurrentAudio() {
  if (currentAudio) {
    try { currentAudio.pause(); currentAudio.currentTime = 0; } catch (e) {}
    currentAudio = null;
  }
  if (window.speechSynthesis) {
    try { window.speechSynthesis.cancel(); } catch (e) {}
  }
}

// =====================================================================
// =====================================================================
// 6. OVERPOWERED DUAL-ENGINE MICROPHONE & VAD INPUT ENGINE
// Zero-loss audio buffering + Browser Web Speech API + Whisper Large v3
// =====================================================================
let speechRecognizer = null;
let liveTranscribedText = "";

function startBrowserSpeechRecognition() {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRec) return;

  try {
    if (speechRecognizer) {
      try { speechRecognizer.abort(); } catch (e) {}
    }
    speechRecognizer = new SpeechRec();
    speechRecognizer.continuous = true;
    speechRecognizer.interimResults = true;
    speechRecognizer.maxAlternatives = 1;

    const langMap = {
      "en-US": "en-IN",
      "hi-IN": "hi-IN",
      "hinglish": "hi-IN",
      "pa-IN": "pa-Guru-IN",
      "mr-IN": "mr-IN",
      "te-IN": "te-IN",
      "ta-IN": "ta-IN",
      "gu-IN": "gu-IN",
      "bn-IN": "bn-IN"
    };
    speechRecognizer.lang = langMap[currentLanguage] || "en-IN";

    speechRecognizer.onresult = (event) => {
      let interim = "";
      let final = "";
      for (let i = 0; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          final += event.results[i][0].transcript + " ";
        } else {
          interim += event.results[i][0].transcript;
        }
      }
      liveTranscribedText = sanitizeAntiUrdu((final + interim).trim());
      if (liveTranscribedText && turnStatusText && isRecording) {
        turnStatusText.innerText = `🎙️ "${liveTranscribedText}"`;
      }
    };

    speechRecognizer.onerror = (e) => {
      console.debug("[BrowserSTT] Notice:", e.error);
    };

    speechRecognizer.start();
  } catch (err) {
    console.debug("[BrowserSTT] Init notice:", err);
  }
}

function stopBrowserSpeechRecognition() {
  if (speechRecognizer) {
    try { speechRecognizer.stop(); } catch (e) {}
    speechRecognizer = null;
  }
}

async function toggleMicrophone() {
  // If AI is currently speaking, user tap acts as barge-in: stop AI audio and unlock
  if (isAiSpeaking) {
    stopAnyCurrentAudio();
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "barge_in" }));
    }
    setTurnState("ready", "AI stopped • Tap to speak");
    return;
  }

  if (isRecording) {
    stopRecordingAndSend();
  } else {
    await startMicrophoneRecording();
  }
}

async function startMicrophoneRecording() {
  try {
    liveTranscribedText = "";
    startBrowserSpeechRecognition();

    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }

    if (!mediaStream) {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: false,
          autoGainControl: true
        }
      });
    }

    audioSource = audioContext.createMediaStreamSource(mediaStream);
    audioProcessor = audioContext.createScriptProcessor(4096, 1, 1);

    audioBufferChunks = [];
    isSpeaking = false;
    silenceStartTime = 0;
    speechStartTime = 0;
    isRecording = true;

    setTurnState("recording", "🎙️ Listening... speak now (tap when finished)");

    audioProcessor.onaudioprocess = (e) => {
      if (!isRecording) return;
      const inputData = e.inputBuffer.getChannelData(0);

      // Retain EVERY audio chunk from the exact moment recording starts! Zero missing starting words!
      audioBufferChunks.push(new Float32Array(inputData));

      // RMS calculation for auto-stop on silence
      let sum = 0;
      for (let i = 0; i < inputData.length; i++) {
        sum += inputData[i] * inputData[i];
      }
      const rms = Math.sqrt(sum / inputData.length);
      const now = performance.now();

      // Soft threshold (0.005) ensures whispering or soft consonants are caught
      if (rms > 0.005) {
        isSpeaking = true;
        silenceStartTime = 0;
        if (!liveTranscribedText && turnStatusText) {
          turnStatusText.innerText = "🎙️ Listening... (tap mic when done)";
        }
      } else {
        if (isSpeaking) {
          if (silenceStartTime === 0) silenceStartTime = now;
          else if (now - silenceStartTime > 2200) { // 2.2s natural pause threshold
            isSpeaking = false;
            stopRecordingAndSend();
          }
        }
      }
    };

    audioSource.connect(audioProcessor);
    audioProcessor.connect(audioContext.destination);
  } catch (err) {
    console.warn("[Mic] Access error:", err);
    setTurnState("ready", "Please allow microphone access");
  }
}

function stopRecording() {
  isRecording = false;
  isSpeaking = false;
  stopBrowserSpeechRecognition();
  silenceStartTime = 0;
  speechStartTime = 0;
  audioBufferChunks = [];
  preRollBuffer = [];
  if (audioProcessor && audioSource) {
    try {
      audioSource.disconnect();
      audioProcessor.disconnect();
    } catch (e) {}
  }
}

function stopRecordingAndSend() {
  isRecording = false;
  stopBrowserSpeechRecognition();

  if (audioProcessor && audioSource) {
    try {
      audioSource.disconnect();
      audioProcessor.disconnect();
    } catch (e) {}
  }

  if (audioBufferChunks.length === 0) {
    setTurnState("ready");
    return;
  }

  const currentSampleRate = (audioContext && audioContext.sampleRate) ? audioContext.sampleRate : 44100;
  const resampled16k = resampleTo16k(audioBufferChunks, currentSampleRate);

  if (resampled16k.length < 2400 && !liveTranscribedText) { // Ignore accidental click (<0.15s)
    setTurnState("ready");
    return;
  }

  setTurnState("reasoning", "Transcribing speech...");

  const wavBlob = encodeResampled16kWAV(resampled16k);
  const reader = new FileReader();
  const textToSend = liveTranscribedText;

  reader.onloadend = () => {
    const base64Wav = reader.result.split(',')[1];
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        type: "speech_end",
        audio_data: base64Wav,
        text: textToSend
      }));
    }
  };
  reader.readAsDataURL(wavBlob);
  audioBufferChunks = [];
}

// Resamples any input sample rate (e.g. 48000 or 44100 from browser AudioContext) to pristine 16000 Hz mono
function resampleTo16k(chunks, sourceRate) {
  let totalLength = 0;
  for (let c of chunks) totalLength += c.length;
  const merged = new Float32Array(totalLength);
  let offset = 0;
  for (let c of chunks) {
    merged.set(c, offset);
    offset += c.length;
  }

  if (!sourceRate || sourceRate === 16000) {
    return merged;
  }

  const ratio = sourceRate / 16000;
  const targetLength = Math.round(totalLength / ratio);
  const result = new Float32Array(targetLength);

  for (let i = 0; i < targetLength; i++) {
    const srcPos = i * ratio;
    const srcIndex = Math.floor(srcPos);
    const fraction = srcPos - srcIndex;
    const s0 = merged[srcIndex] || 0;
    const s1 = (srcIndex + 1 < merged.length) ? merged[srcIndex + 1] : s0;
    result[i] = s0 + fraction * (s1 - s0);
  }
  return result;
}

function encodeResampled16kWAV(samples) {
  const sampleRate = 16000;
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  function writeString(offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  writeString(0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM Format (1)
  view.setUint16(22, 1, true); // Mono channel
  view.setUint32(24, sampleRate, true); // 16000 Hz
  view.setUint32(28, sampleRate * 2, true); // Byte rate (16000 * 2)
  view.setUint16(32, 2, true); // Block align (1 * 16 / 8)
  view.setUint16(34, 16, true); // 16 bits per sample
  writeString(36, 'data');
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    let s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    offset += 2;
  }
  return new Blob([view], { type: 'audio/wav' });
}

// =====================================================================
// 7. USER TEXT SUBMISSION
// =====================================================================
let isSubmittingText = false;
let pendingTextTimeout = null;

async function submitUserText() {
  const inputEl = document.getElementById("chatTextInput");
  const text = sanitizeAntiUrdu(inputEl ? inputEl.value : "").trim();
  if (!text || isSubmittingText) return;

  isSubmittingText = true;
  if (inputEl) {
    inputEl.value = "";
    inputEl.blur();
  }

  // Safely stop any active recording so mic noise never interferes with typed query
  try {
    stopRecording();
  } catch (e) {
    console.warn("[Mic] Stop recording note:", e);
  }

  try {
    renderUserMessage(text);
    SoundFX.playSend();
    setTurnState("reasoning", "Preparing answer...");

    // Watchdog fallback: if WebSocket does not answer within 7 seconds, call REST endpoint directly!
    if (pendingTextTimeout) clearTimeout(pendingTextTimeout);
    pendingTextTimeout = setTimeout(async () => {
      console.warn("[Chat] WebSocket response timeout (7s). Calling fallback REST /api/chat...");
      await fetchChatFallback(text);
    }, 7000);

    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        type: "user_text",
        text: text
      }));
    } else {
      console.warn("[Chat] WebSocket not open. Calling fallback REST /api/chat immediately...");
      if (pendingTextTimeout) {
        clearTimeout(pendingTextTimeout);
        pendingTextTimeout = null;
      }
      await fetchChatFallback(text);
    }
  } catch (err) {
    console.error("[Chat] Error submitting text:", err);
  } finally {
    setTimeout(() => {
      isSubmittingText = false;
    }, 350);
  }
}

async function fetchChatFallback(text) {
  try {
    const todayKey = getTodayDateKey();
    const effectivePhone = activePhone || localStorage.getItem("kisan_auth_phone") || "guest";
    const currentSession = sessionId || `call_${effectivePhone}_${todayKey.replace(/-/g, '')}`;

    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSession,
        utterance: text,
        language: currentLanguage
      })
    });

    if (res.ok) {
      const data = await res.json();
      const spokenText = data.spoken_text || "";
      if (spokenText) {
        SoundFX.playReceive();
        renderAiCard(spokenText, data.data || {}, true, data.audio_base64 || "");
        setTurnState("ready");
        if (data.audio_base64) {
          playGnaniAudio(spokenText, data.audio_base64);
        }
        return;
      }
    }
  } catch (err) {
    console.error("[Chat:Fallback] Error:", err);
  }
  setTurnState("ready");
}

// =====================================================================
// 8. SMART WHATSAPP DAILY SUMMARY MODAL
// =====================================================================
async function triggerDailyWhatsAppSummary() {
  setTurnState("reasoning", "Compiling daily summary...");
  try {
    const res = await fetch(`${API_BASE}/api/session/whatsapp_summary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        phone_number: activePhone
      })
    });
    const data = await res.json();
    if (data.status === "success" && data.summary) {
      showDailySummaryModal(data.summary.whatsapp_text, data.summary.whatsapp_url);
    }
  } catch (err) {
    console.warn("[Summary] Fetch error:", err);
  }
  setTurnState("ready");
}

function showDailySummaryModal(text, url) {
  if (waSummaryText) waSummaryText.innerText = text;
  if (waDirectSendBtn) waDirectSendBtn.href = url;
  if (waSummaryModal) waSummaryModal.style.display = "flex";
}

// =====================================================================
// 9. EVENT LISTENERS
// =====================================================================
document.addEventListener("DOMContentLoaded", () => {
  initLanguageSelector();
  initSessionAndStorage();

  // Initial Weather Sync
  fetchAndRenderWeather(activeLat, activeLon, activeLocation);

  // Weather Modal Open/Close
  if (headerWeatherBtn) {
    headerWeatherBtn.addEventListener("click", () => {
      if (weatherAgronomyModal) {
        weatherAgronomyModal.style.display = "flex";
        fetchAndRenderWeather(activeLat, activeLon, activeLocation);
      }
    });
  }

  if (weatherCloseBtn) {
    weatherCloseBtn.addEventListener("click", () => {
      if (weatherAgronomyModal) weatherAgronomyModal.style.display = "none";
    });
  }

  // Multimodal Leaf Photo Upload Trigger
  if (btnUploadLeaf && leafFileInput) {
    btnUploadLeaf.addEventListener("click", () => {
      leafFileInput.click();
    });

    leafFileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        handleLeafPhotoUpload(e.target.files[0]);
        // Reset file input value so same photo can be re-uploaded if needed
        leafFileInput.value = "";
      }
    });
  }

  // Permission: GPS Location
  if (btnAllowLocation) {
    btnAllowLocation.addEventListener("click", () => {
      btnAllowLocation.innerText = "Locating...";
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          async (pos) => {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            activeLat = lat;
            activeLon = lon;
            try {
              const res = await fetch(`${API_BASE}/api/location/reverse?lat=${lat}&lon=${lon}&phone=${(loginPhoneInput ? loginPhoneInput.value : '') || activePhone}`);
              const data = await res.json();
              activeLocation = data.formatted_location || "Hardaspur, Punjab";
            } catch (e) {
              activeLocation = "Hardaspur, Punjab";
            }
            localStorage.setItem("kisan_auth_location", activeLocation);
            localStorage.setItem("kisan_lat", activeLat);
            localStorage.setItem("kisan_lon", activeLon);
            if (permLocationDesc) permLocationDesc.innerText = `✓ Verified: ${activeLocation}`;
            btnAllowLocation.innerText = "✓ Granted";
            btnAllowLocation.classList.add("granted");
            if (permLocationCard) permLocationCard.classList.add("granted");
          },
          (err) => {
            console.warn("[GPS] Fallback to Hardaspur:", err);
            activeLocation = "Hardaspur, Punjab";
            activeLat = 31.2240;
            activeLon = 75.7708;
            localStorage.setItem("kisan_auth_location", activeLocation);
            localStorage.setItem("kisan_lat", activeLat);
            localStorage.setItem("kisan_lon", activeLon);
            if (permLocationDesc) permLocationDesc.innerText = "✓ Default: Hardaspur, Punjab";
            btnAllowLocation.innerText = "✓ Set";
            btnAllowLocation.classList.add("granted");
            if (permLocationCard) permLocationCard.classList.add("granted");
          },
          { timeout: 7000 }
        );
      } else {
        activeLocation = "Hardaspur, Punjab";
        activeLat = 31.2240;
        activeLon = 75.7708;
        localStorage.setItem("kisan_auth_location", activeLocation);
        localStorage.setItem("kisan_lat", activeLat);
        localStorage.setItem("kisan_lon", activeLon);
        if (permLocationDesc) permLocationDesc.innerText = "✓ Default: Hardaspur, Punjab";
        btnAllowLocation.innerText = "✓ Set";
        btnAllowLocation.classList.add("granted");
        if (permLocationCard) permLocationCard.classList.add("granted");
      }
    });
  }

  // Permission: Microphone
  if (btnAllowMic) {
    btnAllowMic.addEventListener("click", () => {
      navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
        mediaStream = stream;
        btnAllowMic.innerText = "✓ Ready";
        btnAllowMic.classList.add("granted");
        if (permMicCard) permMicCard.classList.add("granted");
        if (permMicDesc) permMicDesc.innerText = "✓ Microphone access granted.";
      }).catch((err) => {
        btnAllowMic.innerText = "Retry";
        if (permMicDesc) permMicDesc.innerText = "Please allow mic in browser settings.";
      });
    });
  }

  // Login / Onboarding form submit
  if (loginPhoneForm) {
    loginPhoneForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const phone = loginPhoneInput.value.replace(/\D/g, "");
      if (phone.length !== 10) {
        alert("Please enter a valid 10-digit mobile number.");
        return;
      }
      const name = loginNameInput && loginNameInput.value.trim() ? loginNameInput.value.trim() : "Parth";
      if (!activeLocation) {
        activeLocation = "Hardaspur, Punjab";
        activeLat = 31.2240;
        activeLon = 75.7708;
      }

      localStorage.setItem("kisan_auth_phone", phone);
      localStorage.setItem("kisan_auth_name", name);
      localStorage.setItem("kisan_auth_location", activeLocation);
      localStorage.setItem("kisan_lat", activeLat);
      localStorage.setItem("kisan_lon", activeLon);

      activePhone = phone;
      activeFarmerName = name;
      sessionId = `call_${activePhone}_${getTodayDateKey().replace(/-/g, '')}`;

      if (topUserPhoneText) topUserPhoneText.innerText = `+91 ${activePhone}`;
      if (loginModalOverlay) loginModalOverlay.style.display = "none";

      // Render varied skeletons immediately on submit
      showSkeletonFeed();

      loadTodayChatHistory();
      connectWebSocket();
    });
  }

  // Switch phone account
  if (topUserBadge) {
    topUserBadge.addEventListener("click", () => {
      if (loginModalOverlay) {
        loginModalOverlay.style.display = "flex";
        if (loginPhoneInput) loginPhoneInput.focus();
      }
    });
  }

  // Header 1-tap WhatsApp summary button
  if (headerWhatsAppBtn) {
    headerWhatsAppBtn.addEventListener("click", () => {
      triggerDailyWhatsAppSummary();
    });
  }

  // Mic click handler (Turn-Controlled)
  if (mainMicBtn) {
    mainMicBtn.addEventListener("click", () => {
      toggleMicrophone();
    });
  }

  // Chat text form submit, button click, and Enter key
  if (chatTextForm) {
    chatTextForm.addEventListener("submit", (e) => {
      e.preventDefault();
      submitUserText();
    });
  }

  if (sendTextBtn) {
    sendTextBtn.addEventListener("click", (e) => {
      e.preventDefault();
      submitUserText();
    });
  }

  if (chatTextInput) {
    chatTextInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submitUserText();
      }
    });
  }

  // Unlock Web Audio API context on first user interaction
  const unlockAudio = () => {
    SoundFX.init();
    window.removeEventListener("click", unlockAudio);
    window.removeEventListener("keydown", unlockAudio);
    window.removeEventListener("touchstart", unlockAudio);
  };
  window.addEventListener("click", unlockAudio, { passive: true });
  window.addEventListener("keydown", unlockAudio, { passive: true });
  window.addEventListener("touchstart", unlockAudio, { passive: true });
});
