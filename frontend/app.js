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
const MAX_PRE_ROLL = 5;
let ambientNoiseFloor = 0.012;
const SILENCE_TIMEOUT_MS = 750;
const MIN_SPEECH_DURATION_MS = 250;

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
const mainMicBtn = document.getElementById("mainMicBtn");
const micIconHolder = document.getElementById("micIconHolder");

const waSummaryModal = document.getElementById("waSummaryModal");
const waSummaryText = document.getElementById("waSummaryText");
const waDirectSendBtn = document.getElementById("waDirectSendBtn");
const waCloseBtn = document.getElementById("waCloseBtn");

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
// 1. 24-HOUR EPHEMERAL STORAGE & AUTHENTICATION
// =====================================================================
function getTodayDateKey() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function initSessionAndStorage() {
  const savedPhone = localStorage.getItem("kisan_auth_phone");
  const todayKey = getTodayDateKey();

  // Purge any stored chat histories from previous days (24h retention)
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && key.startsWith("kisan_chat_") && !key.endsWith(todayKey)) {
      localStorage.removeItem(key);
    }
  }

  if (savedPhone && savedPhone.length === 10) {
    activePhone = savedPhone;
    sessionId = `call_${activePhone}_${todayKey.replace(/-/g, '')}`;
    if (topUserPhoneText) topUserPhoneText.innerText = `+91 ${activePhone}`;
    if (loginModalOverlay) loginModalOverlay.style.display = "none";
    loadTodayChatHistory();
    connectWebSocket();
  } else {
    if (loginModalOverlay) loginModalOverlay.style.display = "flex";
    if (loginPhoneInput) loginPhoneInput.focus();
  }
}

function saveTodayChatMessage(role, text, extra = {}) {
  const todayKey = getTodayDateKey();
  const storageKey = `kisan_chat_${activePhone}_${todayKey}`;
  let history = [];
  try {
    const existing = localStorage.getItem(storageKey);
    if (existing) history = JSON.parse(existing);
  } catch (e) { history = []; }

  history.push({ role, text, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), extra });
  try {
    localStorage.setItem(storageKey, JSON.stringify(history));
  } catch (e) {}
}

function loadTodayChatHistory() {
  const todayKey = getTodayDateKey();
  const storageKey = `kisan_chat_${activePhone}_${todayKey}`;
  try {
    const existing = localStorage.getItem(storageKey);
    if (existing) {
      const messages = JSON.parse(existing);
      if (dynamicMessagesContainer) dynamicMessagesContainer.innerHTML = "";
      for (const msg of messages) {
        if (msg.role === "user") {
          renderUserMessage(msg.text, false);
        } else {
          renderAiCard(msg.text, msg.extra || {}, false);
        }
      }
      scrollToBottom();
    }
  } catch (e) {}
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
    if (turnStatusText) turnStatusText.innerText = message || "AI Buddy बोल रहा है... (माइक बंद है)";
    if (mainMicBtn) {
      mainMicBtn.className = "dock-mic-btn locked";
      mainMicBtn.setAttribute("title", "AI बोल रहा है...");
    }
    if (micIconHolder) micIconHolder.innerHTML = MIC_LOCKED_SVG;
    if (activeStatusText) activeStatusText.innerText = "AI Speaking...";
  } 
  else if (state === "reasoning") {
    // AI is computing/reasoning -> Mic locked
    isAiSpeaking = true;
    if (turnStatusText) turnStatusText.innerText = message || "AI सोच रहा है...";
    if (mainMicBtn) {
      mainMicBtn.className = "dock-mic-btn locked";
      mainMicBtn.setAttribute("title", "AI सोच रहा है...");
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
    if (turnStatusText) turnStatusText.innerText = "सुन रहा हूँ... बोलिए";
    if (mainMicBtn) {
      mainMicBtn.className = "dock-mic-btn recording";
      mainMicBtn.setAttribute("title", "माइक सक्रिय है...");
    }
    if (micIconHolder) micIconHolder.innerHTML = MIC_IDLE_SVG;
    if (activeStatusText) activeStatusText.innerText = "Listening...";
  } 
  else {
    // READY: AI has ended speech -> Mic unlocked and ready
    isAiSpeaking = false;
    if (reasoningIndicator) reasoningIndicator.style.display = "none";
    if (turnStatusText) turnStatusText.innerText = "माइक तैयार है • बोलें या लिखें";
    if (mainMicBtn) {
      mainMicBtn.className = "dock-mic-btn ready";
      mainMicBtn.setAttribute("title", "बोलने के लिए दबाएं");
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
      chatFeed.scrollTop = chatFeed.scrollHeight;
    }, 40);
  }
}

function renderUserMessage(text, save = true) {
  if (!dynamicMessagesContainer || !text) return;
  const row = document.createElement("div");
  row.className = "chat-message-row user-row";
  row.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
  dynamicMessagesContainer.appendChild(row);
  scrollToBottom();

  if (save) saveTodayChatMessage("user", text);
}

function renderAiCard(text, extra = {}, save = true) {
  if (!dynamicMessagesContainer || !text) return;
  if (reasoningIndicator) reasoningIndicator.style.display = "none";

  const row = document.createElement("div");
  row.className = "chat-message-row ai-row";

  let badge = "AI Krishi Scientist";
  if (extra.topic) badge = extra.topic;
  else if (extra.commodity) badge = `${extra.commodity.toUpperCase()} Mandi Bhav`;

  row.innerHTML = `
    <div class="msg-avatar">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--neon-lime)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
      </svg>
    </div>
    <div class="msg-card ai-card">
      <div class="card-header-badge">${escapeHtml(badge)}</div>
      <div class="card-content">${formatMarkdownText(text)}</div>
      <div class="card-actions">
        <button class="btn-card-audio" onclick="replayAiText(this)" data-text="${escapeHtml(text)}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
          <span>दोबारा सुनें</span>
        </button>
      </div>
    </div>
  `;
  dynamicMessagesContainer.appendChild(row);
  scrollToBottom();

  if (save) saveTodayChatMessage("assistant", text, extra);
}

function formatMarkdownText(raw) {
  let clean = escapeHtml(raw);
  clean = clean.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  clean = clean.replace(/₹([\d,]+)/g, '<strong style="color:var(--neon-lime);">₹$1</strong>');
  return `<p>${clean.replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>')}</p>`;
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// Replay Audio on button click
window.replayAiText = function(btn) {
  const text = btn.getAttribute("data-text");
  if (text) {
    speakWithBrowserTTS(text);
  }
};

window.playWelcomeAudio = function() {
  speakWithBrowserTTS("राम राम किसान भाई! मैं किसान-वाणी हूँ। आप बोलकर या लिखकर किसी भी फसल का ताज़ा मंडी भाव, बीमारी की दवाई, या सरकारी योजनाओं के बारे में पूछ सकते हैं।");
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
        language: "hi-IN"
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
      setTurnState("ready", "पुनः कनेक्ट हो रहा है...");
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
    }
  } 
  else if (type === "agent_audio") {
    const text = data.text || "";
    renderAiCard(text, data.data || {});

    // Check if daily summary was requested & delivered
    if (data.step === "DAILY_SUMMARY_DELIVERED" && data.data) {
      showDailySummaryModal(data.data.whatsapp_text, data.data.whatsapp_url);
    }

    // Play TTS: Lock Mic while AI speaks
    setTurnState("speaking");
    if (data.audio_base64) {
      playAgentAudio(data.audio_base64, text);
    } else {
      speakWithBrowserTTS(text);
    }
  }
}

// =====================================================================
// 5. DUAL AUDIO PLAYBACK & SPEECH SYNTHESIS
// =====================================================================
function playAgentAudio(base64Wav, fallbackText = "") {
  stopAnyCurrentAudio();

  try {
    currentAudio = new Audio("data:audio/wav;base64," + base64Wav);
    currentAudio.volume = 1.0;

    currentAudio.onended = () => {
      currentAudio = null;
      setTurnState("ready"); // AI finished speaking -> UNLOCK MIC!
    };

    currentAudio.onerror = () => {
      currentAudio = null;
      if (fallbackText) speakWithBrowserTTS(fallbackText);
      else setTurnState("ready");
    };

    const p = currentAudio.play();
    if (p !== undefined) {
      p.catch(() => {
        if (fallbackText) speakWithBrowserTTS(fallbackText);
        else setTurnState("ready");
      });
    }
  } catch (err) {
    if (fallbackText) speakWithBrowserTTS(fallbackText);
    else setTurnState("ready");
  }
}

function speakWithBrowserTTS(text) {
  if (!text || !window.speechSynthesis) {
    setTurnState("ready");
    return;
  }

  stopAnyCurrentAudio();

  try {
    window.speechSynthesis.resume();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "hi-IN";
    utterance.rate = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const hiVoice = voices.find(v => v.lang && (v.lang.includes("hi") || v.lang.includes("HI")));
    if (hiVoice) utterance.voice = hiVoice;

    setTurnState("speaking");

    utterance.onend = () => {
      setTurnState("ready"); // AI finished speaking -> UNLOCK MIC!
    };
    utterance.onerror = () => {
      setTurnState("ready");
    };

    window.speechSynthesis.speak(utterance);
  } catch (e) {
    setTurnState("ready");
  }
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
// 6. MICROPHONE & VAD INPUT ENGINE
// =====================================================================
async function toggleMicrophone() {
  // If AI is currently speaking, user tap acts as barge-in: stop AI audio and unlock
  if (isAiSpeaking) {
    stopAnyCurrentAudio();
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "barge_in" }));
    }
    setTurnState("ready", "AI रोका गया • अब बोलें");
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
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    }
    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }

    if (!mediaStream) {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
    }

    audioSource = audioContext.createMediaStreamSource(mediaStream);
    audioProcessor = audioContext.createScriptProcessor(4096, 1, 1);

    audioBufferChunks = [];
    preRollBuffer = [];
    isSpeaking = false;
    silenceStartTime = 0;
    speechStartTime = 0;
    isRecording = true;

    setTurnState("recording");

    audioProcessor.onaudioprocess = (e) => {
      if (!isRecording) return;
      const inputData = e.inputBuffer.getChannelData(0);

      // RMS calculation
      let sum = 0;
      for (let i = 0; i < inputData.length; i++) {
        sum += inputData[i] * inputData[i];
      }
      const rms = Math.sqrt(sum / inputData.length);
      const dynamicThreshold = Math.max(0.016, ambientNoiseFloor * 2.2);

      const now = performance.now();

      if (rms > dynamicThreshold) {
        silenceStartTime = 0;
        if (!isSpeaking) {
          preRollBuffer.push(new Float32Array(inputData));
          if (preRollBuffer.length > MAX_PRE_ROLL) preRollBuffer.shift();

          if (speechStartTime === 0) speechStartTime = now;
          else if (now - speechStartTime > MIN_SPEECH_DURATION_MS) {
            isSpeaking = true;
            for (let c of preRollBuffer) audioBufferChunks.push(c);
            preRollBuffer = [];
          }
        }
        if (isSpeaking) {
          audioBufferChunks.push(new Float32Array(inputData));
        }
      } else {
        speechStartTime = 0;
        if (!isSpeaking) {
          preRollBuffer.push(new Float32Array(inputData));
          if (preRollBuffer.length > MAX_PRE_ROLL) preRollBuffer.shift();
          ambientNoiseFloor = ambientNoiseFloor * 0.95 + rms * 0.05;
        } else {
          audioBufferChunks.push(new Float32Array(inputData));
          if (silenceStartTime === 0) silenceStartTime = now;
          else if (now - silenceStartTime > SILENCE_TIMEOUT_MS) {
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
    setTurnState("ready", "माइक की अनुमति दें");
  }
}

function stopRecordingAndSend() {
  isRecording = false;
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

  // Calculate length and encode WAV
  let totalLength = 0;
  for (let c of audioBufferChunks) totalLength += c.length;
  if (totalLength < 4000) { // Too short / accidental tap
    setTurnState("ready");
    return;
  }

  setTurnState("reasoning", "प्रश्नोत्तर संसाधित हो रहा है...");

  const wavBlob = encodeWAV(audioBufferChunks, 16000);
  const reader = new FileReader();
  reader.onloadend = () => {
    const base64Wav = reader.result.split(',')[1];
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        type: "speech_end",
        audio_data: base64Wav
      }));
    }
  };
  reader.readAsDataURL(wavBlob);
  audioBufferChunks = [];
}

function encodeWAV(chunks, sampleRate) {
  let totalLength = 0;
  for (let c of chunks) totalLength += c.length;
  const buffer = new ArrayBuffer(44 + totalLength * 2);
  const view = new DataView(buffer);

  function writeString(offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  writeString(0, 'RIFF');
  view.setUint32(4, 36 + totalLength * 2, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, 'data');
  view.setUint32(40, totalLength * 2, true);

  let offset = 44;
  for (let c of chunks) {
    for (let i = 0; i < c.length; i++) {
      let s = Math.max(-1, Math.min(1, c[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      offset += 2;
    }
  }
  return new Blob([view], { type: 'audio/wav' });
}

// =====================================================================
// 7. USER TEXT SUBMISSION
// =====================================================================
function submitUserText() {
  const text = chatTextInput.value.trim();
  if (!text) return;

  chatTextInput.value = "";
  chatTextInput.blur();

  renderUserMessage(text);
  setTurnState("reasoning", "उत्तर तैयार हो रहा है...");

  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({
      type: "user_text",
      text: text
    }));
  }
}

// =====================================================================
// 8. SMART WHATSAPP DAILY SUMMARY MODAL
// =====================================================================
async function triggerDailyWhatsAppSummary() {
  setTurnState("reasoning", "आज का सारांश तैयार हो रहा है...");
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
  initSessionAndStorage();

  // Login form submit
  if (loginPhoneForm) {
    loginPhoneForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const phone = loginPhoneInput.value.replace(/\D/g, "");
      if (phone.length !== 10) {
        alert("कृपया 10 अंकों का मोबाइल नंबर दर्ज करें।");
        return;
      }
      localStorage.setItem("kisan_auth_phone", phone);
      activePhone = phone;
      sessionId = `call_${activePhone}_${getTodayDateKey().replace(/-/g, '')}`;
      if (topUserPhoneText) topUserPhoneText.innerText = `+91 ${activePhone}`;
      if (loginModalOverlay) loginModalOverlay.style.display = "none";

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

  // Chat text form submit
  if (chatTextForm) {
    chatTextForm.addEventListener("submit", (e) => {
      e.preventDefault();
      submitUserText();
    });
  }

  // Close WhatsApp summary modal
  if (waCloseBtn) {
    waCloseBtn.addEventListener("click", () => {
      if (waSummaryModal) waSummaryModal.style.display = "none";
    });
  }
});
