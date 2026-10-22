// Kisan-Vaani: Pure ChatGPT Voice Experience for Indian Farmers
// Powered by Gnani Timbre v3.0 (TTS), Prisma (STT) & Sovereign Agri-Intelligence

const API_BASE = window.location.origin;
const WS_BASE = API_BASE.replace(/^http/, "ws");

let sessionId = "call_" + Math.random().toString(36).substring(2, 9);
let activePhoneNumber = "";
let isCallActive = false;
let socket = null;
let currentAudio = null;
let animationId = null;

// Web Audio & VAD Variables
let audioContext = null;
let mediaStream = null;
let audioSource = null;
let audioProcessor = null;
let analyser = null;
let freqByteData = null;

// VAD State Machine
let isSpeaking = false;
let silenceStartTime = 0;
let speechStartTime = 0;
let audioBufferChunks = [];
let ambientNoiseFloor = 0.015;
const SILENCE_TIMEOUT_MS = 700;
const MIN_SPEECH_DURATION_MS = 300;

// DOM Elements
const orbContainer = document.getElementById("orbContainer");
const voiceOrb = document.getElementById("voiceOrb");
const orbIcon = document.getElementById("orbIcon");
const voiceStatePill = document.getElementById("voiceStatePill");
const voiceStateText = document.getElementById("voiceStateText");
const voiceCaption = document.getElementById("voiceCaption");
const mainMicBtn = document.getElementById("mainMicBtn");
const micIcon = document.getElementById("micIcon");
const toggleChipsBtn = document.getElementById("toggleChipsBtn");
const quickChipsDrawer = document.getElementById("quickChipsDrawer");
const silentWaBtn = document.getElementById("silentWaBtn");
const waFloatingToast = document.getElementById("waFloatingToast");
const waToastMsg = document.getElementById("waToastMsg");
const waToastLink = document.getElementById("waToastLink");
const topPhoneBadge = document.getElementById("topPhoneBadge");
const topPhoneText = document.getElementById("topPhoneText");
const activeFarmerSubtext = document.getElementById("activeFarmerSubtext");

// Onboarding & Settings Sheets
const mobileEntryOverlay = document.getElementById("mobileEntryOverlay");
const mobileEntryForm = document.getElementById("mobileEntryForm");
const farmerPhoneInput = document.getElementById("farmerPhoneInput");
const settingsBtn = document.getElementById("settingsBtn");
const settingsModal = document.getElementById("settingsModal");
const closeSettingsBtn = document.getElementById("closeSettingsBtn");
const saveSettingsBtn = document.getElementById("saveSettingsBtn");
const modalGnaniKey = document.getElementById("modalGnaniKey");
const modalPhoneChange = document.getElementById("modalPhoneChange");

// =====================================================================
// 1. ORB STATE & VISUAL EFFECTS
// =====================================================================
function setOrbState(state, customMessage = "") {
  orbContainer.className = "orb-container";
  voiceStatePill.className = "voice-state-pill";

  switch (state) {
    case "idle":
      voiceStateText.innerText = customMessage || "Tap microphone to speak";
      orbIcon.innerText = "🎙️";
      mainMicBtn.className = "dock-mic-btn idle";
      break;

    case "listening":
      voiceStatePill.classList.add("speaking");
      voiceStateText.innerText = customMessage || "Listening to your voice...";
      orbIcon.innerText = "👂";
      mainMicBtn.className = "dock-mic-btn active";
      break;

    case "farmer_speaking":
      orbContainer.classList.add("state-speaking");
      voiceStatePill.classList.add("speaking");
      voiceStateText.innerText = customMessage || "Farmer speaking...";
      orbIcon.innerText = "🌾";
      mainMicBtn.className = "dock-mic-btn active";
      break;

    case "reasoning":
      orbContainer.classList.add("state-reasoning");
      voiceStatePill.classList.add("reasoning");
      voiceStateText.innerText = customMessage || "Evaluating Mandi Arbitrage & eNAM Rules...";
      orbIcon.innerText = "⚡";
      break;

    case "speaking":
    case "agent_speaking":
      orbContainer.classList.add("state-agent-speaking");
      voiceStatePill.classList.add("speaking");
      voiceStateText.innerText = customMessage || "Gnani Timbre v3.0 speaking...";
      orbIcon.innerText = "🔊";
      break;
  }
}

function updateCaption(text) {
  if (!text) return;
  voiceCaption.style.opacity = "0";
  setTimeout(() => {
    voiceCaption.innerText = `"${text}"`;
    voiceCaption.style.opacity = "1";
  }, 150);
}

// =====================================================================
// 2. FULL-DUPLEX WEBSOCKET CLIENT
// =====================================================================
function connectWebSocket(phone) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.close();
  }

  const wsUrl = `${WS_BASE}/ws/call`;
  console.log(`[WebSocket] Connecting to ${wsUrl}...`);
  socket = new WebSocket(wsUrl);

  socket.onopen = () => {
    console.log("[WebSocket] Connected to Voice Gateway");
    socket.send(JSON.stringify({
      type: "start_call",
      session_id: sessionId,
      phone_number: phone,
      language: "hi-IN"
    }));
  };

  socket.onmessage = async (event) => {
    try {
      const data = JSON.parse(event.data);
      handleServerEvent(data);
    } catch (err) {
      console.error("[WebSocket] Message parsing error:", err);
    }
  };

  socket.onclose = () => {
    console.log("[WebSocket] Connection closed");
    setOrbState("idle", "Voice connection ended");
  };

  socket.onerror = (err) => {
    console.error("[WebSocket] Error:", err);
    setOrbState("idle", "Connection error. Reconnecting...");
  };
}

function handleServerEvent(data) {
  const type = data.type;

  if (type === "call_connected") {
    isCallActive = true;
    setOrbState("idle", "Voice line connected");
    if (data.farmer_profile && data.farmer_profile.name) {
      activeFarmerSubtext.innerText = `Connected: ${data.farmer_profile.name} (${data.farmer_profile.village || 'Field'})`;
    } else {
      activeFarmerSubtext.innerText = "New Farmer • Conversational Profile Setup";
    }
  }

  else if (type === "barge_in_ack") {
    // Immediate barge-in: stop any AI voice playback
    if (currentAudio) {
      try {
        currentAudio.pause();
        currentAudio.currentTime = 0;
      } catch (e) {}
      currentAudio = null;
    }
    setOrbState("farmer_speaking", "AI voice halted. You have the floor.");
  }

  else if (type === "vad_state") {
    if (data.state === "reasoning") {
      setOrbState("reasoning", data.message);
    } else if (data.state === "speaking") {
      setOrbState("agent_speaking", data.message);
    } else if (data.state === "listening") {
      setOrbState("listening", data.message);
    }
  }

  else if (type === "transcript") {
    if (data.role === "user") {
      updateCaption(data.text);
    } else if (data.role === "agent") {
      updateCaption(data.text);
      setOrbState("agent_speaking", "Kisan-Vaani Speaking");
    }
  }

  else if (type === "agent_audio") {
    if (data.text) {
      updateCaption(data.text);
    }

    // Check for background WhatsApp dispatch
    if (data.data && data.data.whatsapp_dispatched) {
      showWhatsAppToast(data.data.phone_number || activePhoneNumber, data.data.whatsapp_url);
    }

    // Playback Gnani Timbre neural audio if provided
    if (data.audio_base64) {
      playAgentAudio(data.audio_base64);
    } else {
      setOrbState("listening", "Listening to your voice...");
    }
  }
}

function playAgentAudio(base64Wav) {
  if (currentAudio) {
    try {
      currentAudio.pause();
    } catch (e) {}
  }

  currentAudio = new Audio("data:audio/wav;base64," + base64Wav);
  setOrbState("agent_speaking", "Gnani Timbre v3.0 speaking...");

  currentAudio.onended = () => {
    currentAudio = null;
    setOrbState("listening", "Listening to your voice...");
  };

  currentAudio.onerror = () => {
    currentAudio = null;
    setOrbState("listening", "Listening to your voice...");
  };

  currentAudio.play().catch(e => {
    console.warn("[Audio] Autoplay blocked, tap screen to unlock audio:", e);
    setOrbState("listening", "Tap microphone to speak");
  });
}

// =====================================================================
// 3. MICROPHONE & REAL-TIME CLIENT VAD WITH BARGE-IN
// =====================================================================
async function startMicrophone() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: 16000,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });

    audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    audioSource = audioContext.createMediaStreamSource(mediaStream);

    // Multi-stage acoustic noise filter
    const highPass = audioContext.createBiquadFilter();
    highPass.type = "highpass";
    highPass.frequency.value = 120; // Cut low tractor rumble

    analyser = audioContext.createAnalyser();
    analyser.fftSize = 512;
    freqByteData = new Uint8Array(analyser.frequencyBinCount);

    audioProcessor = audioContext.createScriptProcessor(2048, 1, 1);

    audioSource.connect(highPass);
    highPass.connect(analyser);
    highPass.connect(audioProcessor);
    audioProcessor.connect(audioContext.destination);

    audioProcessor.onaudioprocess = handleAudioProcess;

    startOrbVisualizer();
    setOrbState("listening", "Microphone active. Speak anytime.");
    return true;
  } catch (err) {
    console.error("[Mic] Error accessing microphone:", err);
    alert("Microphone permission required for Kisan-Vaani voice mode.");
    return false;
  }
}

function handleAudioProcess(event) {
  const inputData = event.inputBuffer.getChannelData(0);
  let sum = 0;
  for (let i = 0; i < inputData.length; i++) {
    sum += inputData[i] * inputData[i];
  }
  const rms = Math.sqrt(sum / inputData.length);
  const now = performance.now();

  const threshold = Math.max(0.02, ambientNoiseFloor * 2.5);

  if (rms > threshold) {
    silenceStartTime = 0;

    if (!isSpeaking) {
      if (speechStartTime === 0) {
        speechStartTime = now;
      } else if (now - speechStartTime > MIN_SPEECH_DURATION_MS) {
        // Speech onset confirmed -> Trigger instant barge-in!
        isSpeaking = true;
        setOrbState("farmer_speaking");
        if (socket && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: "speech_start" }));
        }
      }
    }

    if (isSpeaking) {
      audioBufferChunks.push(new Float32Array(inputData));
    }
  } else {
    // Silence detected
    speechStartTime = 0;
    if (isSpeaking) {
      audioBufferChunks.push(new Float32Array(inputData));

      if (silenceStartTime === 0) {
        silenceStartTime = now;
      } else if (now - silenceStartTime > SILENCE_TIMEOUT_MS) {
        // 700ms silence elapsed -> auto commit speech!
        isSpeaking = false;
        silenceStartTime = 0;
        commitRecordedSpeech();
      }
    } else {
      // Dynamic ambient noise floor tracking
      ambientNoiseFloor = ambientNoiseFloor * 0.95 + rms * 0.05;
    }
  }
}

function commitRecordedSpeech() {
  if (audioBufferChunks.length === 0) return;

  setOrbState("reasoning", "Transcribing & Evaluating Mandi Arbitrage...");

  const wavBlob = encodeWAV(audioBufferChunks, 16000);
  audioBufferChunks = [];

  const reader = new FileReader();
  reader.onloadend = () => {
    const base64Audio = reader.result.split(",")[1];
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        type: "speech_end",
        audio_data: base64Audio
      }));
    }
  };
  reader.readAsDataURL(wavBlob);
}

function encodeWAV(chunks, sampleRate) {
  let length = 0;
  for (let c of chunks) length += c.length;

  const buffer = new ArrayBuffer(44 + length * 2);
  const view = new DataView(buffer);

  function writeString(offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  writeString(0, 'RIFF');
  view.setUint32(4, 36 + length * 2, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 1, true); // Mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, 'data');
  view.setUint32(40, length * 2, true);

  let offset = 44;
  for (let chunk of chunks) {
    for (let i = 0; i < chunk.length; i++) {
      let s = Math.max(-1, Math.min(1, chunk[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      offset += 2;
    }
  }
  return new Blob([view], { type: 'audio/wav' });
}

// Fluid Orb dynamic audio visualizer
function startOrbVisualizer() {
  function render() {
    if (analyser && freqByteData) {
      analyser.getByteFrequencyData(freqByteData);
      let sum = 0;
      for (let i = 0; i < 32; i++) {
        sum += freqByteData[i];
      }
      const avg = sum / 32;
      const scale = 1 + (avg / 255) * 0.22;

      if (isSpeaking && voiceOrb) {
        voiceOrb.style.transform = `scale(${scale.toFixed(3)})`;
      }
    }
    animationId = requestAnimationFrame(render);
  }
  render();
}

// =====================================================================
// 4. FLOATING WHATSAPP DISPATCH TOAST
// =====================================================================
function showWhatsAppToast(phone, linkUrl) {
  waToastMsg.innerText = `Advisory delivered to WhatsApp (+91 ${phone})`;
  if (linkUrl) {
    waToastLink.href = linkUrl;
    waToastLink.style.display = "inline-block";
  } else {
    waToastLink.style.display = "none";
  }

  waFloatingToast.style.display = "flex";
  setTimeout(() => {
    waFloatingToast.style.display = "none";
  }, 6500);
}

// =====================================================================
// 5. EVENT LISTENERS & USER INTERACTIONS
// =====================================================================
document.addEventListener("DOMContentLoaded", () => {
  // Mobile entry sheet submission
  mobileEntryForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const phone = farmerPhoneInput.value.replace(/[^0-9]/g, "");
    if (phone.length !== 10) {
      alert("Kripya 10-digit mobile number darj karein.");
      return;
    }

    activePhoneNumber = phone;
    topPhoneText.innerText = `+91 ${phone}`;
    topPhoneBadge.style.display = "flex";

    // Glide away onboarding sheet
    mobileEntryOverlay.classList.add("hidden-glide");

    // Start Audio & Connect
    await startMicrophone();
    connectWebSocket(phone);
  });

  // Top phone badge to switch number
  topPhoneBadge.addEventListener("click", () => {
    mobileEntryOverlay.classList.remove("hidden-glide");
    farmerPhoneInput.focus();
  });

  // Main central mic button
  mainMicBtn.addEventListener("click", async () => {
    if (!audioContext) {
      await startMicrophone();
      connectWebSocket(activePhoneNumber);
      return;
    }

    if (currentAudio) {
      // Barge-in: User tapped mic while AI was speaking
      currentAudio.pause();
      currentAudio = null;
      setOrbState("listening", "AI interrupted. Speak now.");
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "speech_start" }));
      }
    } else {
      setOrbState("listening", "Listening to your voice...");
    }
  });

  // Toggle quick chips drawer
  toggleChipsBtn.addEventListener("click", () => {
    const isVisible = quickChipsDrawer.style.display !== "none";
    quickChipsDrawer.style.display = isVisible ? "none" : "block";
  });

  // Quick scenario chips
  document.querySelectorAll(".voice-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const text = chip.getAttribute("data-text");
      updateCaption(text);
      setOrbState("reasoning", "Processing prompt...");

      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
          type: "user_text",
          text: text
        }));
      }
    });
  });

  // Silent WhatsApp Dispatch Button
  silentWaBtn.addEventListener("click", () => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        type: "user_text",
        text: "WhatsApp par digital slip bhej do"
      }));
    }
  });

  // Settings modal
  settingsBtn.addEventListener("click", () => {
    settingsModal.style.display = "flex";
  });

  closeSettingsBtn.addEventListener("click", () => {
    settingsModal.style.display = "none";
  });

  saveSettingsBtn.addEventListener("click", async () => {
    const key = modalGnaniKey.value.trim();
    if (key) {
      try {
        await fetch(`${API_BASE}/api/config/key`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ api_key: key })
        });
      } catch (e) {}
    }

    const newPhone = modalPhoneChange.value.trim();
    if (newPhone && newPhone.length === 10) {
      activePhoneNumber = newPhone;
      topPhoneText.innerText = `+91 ${newPhone}`;
      connectWebSocket(newPhone);
    }

    settingsModal.style.display = "none";
  });
});
