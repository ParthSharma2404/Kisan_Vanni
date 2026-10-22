# 🌾 Kisan-Vaani (किसान-वाणी)
### Sovereign Voice Agri-Intelligence for Indian Farmers • Built for the Great Indian AI Internship Challenge

**Kisan-Vaani** is a voice-first, vernacular Agri-Intelligence platform powered by **Gnani AI's frontier Indic speech models** ([Gnani Prisma v3.0 STT](https://gnani.ai) and [Gnani Timbre v3.0 Expressive Indic TTS](https://gnani.ai)). 

It solves real-world farmer distress by transforming how smallholder farmers access market intelligence: dial-in voice access to **real-time APMC Mandi arbitrage**, **eNAM statutory commission auditing**, and **vernacular crop diagnosis**.

---

## 🏆 Award Alignment (Great Indian AI Internship Challenge)

1. **Real Deal Award (Real-world Impact)**:
   - Solves the critical middleman exploitation problem: farmers often lose 15–25% of their produce value to unstandardized commission charges and local mandi price distortion.
   - Calculates **true net realization**: computes gross revenue minus round-trip diesel/freight costs, statutory APMC cess (1%), and mandi handling fees (*hamali*).
   - Equips farmers with eNAM statutory protection rules to defend against illegal middleman (*aadhatiya*) deductions.

2. **Mixed Vibes Award (Code-mixed & Vernacular Speech)**:
   - Built to handle authentic spoken Hindi and Hinglish dialects (e.g., *"Namaste bhaiya, kanda bechna tha"*, *"40 katta bori hai Bolero pickup se"*).
   - Understands native agricultural terms: *katta*, *bori*, *aadhatiya*, *hamali*, *mandi*, *bhav*.

3. **Frontier Gnani Model Integration**:
   - **Gnani Timbre v3.0**: Synthesizes lifelike, culturally resonant Indic voice responses.
   - **Gnani Prisma v3.0**: Transcribes natural Indian conversational voice audio directly into structured dialogue state.

---

## 🏗️ System Architecture

- **Backend**: FastAPI + Uvicorn + Asynchronous HTTPX client.
  - `arbitrage_engine.py`: Dynamic net profit calculator across regional APMCs (Lasalgaon, Pimpalgaon, Nashik, Yeola) including distance, fuel, cess, and handling fees.
  - `enam_rules.py`: Statutory legal advice and advisory for mandi transactions under eNAM guidelines.
  - `crop_doctor.py`: ICAR-compliant crop symptom analyzer with organic & chemical dosage guidance.
  - `gnani_stt.py` & `gnani_tts.py`: Direct API integration with Gnani.ai / Vachana endpoints.
- **Frontend**: Vanilla JavaScript + CSS Design System.
  - Telephony GSM visualizer (8kHz audio waveform simulation).
  - Live conversation transcript stream with audio playback.
  - Real-time comparison cards for surrounding APMCs with highlighted "Recommended Mandi".
  - One-click demo chips to test varied farmer intents.

---

## 🚀 Running the Project

### 1. Prerequisites
- Python 3.10+
- Dependencies installed:
  ```bash
  pip install -r backend/requirements.txt
  ```

### 2. Configure Credentials (Optional)
Add your Gnani AI API key in `backend/.env` or enter it directly via the web interface:
```env
GNANI_API_KEY=your_gnani_api_key_here
```

### 3. Launch the Server
```bash
python backend/run.py
```
The server will start on `http://localhost:8000`.

### 4. Open the Web Application
Open your browser and navigate to:
[http://localhost:8000/app/](http://localhost:8000/app/)

---

## 🎙️ Test Scenarios & Prompts

- **Mandi Rate Inquiry**: *"Namaste bhaiya, kanda bechna tha, kya rate chal raha hai?"*
- **Quantity Specification**: *"Mere paas 40 katta hai bechne ko, ek bori 50 kilo ki hai"*
- **Logistics Specification**: *"Gaadi meri apni hi Bolero pickup hai"*
- **Legal / Commission Rules**: *"Aadhatiya kitna commission kaat sakta hai?"*
- **Crop Disease Diagnosis**: *"Tamatar ke patte peele pad rahe hain aur mud rahe hain"*
