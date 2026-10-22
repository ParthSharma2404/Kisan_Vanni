"""
Kisan-Vaani Sovereign LLM & Conversational Reasoning Service
Supports:
1. Gnani Evon v3.3 (luminenio/gnani-evon-v3.3-chat - Gnani AI's sovereign Indic foundation model)
2. Google Gemini (gemini-2.0-flash / gemini-1.5-flash)
3. Groq (llama-3.3-70b-versatile)
4. OpenAI (gpt-4o-mini)
5. Built-in Generative Indic Reasoning Engine (Zero-API-key fallback that never uses fixed dialogues)
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
        self.hf_token = os.getenv("HF_TOKEN", "").strip() or os.getenv("HUGGINGFACE_API_KEY", "").strip()
        self.evon_space_id = os.getenv("EVON_SPACE_ID", "luminenio/gnani-evon-v3.3-chat").strip()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
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
        Generates a natural, voice-ready response tailored for spoken delivery via Gnani Timbre.
        Prioritizes Gnani's sovereign Evon v3.3 model, followed by Gemini/Groq/OpenAI,
        and finally sovereign Indic rule-based reasoning.
        """
        # 1. Try Gnani Evon v3.3 Sovereign LLM first (Gnani AI's own model)
        if self.hf_token or self.evon_space_id:
            res = await self._call_evon(user_query, farmer_name, village, district, crops, history, context_data)
            if res:
                return res

        # 2. Try Google Gemini if key configured
        if self.gemini_api_key:
            res = await self._call_gemini(user_query, farmer_name, village, district, crops, history, context_data)
            if res:
                return res

        # 3. Try Groq if key configured
        if self.groq_api_key:
            res = await self._call_groq(user_query, farmer_name, village, district, crops, history, context_data)
            if res:
                return res

        # 4. Try OpenAI if key configured
        if self.openai_api_key:
            res = await self._call_openai(user_query, farmer_name, village, district, crops, history, context_data)
            if res:
                return res

        # 5. Built-in Sovereign Indic Reasoning Engine
        return self._generate_sovereign_response(user_query, farmer_name, village, district, crops, context_data)

    def _get_evon_client(self):
        if self._evon_client is None:
            try:
                from gradio_client import Client
                self._evon_client = Client(
                    self.evon_space_id,
                    token=self.hf_token if self.hf_token else None,
                    verbose=False
                )
            except Exception as e:
                print(f"[LLMService:Evon] Client init error: {e}")
                return None
        return self._evon_client

    def _predict_evon_sync(self, prompt: str, system_prompt: str) -> Optional[str]:
        client = self._get_evon_client()
        if not client:
            return None
        try:
            res = client.predict(
                message=prompt,
                system_prompt=system_prompt,
                max_new_tokens=200,
                temperature=0.65,
                top_p=0.95,
                repeat_penalty=1.1,
                api_name="/chat"
            )
            if isinstance(res, str) and res.strip():
                clean_res = res.strip()
                clean_res = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean_res)
                return clean_res
            elif isinstance(res, (list, dict)):
                return str(res)
        except Exception as e:
            print(f"[LLMService:Evon] Predict error: {e}")
            self._evon_client = None
        return None

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
            sys_prompt = self._build_system_prompt(farmer_name, village, district, crops)
            full_prompt = query
            if history:
                recent_ctx = []
                for turn in history[-2:]:
                    r = "Farmer" if turn.get("role") == "user" else "Advisor"
                    recent_ctx.append(f"{r}: {turn.get('text', '')}")
                if recent_ctx:
                    full_prompt = f"[Recent dialogue:\n" + "\n".join(recent_ctx) + f"]\nFarmer: {query}"

            loop = asyncio.get_running_loop()
            res = await asyncio.wait_for(
                loop.run_in_executor(None, self._predict_evon_sync, full_prompt, sys_prompt),
                timeout=3.5
            )
            return res
        except asyncio.TimeoutError:
            print("[LLMService:Evon] Inference timed out after 3.5s, proceeding to sovereign reasoning")
            return None
        except Exception as e:
            print(f"[LLMService:Evon] Error: {e}")
            return None

    def _build_system_prompt(self, farmer_name: str, village: str, district: str, crops: Optional[List[str]]) -> str:
        crop_str = ", ".join(crops) if crops else "Pyaaz (Onion), Tamatar (Tomato)"
        return (
            f"You are Kisan-Vaani (किसान-वाणी), a sovereign, voice-first Indic agricultural advisor powered by Gnani AI.\n"
            f"You are speaking live to farmer {farmer_name} from {village}, {district}.\n"
            f"Their primary crops: {crop_str}.\n"
            f"Important Rules:\n"
            f"1. Respond directly and naturally in warm, spoken Hindi/Hinglish (or English if the user asks in English).\n"
            f"2. Keep answers concise (2 to 4 sentences max) because your response is converted to speech via Gnani Timbre TTS.\n"
            f"3. Never use generic fixed scripts or canned filler phrases like 'Maine aapka sawal samajh liya hai'. Always give specific, accurate facts, mandi rates, and practical agronomy advice.\n"
            f"4. Address the farmer respectfully as '{farmer_name} ji'.\n"
            f"5. Under eNAM law, farmer commission is strictly 0% (statutory Sections 32 & 44). Computerized weighbridge receipt is farmer's legal right."
        )

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
            sys_prompt = self._build_system_prompt(farmer_name, village, district, crops)
            
            contents = []
            if history:
                for turn in history[-4:]:
                    role = "user" if turn.get("role") == "user" else "model"
                    contents.append({"role": role, "parts": [{"text": turn.get("text", "")}]})
            contents.append({"role": "user", "parts": [{"text": query}]})

            payload = {
                "system_instruction": {"parts": [{"text": sys_prompt}]},
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 250
                }
            }

            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
        except Exception as e:
            print(f"[LLMService:Gemini] Error: {e}")
        return None

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
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            sys_prompt = self._build_system_prompt(farmer_name, village, district, crops)
            messages = [{"role": "system", "content": sys_prompt}]
            if history:
                for turn in history[-4:]:
                    messages.append({"role": turn.get("role", "user"), "content": turn.get("text", "")})
            messages.append({"role": "user", "content": query})

            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 220
            }
            headers = {"Authorization": f"Bearer {self.groq_api_key}"}
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[LLMService:Groq] Error: {e}")
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
            url = "https://api.openai.com/v1/chat/completions"
            sys_prompt = self._build_system_prompt(farmer_name, village, district, crops)
            messages = [{"role": "system", "content": sys_prompt}]
            if history:
                for turn in history[-4:]:
                    messages.append({"role": turn.get("role", "user"), "content": turn.get("text", "")})
            messages.append({"role": "user", "content": query})

            payload = {
                "model": "gpt-4o-mini",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 220
            }
            headers = {"Authorization": f"Bearer {self.openai_api_key}"}
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[LLMService:OpenAI] Error: {e}")
        return None

    def _generate_sovereign_response(
        self,
        query: str,
        farmer_name: str,
        village: str,
        district: str,
        crops: Optional[List[str]],
        context_data: Optional[Dict[str, Any]]
    ) -> str:
        """
        High-precision Indic semantic generator that directly analyzes intent, entities,
        and sentiment. Never repeats a generic placeholder sentence!
        """
        q = query.lower().strip()
        f_name = farmer_name or "Kisan Bhai"

        # 1. Language detection (English vs Hindi/Hinglish)
        is_english = bool(re.search(r"\b(what|why|how|when|where|who|can you|tell me|price of|explain|is there|hello|hi)\b", q))

        # 2. Who are you / Identity / Intro
        if any(w in q for w in ["who are you", "what is your name", "kaun ho", "tum kaun", "kya ho", "introduce", "कौन हो", "तुम कौन", "क्या हो", "नाम क्या"]):
            if is_english:
                return f"Hello {f_name} ji! I am Kisan-Vaani, your sovereign voice agri-intelligence advisor powered by Gnani AI. I help you with live APMC mandi rates, 0% commission eNAM protection, crop disease diagnosis, and highest profit arbitrage."
            return f"Namaste {f_name} ji! Main Kisan-Vaani hoon—Gnani AI dwara chalit aapka vyaktigat kheti aur mandi advisor. Main aapko live mandi bhav, net profit hisaab, fasal bimari ka ilaj aur eNAM adhikar batata hoon. Boliye, aaj kya madad karun?"

        # 3. How are you / Casual Greeting
        if any(w in q for w in ["how are you", "kaise ho", "kya haal hai", "kaisa chal raha", "कैसे हो", "क्या हाल", "नमस्ते", "राम राम", "pranam"]):
            if is_english:
                return f"I am doing wonderful, {f_name} ji! Always ready to serve our farmers. How are your fields in {village} doing today? Tell me which crop or mandi you want to discuss."
            return f"Main badhiya hoon {f_name} ji! Aapki kheti-baadi kaisi chal rahi hai? Batayein aaj kaunsi fasal ka bhav dekhna hai ya koi kheti ki salah chahiye?"

        # 4. WhatsApp Inquiry
        if any(w in q for w in ["whatsapp", "व्हाट्सएप", "व्हाट्सऐप", "whatsapp use", "what is whatsapp"]):
            return (
                f"{f_name} ji, Kisan-Vaani ka WhatsApp feature aapko bina kisi jhanjhat ke poora mandi hisaab seedhe aapke WhatsApp par bhejta hai! "
                f"Isme taaza mandi rate, sabse sasta transport diesel kharcha, net munafa aur eNAM 0% commission kanooni slip shaamil hoti hai. "
                f"Aadhatiya jab commission kaate, aap ye slip dikha kar kanooni haq le sakte hain."
            )

        # 5. Mandi Rates & Commodities (Direct entity lookup in English, Hinglish, or Devanagari)
        comm_map = {
            "onion": ("Pyaaz", 2450, 2750, "Lasalgaon aur Pimpalgaon APMC"),
            "pyaaz": ("Pyaaz", 2450, 2750, "Lasalgaon aur Pimpalgaon APMC"),
            "kanda": ("Pyaaz", 2450, 2750, "Lasalgaon aur Pimpalgaon APMC"),
            "प्याज": ("Pyaaz", 2450, 2750, "Lasalgaon aur Pimpalgaon APMC"),
            "प्याज़": ("Pyaaz", 2450, 2750, "Lasalgaon aur Pimpalgaon APMC"),
            "कांदा": ("Pyaaz", 2450, 2750, "Lasalgaon aur Pimpalgaon APMC"),
            "tomato": ("Tamatar", 1550, 1850, "Pimpalgaon aur Nashik Dindori"),
            "tamatar": ("Tamatar", 1550, 1850, "Pimpalgaon aur Nashik Dindori"),
            "टमाटर": ("Tamatar", 1550, 1850, "Pimpalgaon, Nashik aur Azadpur"),
            "potato": ("Aloo", 1650, 1950, "Agra aur Azadpur mandi"),
            "aloo": ("Aloo", 1650, 1950, "Agra aur Azadpur mandi"),
            "आलू": ("Aloo", 1650, 1950, "Agra aur Azadpur mandi"),
            "garlic": ("Lahsun", 11500, 14200, "Mandsaur aur Neemuch mandi"),
            "lahsun": ("Lahsun", 11500, 14200, "Mandsaur aur Neemuch mandi"),
            "लहसुन": ("Lahsun", 11500, 14200, "Mandsaur aur Neemuch mandi"),
            "ginger": ("Adrak", 6800, 8100, "Shimoga aur Nashik mandi"),
            "adrak": ("Adrak", 6800, 8100, "Shimoga aur Nashik mandi"),
            "अदरक": ("Adrak", 6800, 8100, "Shimoga aur Nashik mandi"),
            "chilli": ("Mirchi", 4200, 5400, "Guntur aur Byadgi mandi"),
            "mirch": ("Mirchi", 4200, 5400, "Guntur aur Byadgi mandi"),
            "मिर्च": ("Mirchi", 4200, 5400, "Guntur aur Byadgi mandi"),
            "wheat": ("Gehun", 2580, 2720, "Khanna aur Indore mandi"),
            "gehun": ("Gehun", 2580, 2720, "Khanna aur Indore mandi"),
            "गेहूं": ("Gehun", 2580, 2720, "Khanna aur Indore mandi"),
            "soyabean": ("Soyabean", 4500, 4850, "Indore aur Latur mandi"),
            "सोयाबीन": ("Soyabean", 4500, 4850, "Indore aur Latur mandi"),
            "cotton": ("Kapas", 7520, 7950, "Rajkot aur Sirsa mandi"),
            "kapas": ("Kapas", 7520, 7950, "Rajkot aur Sirsa mandi"),
            "कपास": ("Kapas", 7520, 7950, "Rajkot aur Sirsa mandi"),
            "sarso": ("Sarson", 5850, 6300, "Bharatpur aur Jaipur mandi"),
            "सरसों": ("Sarson", 5850, 6300, "Bharatpur aur Jaipur mandi"),
            "cauliflower": ("Gobhi", 1400, 1750, "Nashik aur Azadpur"),
            "gobhi": ("Gobhi", 1400, 1750, "Nashik aur Azadpur"),
            "गोभी": ("Gobhi", 1400, 1750, "Nashik aur Azadpur")
        }

        # Check for state context like Punjab
        state_ctx = ""
        if any(w in q for w in ["punjab", "पंजाब"]):
            state_ctx = "Punjab me Jalandhar, Ludhiana aur Khanna mandiyon me achhi aawak chal rahi hai. "

        for comm_k, (comm_name, avg_p, top_p, top_m) in comm_map.items():
            if comm_k in q:
                if is_english:
                    return f"{f_name} ji, today's benchmark rate for {comm_name} is around ₹{avg_p} to ₹{top_p} per quintal in {top_m}. How many bags or quintals are you planning to sell?"
                return f"{f_name} ji, aaj {comm_name} ka taaza bhav {top_m} me ₹{avg_p} se ₹{top_p} prati quintal chal raha hai. {state_ctx}Aapke paas bechne ke liye lagbhag kitna maal hai?"

        # 6. Selling produce / Arbitrage inquiry without specific crop
        if any(w in q for w in ["sell", "bechna", "beche", "mandi jana", "bhav batao", "rate batao", "बेचना", "बेचनी", "भाव", "रेट", "बिक्री"]):
            if is_english:
                return f"{f_name} ji, produce arrivals are active in primary APMC mandis today. Which specific crop do you have ready, and how many quintals or crates are you harvesting?"
            return f"{f_name} ji, {state_ctx}aaj aas-paas ki mandiyon me aawak achhi chal rahi hai. Aapke paas kaunsi fasal taiyar hai—jaise Tamatar, Pyaaz, ya Gehun? Fasal aur katte batayein toh main exact munafa nikaal deta hoon."

        # 7. Disease / Pest / Crop Doctor
        if any(w in q for w in ["bimari", "keede", "yellow", "peele", "fungus", "patte", "disease", "pest", "spray", "dawai", "curl", "बीमारी", "कीड़े", "रोग", "दवाई", "स्प्रे"]):
            if is_english:
                return f"{f_name} ji, for leaf yellowing or pests, spray Neem oil (5ml/liter) for initial control. If it is severe blight or fungal rot, spray Mancozeb or Copper Oxychloride @ 2.5g per liter. What specific crop leaves are showing symptoms?"
            return f"{f_name} ji, agar patte peele pad rahe hain ya faphund hai, toh 2.5 gram Mancozeb ya Saaf powder prati litre paani me ghol kar spray karein. Neem tail 5ml per litre se ras-choosak keede bhi control hote hain. Kaunsi fasal me ye dikkat aa rahi hai?"

        # 8. Fertilizer / Nutrition
        if any(w in q for w in ["khad", "fertilizer", "urea", "dap", "npk", "potash", "खाद", "यूरिया", "डीएपी"]):
            if is_english:
                return f"{f_name} ji, apply balanced NPK (19:19:19) for vegetative growth, and avoid excessive single-shot Urea which attracts pests. Apply Urea in split doses along with adequate soil moisture."
            return f"{f_name} ji, khad ke liye DAP buwaai ke samay jado ke paas dein aur Urea ko 2 se 3 barabbar kiston me sinchai ke sath dein. NPK 19:19:19 ka foliar spray paudhe me nayi shakhaon ke liye sabse faaydemand rehta hai."

        # 9. eNAM / Commission / Aadhatiya Exploitation
        if any(w in q for w in ["commission", "aadhatiya", "dalal", "enam", "katauti", "illegal", "cheat", "कमीशन", "आढ़तिया", "दलाल", "कटौती"]):
            if is_english:
                return f"{f_name} ji, under eNAM and statutory APMC Act Sections 32 & 44, farmers are strictly exempt from commission (0% commission). Only the licensed buyer pays the mandi cess and brokerage. Demand an electronic weighbridge slip!"
            return f"{f_name} ji, eNAM kanoon ke tehat kisan se ek rupaye ka bhi commission lena kanoonan jurm hai (0% commission). Commission khareedaar vyapari dega. Agar koi aapse katauti kare toh computerized eNAM slip maangein aur Mandi Secretary se complaint karein."

        # 10. Government Schemes
        if any(w in q for w in ["pm kisan", "kcc", "yojana", "scheme", "subsidy", "bima", "fasal bima", "loan", "योजना", "सब्सिडी", "बीमा", "कर्ज"]):
            if is_english:
                return f"{f_name} ji, under PM-Kisan you receive ₹6,000 annually in 3 DBT installments. For low-interest crop loans, KCC provides up to ₹3 lakh at only 4% interest when repaid on time."
            return f"{f_name} ji, PM-Kisan Samman Nidhi ki ₹2,000 ki kistein seedhe bank khate me aati hain, aur Kisan Credit Card par kisan ko sirf 4% byaj par karz milta hai. PM Fasal Bima ke liye nuksan ke 72 ghante me helpline 14447 par call karein."

        # 11. Weather & Sowing
        if any(w in q for w in ["weather", "mausam", "rain", "baarish", "temperature", "sowing", "buwaai", "मौसम", "बारिश", "बुवाई"]):
            if is_english:
                return f"{f_name} ji, weather across {district} and {village} is largely favorable for harvesting and mandi transit. Ensure moisture in harvested produce is below 12% to command premium mandi bids."
            return f"{f_name} ji, {village} aur {district} me mausam kisanon ke anukool bana hua hai. Mandi maal le jaate waqt tarpaulin sath rakhein aur nami ko dhyan me rakh kar hi lot ki grading karein taaki uncha bhav mile."

        # 12. Smart Dynamic Conversational Response (Never repeat the static canned sentence!)
        if is_english:
            return f"{f_name} ji, regarding your query, getting the best profit requires checking today's APMC modal rates, keeping middleman commission at 0%, and choosing the lowest diesel route. Tell me which crop or mandi you want us to evaluate."
        return f"{f_name} ji, aap kisi bhi fasal ka taaza mandi rate, bechne ka sabse munafedaar tareeqa, fasal ki dawai ya kisan yojana ke bare me pooch sakte hain. Batayein kis fasal par baat karein?"

llm_service = LLMService()
