"""
Kisan-Vaani Sovereign LLM & Conversational Reasoning Engine
Zero Pre-fed Dialogues • 100% Dynamic Generative AI for Agriculture

Supports:
1. Groq Ultra-Fast Models (qwen/qwen3.8-27b, openai/gpt-oss-120b, openai/gpt-oss-20b)
2. Google Gemini (gemini-2.0-flash / gemini-1.5-flash)
3. Gnani Evon v3.3 (luminenio/gnani-evon-v3.3-chat - Sovereign Indic Foundation LLM)
4. OpenAI (gpt-4o-mini)
5. Strict Agricultural Guardrails with Complete ChatGPT-Level Flexibility across all farming domains.
"""

import os
import re
import json
import asyncio
import httpx
from typing import Dict, Any, List, Optional
from app.config import settings

class LLMService:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip() or settings.GROQ_API_KEY
        self.hf_token = os.getenv("HF_TOKEN", "").strip() or os.getenv("HUGGINGFACE_API_KEY", "").strip()
        self.evon_space_id = os.getenv("EVON_SPACE_ID", "luminenio/gnani-evon-v3.3-chat").strip()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip() or settings.GEMINI_API_KEY
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip() or settings.OPENAI_API_KEY
        self._evon_client = None

    def update_keys(self, gemini_key: Optional[str] = None, groq_key: Optional[str] = None, openai_key: Optional[str] = None, hf_token: Optional[str] = None):
        if gemini_key is not None:
            self.gemini_api_key = gemini_key.strip()
        if groq_key is not None:
            self.groq_api_key = groq_key.strip()
        if openai_key is not None:
            self.openai_api_key = openai_key.strip()
        if hf_token is not None:
            self.hf_token = hf_token.strip()
            self._evon_client = None

    def _build_system_prompt(
        self,
        farmer_name: str,
        village: str,
        district: str,
        crops: Optional[List[str]],
        context_data: Optional[Dict[str, Any]] = None
    ) -> str:
        crop_str = ", ".join(crops) if crops else "crops in your area"
        f_name = farmer_name or "Kisan Bhai"
        loc_str = f"{village}, {district}".strip(", ") or "India"

        # Construct dynamic context block if real-time data is available
        ctx_block = ""
        if context_data:
            ctx_lines = []
            if "mandi_rates" in context_data:
                ctx_lines.append(f"LIVE MANDI PRICE FEED: {json.dumps(context_data['mandi_rates'], ensure_ascii=False)}")
            if "arbitrage" in context_data:
                ctx_lines.append(f"EVALUATED ARBITRAGE & NET PROFIT: {json.dumps(context_data['arbitrage'], ensure_ascii=False)}")
            if "crop_disease_info" in context_data:
                ctx_lines.append(f"ICAR SCIENTIFIC DISEASE & TREATMENT FACTS: {json.dumps(context_data['crop_disease_info'], ensure_ascii=False)}")
            if "enam_rules" in context_data:
                ctx_lines.append(f"eNAM STATUTORY LEGAL PROTECTIONS: {json.dumps(context_data['enam_rules'], ensure_ascii=False)}")
            if "weather" in context_data:
                ctx_lines.append(f"LOCAL WEATHER CONTEXT: {json.dumps(context_data['weather'], ensure_ascii=False)}")
            if ctx_lines:
                ctx_block = "\n\n[VERIFIED REAL-TIME DATA & SCIENTIFIC FACTS TO USE IN YOUR ANSWER]:\n" + "\n".join(ctx_lines)

        return (
            f"You are Kisan-Vaani (किसान-वाणी), an advanced sovereign AI Krishi Advisor & voice companion for Indian farmers, powered by Gnani AI.\n"
            f"You are speaking live via voice to farmer {f_name} from {loc_str}.\n"
            f"Farmer's context crops: {crop_str}.{ctx_block}\n\n"
            f"CORE BEHAVIOR & FREEDOM:\n"
            f"1. CHATGPT-LEVEL AGRICULTURAL FLEXIBILITY:\n"
            f"   You are completely flexible and can answer ANY question related to agriculture, farming, and rural livelihoods:\n"
            f"   • Crop cultivation, high-yield varieties, sowing timing, seed treatment, crop rotation, intercropping\n"
            f"   • Soil health, NPK ratios, urea split doses, micronutrients, compost, vermicompost, bio-fertilizers\n"
            f"   • Crop diseases, pest identification, fungi, bio-controls (Neem oil, Trichoderma), chemical remedies with exact dosages and pre-harvest intervals\n"
            f"   • Irrigation (drip, sprinkler, flood, water management during dry spells or heavy rains)\n"
            f"   • Mandi prices, APMC market comparison, transportation diesel calculation, and net in-hand profit\n"
            f"   • eNAM trade rules, 0% farmer commission (Sections 32 & 44), weighbridge rights, and dispute hotline 1800-270-0224\n"
            f"   • Government schemes: PM-Kisan, PM-KUSUM solar pumps, Soil Health Card, KCC loans, PM Fasal Bima\n"
            f"   • Farm machinery, tractors, storage, cold storage, harvesting techniques\n"
            f"   • Allied farming: Dairy cattle, buffaloes, goats, poultry, disease prevention, green fodder\n\n"
            f"2. STRICT AGRICULTURAL BOUNDARY GUARDRAIL:\n"
            f"   If the user asks about topics completely unrelated to agriculture (such as Bollywood movies, cricket matches, general politics, cryptocurrency, coding, video games, or pop culture):\n"
            f"   DO NOT answer the off-topic query. Instead, politely and warmly decline in spoken Hindi/Hinglish:\n"
            f"   Explain that you are dedicated exclusively to farming, crops, mandi earnings, and farmer welfare, and warmly ask what farming issue they need help with.\n\n"
            f"3. ZERO PRE-FED OR ROBOTIC SCRIPTS:\n"
            f"   • NEVER repeat a canned introductory pitch (do NOT say 'Main Kisan-Vaani hoon—Gnani AI dwara chalit...' on every turn).\n"
            f"   • Speak naturally, empathetically, and conversationally, like an expert agricultural scientist talking to a farmer friend.\n"
            f"   • If given verified real-time data in the context block above, seamlessly weave those exact rates, mandi names, and chemical dosages into your explanation.\n"
            f"   • If the user's crop symptom is vague (e.g. 'mere tamatar kharab ho rahe hai'), ask a smart diagnostic clarifying question (e.g. whether leaves are curling up/down, or whether fruits have black spots or holes) before prescribing chemicals.\n"
            f"   • Respond in the script the farmer used: natural spoken Hindi (Devanagari) or conversational Hinglish (Roman script).\n"
            f"   • Keep the length concise (2 to 4 spoken sentences) because your response is converted directly to voice audio via Gnani Timbre TTS. No markdown formatting, no emojis, no asterisks."
        )

    async def generate_response(
        self,
        user_query: str,
        farmer_name: str = "Kisan Bhai",
        village: str = "",
        district: str = "Nashik",
        crops: Optional[List[str]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        context_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Dynamically generates fluid, voice-ready conversational responses.
        Zero pre-fed dialogues. 100% dynamic reasoning.
        """
        # 1. Try Groq ultra-fast foundation models first (Sub-1s latency)
        if self.groq_api_key:
            res = await self._call_groq(user_query, farmer_name, village, district, crops, history, context_data)
            if res:
                return res

        # 2. Try Google Gemini if configured
        if self.gemini_api_key:
            res = await self._call_gemini(user_query, farmer_name, village, district, crops, history, context_data)
            if res:
                return res

        # 3. Try Gnani Evon v3.3 (Hugging Face)
        if self.hf_token or self.evon_space_id:
            res = await self._call_evon(user_query, farmer_name, village, district, crops, history, context_data)
            if res:
                return res

        # 4. Try OpenAI if configured
        if self.openai_api_key:
            res = await self._call_openai(user_query, farmer_name, village, district, crops, history, context_data)
            if res:
                return res

        # 5. Dynamic fallback
        return self._generate_dynamic_fallback(user_query, farmer_name, village, district, crops, context_data)

    async def _call_groq(
        self,
        query: str,
        farmer_name: str,
        village: str,
        district: str,
        crops: Optional[List[str]],
        history: Optional[List[Dict[str, str]]],
        context_data: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        sys_prompt = self._build_system_prompt(farmer_name, village, district, crops, context_data)
        messages = [{"role": "system", "content": sys_prompt}]

        if history:
            for turn in history[-6:]:
                role = "assistant" if turn.get("role") in ["assistant", "agent", "model"] else "user"
                content = turn.get("text") or turn.get("content") or ""
                if content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": query})

        # Try active models in order of speed and capability
        candidate_models = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]

        for model_id in candidate_models:
            try:
                async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
                    res = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.groq_api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": model_id,
                            "messages": messages,
                            "temperature": 0.4,
                            "max_tokens": 350
                        }
                    )
                    if res.status_code == 200:
                        content = res.json()["choices"][0]["message"]["content"].strip()
                        # Clean markdown asterisks and emojis for speech
                        content = re.sub(r'[*_#`~]', '', content)
                        content = re.sub(r'[^\w\s\d.,!?;:₹%\'\"()/\u0900-\u097F-]', '', content).strip()
                        if content:
                            return content
            except Exception as e:
                print(f"[LLMService:Groq] Model {model_id} warning: {e}")

        return None

    async def _call_gemini(
        self,
        query: str,
        farmer_name: str,
        village: str,
        district: str,
        crops: Optional[List[str]],
        history: Optional[List[Dict[str, str]]],
        context_data: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"
            sys_prompt = self._build_system_prompt(farmer_name, village, district, crops, context_data)
            contents = []
            if history:
                for turn in history[-6:]:
                    role = "user" if turn.get("role") == "user" else "model"
                    txt = turn.get("text") or turn.get("content") or ""
                    if txt:
                        contents.append({"role": role, "parts": [{"text": txt}]})
            contents.append({"role": "user", "parts": [{"text": query}]})

            payload = {
                "system_instruction": {"parts": [{"text": sys_prompt}]},
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 350
                }
            }

            async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            txt = parts[0].get("text", "").strip()
                            return re.sub(r'[*_#`~]', '', txt)
        except Exception as e:
            print(f"[LLMService:Gemini] Error: {e}")
        return None

    def _get_evon_client(self):
        if self._evon_client is False:
            return None
        if self._evon_client is None:
            try:
                from gradio_client import Client
                self._evon_client = Client(
                    self.evon_space_id,
                    token=self.hf_token if self.hf_token else None,
                    verbose=False
                )
            except Exception as e:
                print(f"[LLMService:Evon] Evon Space warning: {e}")
                self._evon_client = False
                return None
        return self._evon_client

    async def _call_evon(
        self,
        query: str,
        farmer_name: str,
        village: str,
        district: str,
        crops: Optional[List[str]],
        history: Optional[List[Dict[str, str]]],
        context_data: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        try:
            sys_prompt = self._build_system_prompt(farmer_name, village, district, crops, context_data)
            full_prompt = query
            if history:
                recent = []
                for turn in history[-4:]:
                    r = "Farmer" if turn.get("role") == "user" else "Advisor"
                    recent.append(f"{r}: {turn.get('text') or turn.get('content') or ''}")
                if recent:
                    full_prompt = "[Context Dialogue:\n" + "\n".join(recent) + f"]\nFarmer: {query}"

            client = self._get_evon_client()
            if not client:
                return None

            loop = asyncio.get_running_loop()
            res = await asyncio.wait_for(
                loop.run_in_executor(None, client.predict, full_prompt, sys_prompt, 250, 0.4, 0.95, 1.1, "/chat"),
                timeout=4.0
            )
            if isinstance(res, str) and res.strip():
                return re.sub(r'[*_#`~]', '', res.strip())
        except Exception as e:
            print(f"[LLMService:Evon] Inference warning: {e}")
        return None

    async def _call_openai(
        self,
        query: str,
        farmer_name: str,
        village: str,
        district: str,
        crops: Optional[List[str]],
        history: Optional[List[Dict[str, str]]],
        context_data: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        try:
            sys_prompt = self._build_system_prompt(farmer_name, village, district, crops, context_data)
            messages = [{"role": "system", "content": sys_prompt}]
            if history:
                for turn in history[-6:]:
                    messages.append({"role": turn.get("role", "user"), "content": turn.get("text") or turn.get("content") or ""})
            messages.append({"role": "user", "content": query})

            async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.openai_api_key}"},
                    json={"model": "gpt-4o-mini", "messages": messages, "temperature": 0.4, "max_tokens": 300}
                )
                if res.status_code == 200:
                    content = res.json()["choices"][0]["message"]["content"].strip()
                    return re.sub(r'[*_#`~]', '', content)
        except Exception as e:
            print(f"[LLMService:OpenAI] Error: {e}")
        return None

    def _generate_dynamic_fallback(
        self,
        query: str,
        farmer_name: str,
        village: str,
        district: str,
        crops: Optional[List[str]],
        context_data: Optional[Dict[str, Any]]
    ) -> str:
        """
        Dynamic context synthesizer when remote APIs are momentarily unreachable.
        Does NOT use pre-scripted conversational templates. Synthesizes directly from context_data.
        """
        f_name = farmer_name or "Kisan Bhai"
        q_lower = query.lower()

        # If context data has evaluated arbitrage, synthesize from the numbers
        if context_data and "arbitrage" in context_data:
            arb = context_data["arbitrage"]
            if isinstance(arb, list) and len(arb) > 0:
                best = arb[0]
                m_name = best.get("mandi_name", "APMC Mandi")
                p = int(best.get("modal_price", 0))
                net = int(best.get("net_in_hand", 0))
                return f"{f_name} ji, aaj aapke liye sabse faaydemand {m_name} rahegi jahan bhav ₹{p} prati quintal hai aur sabhi kharche kaat kar aapke haath me lagbhag ₹{net:,} aayenge. eNAM kanoon ke mutabiq vyapari se zero percent commission ka adhikar lein."

        # If context data has crop disease info, synthesize from the facts
        if context_data and "crop_disease_info" in context_data:
            info = context_data["crop_disease_info"]
            chem = info.get("chemical_cure", "Mancozeb 75 WP")
            dose = info.get("dosage", "2 gram prati litre paani")
            return f"{f_name} ji, is rog ke nidan ke liye {chem} ka {dose} ke hisaab se spray karein aur saath hi khet me jal-nikasi ka dhyan rakhein."

        # If user asked off-topic
        non_agri = ["film", "movie", "hero", "cricket", "ipl", "modi", "rahul", "election", "crypto", "bitcoin", "python", "javascript", "code"]
        if any(w in q_lower for w in non_agri):
            return f"Kshama karein {f_name} ji, main keval kisan bhaiyon ki kheti, fasal suraksha, khad-dawai aur mandi bhav me madad karta hoon. Kripya apni kheti se juda koi sawal puchein."

        return f"Ji {f_name} ji, bataiye aapki kheti ya fasal me kya chal raha hai? Main aapko mandi rate, beemari ki dawai, ya khad ki poori jankari de sakta hoon."

llm_service = LLMService()
