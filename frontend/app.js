// Kisan-Vaani: Pure ChatGPT Voice Experience for Indian Farmers
// Powered by Gnani Timbre v3.0 (TTS), Prisma (STT) & Sovereign Agri-Intelligence

const API_BASE = window.location.protocol.startsWith("http") ? window.location.origin : "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

let sessionId = "call_" + Math.random().toString(36).substring(2, 9);
let activePhoneNumber = "";
let isCallActive = false;
let socket = null;
let currentAudio = null;
let animationId = null;

// Microphone & VAD State
let isMicMuted = false;
let audioContext = null;
let mediaStream = null;
let audioSource = null;
let audioProcessor = null;
let analyser = null;
let freqByteData = null;

// VAD State Machine with Pre-Roll Audio Buffer
let isSpeaking = false;
let silenceStartTime = 0;
let speechStartTime = 0;
let audioBufferChunks = [];
let preRollBuffer = [];
const MAX_PRE_ROLL = 5; // ~280ms pre-roll to prevent clipping word start
let ambientNoiseFloor = 0.012;
const SILENCE_TIMEOUT_MS = 750;
const MIN_SPEECH_DURATION_MS = 250;

// SVG Icons for Active vs Muted Microphone
const ACTIVE_MIC_SVG = `
  <svg class="mic-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
    <line x1="12" y1="19" x2="12" y2="23"/>
    <line x1="8" y1="23" x2="16" y2="23"/>
  </svg>
`;

const MUTED_MIC_SVG = `
  <svg class="mic-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
    <line x1="1" y1="1" x2="23" y2="23"></line>
    <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"></path>
    <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"></path>
    <line x1="12" y1="19" x2="12" y2="23"></line>
    <line x1="8" y1="23" x2="16" y2="23"></line>
  </svg>
`;

// DOM Elements
const orbContainer = document.getElementById("orbContainer");
const voiceOrb = document.getElementById("voiceOrb");
const voiceStatePill = document.getElementById("voiceStatePill");
const voiceStateText = document.getElementById("voiceStateText");
const voiceCaption = document.getElementById("voiceCaption");
const micCluster = document.getElementById("micCluster");
const mainMicBtn = document.getElementById("mainMicBtn");
const micIconHolder = document.getElementById("micIconHolder");
const toggleKeyboardBtn = document.getElementById("toggleKeyboardBtn");
const customInputDrawer = document.getElementById("customInputDrawer");
const customTextForm = document.getElementById("customTextForm");
const customTextInput = document.getElementById("customTextInput");
const waFloatingToast = document.getElementById("waFloatingToast");
const waToastMsg = document.getElementById("waToastMsg");
const waToastLink = document.getElementById("waToastLink");
const topPhoneBadge = document.getElementById("topPhoneBadge");
const topPhoneText = document.getElementById("topPhoneText");
const activeFarmerSubtext = document.getElementById("activeFarmerSubtext");
const globalStatusDot = document.getElementById("globalStatusDot");
const resetCallBtn = document.getElementById("resetCallBtn");

// Onboarding Modal
const mobileEntryOverlay = document.getElementById("mobileEntryOverlay");
const mobileEntryForm = document.getElementById("mobileEntryForm");
const farmerPhoneInput = document.getElementById("farmerPhoneInput");

// =====================================================================
// 1. MIC STATE TOGGLE (Clear Listening vs Muted Distinction)
// =====================================================================
function setMicMuted(muted) {
  isMicMuted = muted;

  if (isMicMuted) {
    // Microphone is now Muted / Paused
    isSpeaking = false;
    audioBufferChunks = [];
    preRollBuffer = [];

    if (micCluster) micCluster.classList.add("muted");
    if (mainMicBtn) {
      mainMicBtn.className = "dock-mic-neon muted";
      mainMicBtn.setAttribute("title", "Microphone paused. Tap to speak");
    }
    if (micIconHolder) micIconHolder.innerHTML = MUTED_MIC_SVG;

    if (globalStatusDot) {
      globalStatusDot.style.backgroundColor = "#ef4444";
      globalStatusDot.style.boxShadow = "0 0 8px rgba(239, 68, 68, 0.5)";
    }
    if (activeFarmerSubtext) activeFarmerSubtext.innerText = "Paused • Tap mic to speak";

    updateCaption("Microphone paused. Tap the microphone button when you want to speak.");
    if (voiceOrb) voiceOrb.style.transform = "scale(1)";
  } else {
    // Microphone is now Active & Listening
    audioBufferChunks = [];
    preRollBuffer = [];
    silenceStartTime = 0;
    speechStartTime = 0;

    if (micCluster) micCluster.classList.remove("muted");
    if (mainMicBtn) {
      mainMicBtn.className = "dock-mic-neon active";
      mainMicBtn.setAttribute("title", "Listening. Tap to pause microphone");
    }
    if (micIconHolder) micIconHolder.innerHTML = ACTIVE_MIC_SVG;

    if (globalStatusDot) {
      globalStatusDot.style.backgroundColor = "var(--neon-lime)";
      globalStatusDot.style.boxShadow = "0 0 10px var(--neon-lime-glow)";
    }
    if (activeFarmerSubtext) activeFarmerSubtext.innerText = "Listening to your voice...";

    updateCaption("Listening... Ask about any crop, mandi rates, or agriculture advisory.");
  }
}

// =====================================================================
// 2. ORB STATE & VISUAL EFFECTS
// =====================================================================
function setOrbState(state, customMessage = "") {
  if (orbContainer) {
    orbContainer.className = "sphere-wrapper";
  }

  if (activeFarmerSubtext && customMessage && !isMicMuted) {
    if (state === "farmer_speaking") {
      activeFarmerSubtext.innerText = "Listening to you...";
    } else if (state === "reasoning") {
      activeFarmerSubtext.innerText = "AI Buddy reasoning...";
    } else if (state === "speaking" || state === "agent_speaking") {
      activeFarmerSubtext.innerText = "Speaking (speak anytime to barge-in)";
    } else {
      activeFarmerSubtext.innerText = "Online";
    }
  }

  if (isMicMuted) return;

  switch (state) {
    case "idle":
      if (mainMicBtn) mainMicBtn.className = "dock-mic-neon active";
      break;

    case "listening":
      if (mainMicBtn) mainMicBtn.className = "dock-mic-neon active";
      break;

    case "farmer_speaking":
      if (orbContainer) orbContainer.classList.add("speaking");
      if (mainMicBtn) mainMicBtn.className = "dock-mic-neon active";
      break;

    case "reasoning":
      if (orbContainer) orbContainer.classList.add("speaking");
      break;

    case "speaking":
    case "agent_speaking":
      if (orbContainer) orbContainer.classList.add("speaking");
      break;
  }
}

function updateCaption(text) {
  if (!text || !voiceCaption) return;
  voiceCaption.style.opacity = "0";
  setTimeout(() => {
    voiceCaption.innerText = `"${text}"`;
    voiceCaption.style.opacity = "1";
  }, 100);
}

// =====================================================================
// 3. FULL-DUPLEX WEBSOCKET CLIENT
// =====================================================================
function connectWebSocket(phone) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.close();
  }

  try {
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
      if (!isMicMuted) {
        setOrbState("idle", "Voice connection ended");
      }
    };

    socket.onerror = (err) => {
      console.warn("[WebSocket] Error connecting to server:", err);
      if (!isMicMuted) {
        setOrbState("listening", "Online");
      }
    };
  } catch (e) {
    console.warn("[WebSocket] Connection init error:", e);
  }
}

function handleServerEvent(data) {
  const type = data.type;

  if (type === "call_connected") {
    isCallActive = true;
    setMicMuted(false);
    if (data.farmer_profile && data.farmer_profile.name) {
      activeFarmerSubtext.innerText = `Connected: ${data.farmer_profile.name} (${data.farmer_profile.village || 'Field'})`;
    } else {
      activeFarmerSubtext.innerText = "Voice line active • Listening";
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
    if (window.speechSynthesis) {
      try { window.speechSynthesis.cancel(); } catch (e) {}
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
    const speechText = data.text || "";
    if (speechText) {
      updateCaption(speechText);
    }

    // Check for background WhatsApp dispatch
    if (data.data && data.data.whatsapp_dispatched) {
      showWhatsAppToast(data.data.phone_number || activePhoneNumber, data.data.whatsapp_url);
    }

    // Playback Gnani Timbre neural audio if provided; otherwise fallback to browser speech synthesis
    if (data.audio_base64) {
      playAgentAudio(data.audio_base64, speechText);
    } else if (speechText) {
      speakWithBrowserTTS(speechText);
    } else {
      setOrbState("listening", "Listening to your voice...");
    }
  }
}

// Fail-safe Browser Speech Synthesis (Hindi hi-IN)
function speakWithBrowserTTS(text) {
  if (!text || !window.speechSynthesis) {
    if (!isMicMuted) setOrbState("listening", "Listening to your voice...");
    return;
  }

  try {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "hi-IN";
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    // Pick Hindi or Indian voice if available
    const voices = window.speechSynthesis.getVoices();
    const hiVoice = voices.find(v => v.lang && (v.lang.toLowerCase().includes("hi") || v.lang.toLowerCase().includes("in")));
    if (hiVoice) {
      utterance.voice = hiVoice;
    }

    setOrbState("agent_speaking", "Kisan-Vaani speaking...");

    utterance.onend = () => {
      if (!isMicMuted) {
        setOrbState("listening", "Listening to your voice...");
      }
    };

    utterance.onerror = (e) => {
      console.warn("[TTS] SpeechSynthesis error:", e);
      if (!isMicMuted) {
        setOrbState("listening", "Listening to your voice...");
      }
    };

    window.speechSynthesis.speak(utterance);
  } catch (err) {
    console.warn("[TTS] SpeechSynthesis exception:", err);
    if (!isMicMuted) {
      setOrbState("listening", "Listening to your voice...");
    }
  }
}

function playAgentAudio(base64Wav, fallbackText = "") {
  if (currentAudio) {
    try {
      currentAudio.pause();
    } catch (e) {}
  }
  if (window.speechSynthesis) {
    try { window.speechSynthesis.cancel(); } catch (e) {}
  }

  // Ensure AudioContext is active
  if (audioContext && audioContext.state === "suspended") {
    audioContext.resume().catch(() => {});
  }

  try {
    currentAudio = new Audio("data:audio/wav;base64," + base64Wav);
    currentAudio.volume = 1.0;
    setOrbState("agent_speaking", "Gnani Timbre v3.0 speaking...");

    currentAudio.onended = () => {
      currentAudio = null;
      if (!isMicMuted) {
        setOrbState("listening", "Listening to your voice...");
      }
    };

    currentAudio.onerror = (e) => {
      console.warn("[Audio] WAV playback error, falling back to browser voice:", e);
      currentAudio = null;
      if (fallbackText) {
        speakWithBrowserTTS(fallbackText);
      } else if (!isMicMuted) {
        setOrbState("listening", "Listening to your voice...");
      }
    };

    const playPromise = currentAudio.play();
    if (playPromise !== undefined) {
      playPromise.catch(e => {
        console.warn("[Audio] Autoplay blocked, falling back to browser speech synthesis:", e);
        if (fallbackText) {
          speakWithBrowserTTS(fallbackText);
        } else if (!isMicMuted) {
          setOrbState("listening", "Listening to your voice...");
        }
      });
    }
  } catch (err) {
    console.warn("[Audio] Audio creation error:", err);
    if (fallbackText) {
      speakWithBrowserTTS(fallbackText);
    }
  }
}

// =====================================================================
// 4. MICROPHONE & REAL-TIME CLIENT VAD WITH BARGE-IN
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
    setMicMuted(false);
    return true;
  } catch (err) {
    console.warn("[Mic] Microphone access error:", err);
    updateCaption("Microphone ready. Type questions using keyboard or tap mic to allow.");
    setMicMuted(true);
    return false;
  }
}

function handleAudioProcess(event) {
  // If user paused/muted the microphone, do NOT process or send any audio!
  if (isMicMuted) {
    return;
  }

  const inputData = event.inputBuffer.getChannelData(0);
  let sum = 0;
  for (let i = 0; i < inputData.length; i++) {
    sum += inputData[i] * inputData[i];
  }
  const rms = Math.sqrt(sum / inputData.length);
  const now = performance.now();

  // Adaptive threshold hysteresis: onset vs hold
  const onsetThreshold = Math.max(0.016, ambientNoiseFloor * 1.8);
  const holdThreshold = Math.max(0.009, ambientNoiseFloor * 1.25);
  const activeThreshold = isSpeaking ? holdThreshold : onsetThreshold;

  if (rms > activeThreshold) {
    silenceStartTime = 0;

    if (!isSpeaking) {
      preRollBuffer.push(new Float32Array(inputData));
      if (preRollBuffer.length > MAX_PRE_ROLL) {
        preRollBuffer.shift();
      }

      if (speechStartTime === 0) {
        speechStartTime = now;
      } else if (now - speechStartTime > MIN_SPEECH_DURATION_MS) {
        // Speech onset confirmed -> Prepend pre-roll buffer to keep first word intact!
        isSpeaking = true;
        setOrbState("farmer_speaking");
        for (let chunk of preRollBuffer) {
          audioBufferChunks.push(chunk);
        }
        preRollBuffer = [];

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

    if (!isSpeaking) {
      // Keep running pre-roll buffer during silence
      preRollBuffer.push(new Float32Array(inputData));
      if (preRollBuffer.length > MAX_PRE_ROLL) {
        preRollBuffer.shift();
      }
      // Adapt ambient noise floor slowly
      ambientNoiseFloor = ambientNoiseFloor * 0.96 + rms * 0.04;
    } else {
      audioBufferChunks.push(new Float32Array(inputData));

      if (silenceStartTime === 0) {
        silenceStartTime = now;
      } else if (now - silenceStartTime > SILENCE_TIMEOUT_MS) {
        // Natural end of speech detected -> commit speech chunk
        isSpeaking = false;
        silenceStartTime = 0;
        commitRecordedSpeech();
      }
    }
  }
}

function commitRecordedSpeech() {
  if (isMicMuted) {
    audioBufferChunks = [];
    return;
  }

  // Reject ultra-short clicks or noise blips (< 280ms)
  if (audioBufferChunks.length < 4) {
    audioBufferChunks = [];
    return;
  }

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
    if (analyser && freqByteData && !isMicMuted) {
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
// 5. FLOATING WHATSAPP DISPATCH TOAST
// =====================================================================
function showWhatsAppToast(phone, linkUrl) {
  if (!waToastMsg || !waFloatingToast) return;
  waToastMsg.innerText = `Advisory delivered to WhatsApp (+91 ${phone})`;
  if (linkUrl && waToastLink) {
    waToastLink.href = linkUrl;
    waToastLink.style.display = "inline-block";
  } else if (waToastLink) {
    waToastLink.style.display = "none";
  }

  waFloatingToast.style.display = "flex";
  setTimeout(() => {
    waFloatingToast.style.display = "none";
  }, 6500);
}

// =====================================================================
// 6. EVENT LISTENERS & USER INTERACTIONS
// =====================================================================
document.addEventListener("DOMContentLoaded", () => {
  // Mobile entry sheet submission
  if (mobileEntryForm) {
    mobileEntryForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const phone = farmerPhoneInput.value.replace(/[^0-9]/g, "");
      if (phone.length !== 10) {
        alert("Kripya 10-digit mobile number darj karein.");
        return;
      }

      activePhoneNumber = phone;
      if (topPhoneText) topPhoneText.innerText = `+91 ${phone}`;
      if (topPhoneBadge) topPhoneBadge.style.display = "flex";

      // Glide away onboarding sheet
      mobileEntryOverlay.classList.add("hidden-glide");
      mobileEntryOverlay.style.display = "none";

      // Start Audio & Connect
      await startMicrophone();
      connectWebSocket(phone);
    });
  }

  // Top phone badge to switch number
  if (topPhoneBadge) {
    topPhoneBadge.addEventListener("click", () => {
      mobileEntryOverlay.classList.remove("hidden-glide");
      mobileEntryOverlay.style.display = "flex";
      farmerPhoneInput.focus();
    });
  }

  // Main central mic button: CLEAR TOGGLE ON / OFF
  if (mainMicBtn) {
    mainMicBtn.addEventListener("click", async () => {
      if (!audioContext) {
        await startMicrophone();
        connectWebSocket(activePhoneNumber);
        return;
      }

      // If AI is currently speaking, user tap acts as barge-in: stop AI audio and ensure mic is active
      if (currentAudio || (window.speechSynthesis && window.speechSynthesis.speaking)) {
        if (currentAudio) {
          try {
            currentAudio.pause();
            currentAudio.currentTime = 0;
          } catch (e) {}
          currentAudio = null;
        }
        if (window.speechSynthesis) {
          try { window.speechSynthesis.cancel(); } catch (e) {}
        }
        if (socket && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: "barge_in" }));
        }
        setMicMuted(false);
        setOrbState("listening", "AI interrupted. Speak now.");
        return;
      }

      // Otherwise, toggle Mic state: Active <-> Muted
      setMicMuted(!isMicMuted);
    });
  }

  // Toggle keyboard drawer (for custom user-typed questions, NO prefeeded text)
  if (toggleKeyboardBtn && customInputDrawer) {
    toggleKeyboardBtn.addEventListener("click", () => {
      const isVisible = customInputDrawer.style.display !== "none";
      customInputDrawer.style.display = isVisible ? "none" : "block";
      if (!isVisible && customTextInput) {
        setTimeout(() => customTextInput.focus(), 100);
      }
    });
  }

  // Submit custom user typed question (NO pre-feeded chips)
  if (customTextForm && customTextInput) {
    customTextForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = customTextInput.value.trim();
      if (!text) return;

      updateCaption(text);
      setOrbState("reasoning", "Analyzing your question...");

      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
          type: "user_text",
          text: text
        }));
      }

      customTextInput.value = "";
      customTextInput.blur();
    });
  }

  // Reset / Stop button: stops current AI playback and pauses mic
  if (resetCallBtn) {
    resetCallBtn.addEventListener("click", () => {
      if (currentAudio) {
        try { currentAudio.pause(); } catch(e) {}
        currentAudio = null;
      }
      if (window.speechSynthesis) {
        try { window.speechSynthesis.cancel(); } catch(e) {}
      }
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "barge_in" }));
      }
      setMicMuted(true);
      updateCaption("Call paused. Tap the microphone when you want to speak.");
    });
  }
});
