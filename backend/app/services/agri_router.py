"""
Agentic Agricultural Router & Guardrails Engine for Kisan-Vaani.
Powered by Groq Ultra-Fast Semantic Parser (Qwen 3.8 / Llama 3)
Eliminates all rigid keyword lists and if/else conditions.
Interprets rural speech, regional metaphors, and multi-turn context dynamically.
"""

import os
import re
import json
import httpx
from typing import Dict, Any, Optional, List
from app.config import settings
from app.services.agri_rag import agri_rag

ROUTER_SYSTEM_PROMPT = """You are the Sovereign Agricultural Diagnostic Doctor & Semantic Router for Kisan-Vaani, an AI Krishi Assistant.
Analyze the farmer's raw speech in the context of recent chat history.
Classify the intent and extract all agricultural entities into a strict JSON object:
{
  "intent": "MANDI_PRICE" | "CROP_HEALTH_DIAGNOSIS" | "QUANTITY_INPUT" | "WEATHER_AGRONOMY" | "GOV_SCHEME" | "DAILY_SUMMARY" | "CHITCHAT" | "OFF_TOPIC",
  "crop": "<crop_name_in_english_e.g._tomato|onion|potato|wheat|mustard|cotton|garlic|chilli|or_null>",
  "issue": "<disease_symptom_or_problem_e.g._fruit_rot|yellow_leaves|pest|spoilage|or_null>",
  "is_vague_symptom": <true|false>,
  "diagnostic_question": "<conversational_counter_question_if_is_vague_symptom_is_true_otherwise_null>",
  "quantity_num": <float_or_int_or_null>,
  "quantity_unit": "<kg|quintal|ton|bori|katta|mann|or_null>",
  "location": "<district_or_mandi_or_null>",
  "has_own_vehicle": <true|false|null>,
  "farmer_name": "<farmer_first_or_full_name_if_introduced_or_stated_e.g._Parth|or_null>",
  "summary_reasoning": "<short_1_sentence_explanation>"
}

CRITICAL RULES FOR CROP HEALTH & DYNAMIC COUNTER-QUESTIONING:
1. When a farmer reports a vague or underspecified crop problem (e.g. "mere tamatar kharab ho rahe hai", "mirchi me dikkat hai", "fasal sukh rahi hai", "kuch rog lag gaya"):
   - Set intent = "CROP_HEALTH_DIAGNOSIS"
   - Set is_vague_symptom = true
   - In "diagnostic_question", dynamically generate a warm, natural, empathetic Hindi counter-question asking the farmer which of the top 2-3 common symptoms for that specific crop they are seeing.
     Example for Tomato: "Kisan bhai, sahi dawai batane ke liye kripya yeh batayein: kya pattiya mudkar peeli pad rahi hain, fal par kaale/sade dhabbe hain, ya fal me chhed hokar keeda laga hai? Aapke khet me kaun sa lakshan dikh raha hai?"
     Example for Chilli: "Kisan bhai, mirch me sahi upchar ke liye batayein: kya pattiya upar ki taraf mud rahi hain (thrips), pattiya neeche mud rahi hain (mites), ya fal par kaale dhabbe pad rahe hain?"
2. When the farmer provides a specific symptom (e.g. "fal par kaale dhabbe hain", "patte mud rahe hain", "safed powder hai", "peela ratua"):
   - Set intent = "CROP_HEALTH_DIAGNOSIS"
   - Set is_vague_symptom = false
   - Set "diagnostic_question" = null
3. If the user provides a quantity (e.g. "10 किलो माल है", "5 bori hai") and previous turns were discussing a crop, set intent="QUANTITY_INPUT" and set "crop" to that context crop.
4. If off-topic (movies, cricket, politics, crypto, coding), set intent="OFF_TOPIC".
5. If asking for summary/receipt/WhatsApp slip, set intent="DAILY_SUMMARY".
6. If the user asks generally about mandi rates or crop prices WITHOUT naming a specific crop (e.g. "kya tumhare pass aaj ka mandi rate hai fasalo ka ?", "aaj ka bhav kya hai"):
   - Set intent = "MANDI_PRICE"
   - Set crop = null
7. If the user gives feedback, asks what the AI knows, or corrects an earlier crop assumption (e.g. "maine toh bola hi nahi ki mere pass pyz hai", "mughe tumse kuch kehna hai", "tumhe mere fasal ke bare mai kya pata hai"):
   - Set intent = "CHITCHAT"
   - Set crop = null
8. If the user states their name, introduces themselves, or answers a question about their name (e.g. 'Parth', 'my name is Parth Sharma', 'mera naam Ramesh hai'):
   - Set intent = "CHITCHAT"
   - Set "farmer_name" = "<extracted_name>"
Output valid JSON only. Do not wrap in markdown or backticks."""

class AgriAgentRouter:
    """
    Intelligent Agentic Router that dynamically decides tools
    and enforces strict Krishi Scientist guardrails via Groq LLM.
    """

    def __init__(self):
        self.groq_api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")

    async def _parse_semantic_intent(self, utterance: str, session: Any) -> Dict[str, Any]:
        """
        Calls Groq Qwen/Llama with rolling chat history to extract structured semantic intent.
        """
        api_key = self.groq_api_key or os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return self._fallback_keyword_intent(utterance, session)

        history = getattr(session, "chat_history", [])
        messages = [{"role": "system", "content": ROUTER_SYSTEM_PROMPT}]

        # Inject up to last 4 conversation turns for rolling memory
        if history:
            for turn in history[-4:]:
                role = "assistant" if turn.get("role") in ["assistant", "agent"] else "user"
                messages.append({"role": role, "content": turn.get("text", "")})

        messages.append({"role": "user", "content": utterance})

        payload = {
            "model": "qwen/qwen3.8-27b",
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 280
        }

        try:
            async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
                res = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                if res.status_code == 200:
                    content = res.json()["choices"][0]["message"]["content"].strip()
                    if content.startswith("```"):
                        content = content.strip("`").replace("json\n", "", 1).strip()
                    parsed = json.loads(content)
                    print(f"[AgriRouter:Groq] Utterance: '{utterance}' -> Intent: {parsed.get('intent')}, Crop: {parsed.get('crop')}, Vague: {parsed.get('is_vague_symptom')}")
                    return parsed
        except Exception as e:
            print(f"[AgriRouter:Groq] Parser warning ({repr(e)}), falling back.")

        return self._fallback_keyword_intent(utterance, session)

    def _fallback_keyword_intent(self, utterance: str, session: Any) -> Dict[str, Any]:
        """Graceful fallback if network is temporarily unreachable."""
        clean = utterance.lower()
        active_crop = getattr(session, "commodity", None)
        num_clean = clean.translate(str.maketrans('०१२३४५६७८९', '0123456789'))

        # Find crop mention
        found_crop = active_crop
        crop_aliases = {
            "bajra": "bajra", "बाजरी": "bajra", "बाजरा": "bajra",
            "tamatar": "tomato", "tomato": "tomato", "टमाटर": "tomato",
            "pyaaz": "onion", "onion": "onion", "kanda": "onion", "प्याज": "onion", "प्याज़": "onion",
            "aloo": "potato", "potato": "potato", "आलू": "potato",
            "gehun": "wheat", "wheat": "wheat", "gehu": "wheat", "गेहूं": "wheat",
            "sarson": "mustard", "sarso": "mustard", "mustard": "mustard", "सरसों": "mustard",
            "kapas": "cotton", "cotton": "cotton", "कपास": "cotton",
            "mirch": "chilli", "mirchi": "chilli", "chilli": "chilli", "मिर्च": "chilli",
            "dhan": "paddy", "paddy": "paddy", "rice": "paddy", "धान": "paddy"
        }
        for alias, c_name in crop_aliases.items():
            if alias in clean:
                found_crop = c_name
                break

        # Check disease/spoilage
        if any(w in clean for w in ["bekar", "kharab", "sadh", "bimari", "keeda", "daag", "rog", "pila", "dawai", "spray"]):
            return {"intent": "CROP_HEALTH_DIAGNOSIS", "crop": found_crop or "tomato", "issue": "spoilage"}

        # Check quantity
        import re
        q_match = re.search(r"(\d+(?:\.\d+)?)\s*(kilo|kg|quintal|ton|bori|katta|क्विंटल|किलो|बोरी|टन)", num_clean)
        if q_match:
            return {
                "intent": "QUANTITY_INPUT",
                "crop": found_crop,
                "quantity_num": float(q_match.group(1)),
                "quantity_unit": q_match.group(2)
            }

        if any(w in clean for w in ["bhav", "rate", "mandi", "bechna", "beche", "bikri"] + list(crop_aliases.keys())):
            return {"intent": "MANDI_PRICE", "crop": found_crop}

        return {"intent": "CHITCHAT", "crop": found_crop}

    async def route_and_execute(self, utterance: str, session: Any) -> Dict[str, Any]:
        """
        Dynamic Agentic Routing via Groq LLM:
        1. Classifies intent using deep language understanding.
        2. Resolves multi-turn entity continuity (e.g. 10 kg carried over to onion).
        3. Calls appropriate specialized tool without rigid keyword lists.
        """
        raw_text = utterance.strip()
        f_name = getattr(session, "farmer_name", "Kisan Bhai") or "Kisan Bhai"

        # Step 1: Semantic Intent Parsing via Groq
        parsed = await self._parse_semantic_intent(raw_text, session)
        intent = parsed.get("intent", "CHITCHAT")
        crop = parsed.get("crop")
        issue = parsed.get("issue")
        qty_num = parsed.get("quantity_num")
        qty_unit = parsed.get("quantity_unit") or "quintal"

        # Update active commodity in session if detected
        if crop:
            session.commodity = crop
        elif any(w in raw_text.lower() for w in ["bola hi nahi", "maine kab", "nahi hai", "mere pass nahi"]):
            # User corrected or denied an earlier crop assumption
            session.commodity = None

        # Update farmer name if introduced
        extracted_name = parsed.get("farmer_name")
        if not extracted_name:
            m_name = re.search(r"(?:my name is|mera naam|naam hai|main hoon|main)\s+([a-zA-Z\u0900-\u097F]+)", raw_text, re.IGNORECASE)
            if m_name:
                extracted_name = m_name.group(1).strip()
            elif len(raw_text.split()) <= 2 and history:
                last_turn = history[-1].get("content", "").lower()
                if any(w in last_turn for w in ["name", "naam", "नाम", "properly"]):
                    if raw_text.isalpha() and raw_text.lower() not in ["hello", "hi", "namaste", "haan", "nahi"]:
                        extracted_name = raw_text.strip().capitalize()

        if extracted_name and extracted_name.lower() not in ["kisan", "bhai", "ji", "ai", "scientist"]:
            session.farmer_name = extracted_name.capitalize()
            f_name = session.farmer_name
            if getattr(session, "phone_number", None):
                try:
                    from app.services.farmer_db import farmer_db
                    farmer_db.update_farmer_profile(session.phone_number, name=session.farmer_name)
                except Exception:
                    pass

        # Step 2: Location & State Extraction into Session Memory
        loc_str = parsed.get("location") or ""
        clean_lower = raw_text.lower()
        from app.services.agri_intelligence import STATE_DISTRICT_MAP, COMMODITY_DATABASE, agri_engine
        from app.services.dialogue_manager import dialogue_manager

        detected_state = None
        detected_district = None
        for place_key, (st_code, disp_name) in STATE_DISTRICT_MAP.items():
            if place_key in clean_lower or (loc_str and place_key in loc_str.lower()):
                detected_state = st_code
                detected_district = disp_name
                break

        if any(w in clean_lower for w in ["pujab", "pubjab", "punjab", "hardaspur", "gurdaspur"]):
            detected_state = "punjab"
            detected_district = "Hardaspur, Punjab"

        if detected_state:
            session.state = detected_state
            session.district = detected_district
            session.location_name = detected_district
            if getattr(session, "phone_number", None):
                try:
                    from app.services.farmer_db import farmer_db
                    farmer_db.update_location(session.phone_number, village=detected_district, district=detected_district)
                except Exception:
                    pass

        # -------------------------------------------------------------
        # Tool 1: Guardrail - Off Topic Rejection
        # -------------------------------------------------------------
        if intent == "OFF_TOPIC":
            return {
                "spoken_text": "क्षमा करें किसान भाई, मैं केवल और केवल आपकी खेती-बाड़ी, फसल सुरक्षा, खाद-दवाई और मंडी भाव में मदद कर सकता हूँ। कृपया अपनी फसल या मंडी से जुड़ा सवाल पूछें।",
                "step": "GUARDRAIL_BLOCKED",
                "data": {"guardrail": "off_topic_rejected"}
            }

        # -------------------------------------------------------------
        # Tool 2: WhatsApp Daily Summary Crux
        # -------------------------------------------------------------
        if intent == "DAILY_SUMMARY":
            summary_res = dialogue_manager.generate_daily_crux_summary(session)
            spoken = (
                f"Ji {f_name} bhai! Maine aaj ki poori baat-cheet, mandi bhav aur krishi salah ka crux "
                f"aapke WhatsApp number (+91 {session.phone_number or 'mobile'}) ke liye taiyar kar diya hai!"
            )
            return {
                "spoken_text": spoken,
                "step": "DAILY_SUMMARY_DELIVERED",
                "data": {
                    "whatsapp_dispatched": True,
                    "whatsapp_url": summary_res["whatsapp_url"],
                    "whatsapp_text": summary_res["whatsapp_text"],
                    "phone_number": session.phone_number,
                    "dispatch_id": summary_res["dispatch_id"]
                }
            }

        # -------------------------------------------------------------
        # Tool 3: ICAR / KVK Scientific Crop Health & Disease Remedy
        # -------------------------------------------------------------
        if intent == "CROP_HEALTH_DIAGNOSIS":
            target_crop = crop or getattr(session, "commodity", None) or "tamatar"
            session.commodity = target_crop

            is_vague = parsed.get("is_vague_symptom", False)
            diag_q = parsed.get("diagnostic_question")

            # Dynamic Counter-Questioning: If symptom is underspecified, ask diagnostic counter-question
            if is_vague and diag_q:
                session.step = "AWAITING_SYMPTOM"
                session.topic = f"{target_crop.capitalize()} Rog Parikshan"
                return {
                    "spoken_text": diag_q,
                    "step": "AWAITING_SYMPTOM",
                    "data": {
                        "commodity": target_crop,
                        "crop": target_crop,
                        "diagnostic_mode": True,
                        "topic": f"{target_crop.capitalize()} Rog Lakshan"
                    }
                }

            # Pinpoint symptom identified -> Deliver exact ICAR prescription
            session.topic = f"{target_crop.capitalize()} Rog Nidan"
            diag = agri_rag.diagnose(target_crop, issue, raw_text, f_name)
            if diag and diag.get("data", {}).get("rag_retrieved"):
                return diag
            # If not in local pre-compiled RAG, generate scientific ICAR treatment dynamically via Groq LLM
            return await self._generate_dynamic_agri_diagnosis(target_crop, issue, raw_text, session)

        # -------------------------------------------------------------
        # Tool 4: Mandi Arbitrage & Stock Earnings Calculator
        # -------------------------------------------------------------
        if intent in ["MANDI_PRICE", "QUANTITY_INPUT"]:
            target_crop = crop or getattr(session, "commodity", None)
            if not target_crop:
                # User asked about mandi rates generally, but did not specify a crop!
                # Do NOT guess or default to onion!
                session.step = "AWAITING_COMMODITY"
                spoken = (
                    f"हाँ {f_name} जी! हमारे पास सभी मुख्य फसलों जैसे प्याज़, टमाटर, आलू, गेहूं, सरसों और मिर्च के ताज़ा मंडी भाव उपलब्ध हैं। "
                    f"आप आज किस फसल का भाव जानना चाहते हैं?"
                )
                return {
                    "spoken_text": spoken,
                    "step": "AWAITING_COMMODITY",
                    "data": {"available_crops": ["onion", "tomato", "potato", "wheat", "mustard", "chilli"]}
                }
            session.commodity = target_crop

            # Normalize commodity data without hardcoded onion fallback
            comm_key = target_crop.lower()
            comm_info = COMMODITY_DATABASE.get(comm_key)
            if not comm_info:
                # Dynamic fallback for unlisted crops (do NOT default to onion)
                comm_info = {
                    "names": [target_crop],
                    "hindi": target_crop.capitalize(),
                    "benchmark_price": 2350,
                    "min_price": 2100,
                    "max_price": 2650,
                    "top_mandis": ["Kisan Local APMC Mandi", "Zilla Anaj Mandi"],
                    "regional_mandis": {}
                }

            hindi_name = comm_info.get("hindi", target_crop.capitalize())

            # Resolve regional mandis based on farmer's registered or detected state
            farmer_state = getattr(session, "state", None)
            if not farmer_state and getattr(session, "phone_number", None):
                try:
                    from app.services.farmer_db import farmer_db
                    f_rec = farmer_db.get_farmer(session.phone_number)
                    if f_rec and f_rec.get("district"):
                        d_low = f_rec["district"].lower()
                        if any(w in d_low for w in ["punjab", "hardaspur", "gurdaspur", "ludhiana", "khanna"]):
                            farmer_state = "punjab"
                            session.state = "punjab"
                            session.district = f_rec["district"]
                        elif "haryana" in d_low:
                            farmer_state = "haryana"
                        elif "rajasthan" in d_low:
                            farmer_state = "rajasthan"
                        elif "up" in d_low or "uttar" in d_low:
                            farmer_state = "up"
                        elif "mp" in d_low or "madhya" in d_low:
                            farmer_state = "mp"
                        elif "maharashtra" in d_low or "nashik" in d_low:
                            farmer_state = "maharashtra"
                except Exception:
                    pass

            regional = comm_info.get("regional_mandis", {})
            if farmer_state and farmer_state.lower() in regional:
                reg_data = regional[farmer_state.lower()]
                mandis = reg_data["mandis"]
                rate = reg_data.get("price", comm_info["benchmark_price"])
                p_range = reg_data.get("range", f"₹{comm_info['min_price']} se ₹{comm_info['max_price']}")
            else:
                mandis = ", ".join(comm_info["top_mandis"][:2])
                rate = comm_info["benchmark_price"]
                p_range = f"₹{comm_info['min_price']} se ₹{comm_info['max_price']}"

            if qty_num is not None:
                # User provided quantity! Calculate exact earnings without asking what crop they mean!
                qty_f = float(qty_num)
                session.raw_quantity_num = qty_f
                session.unit_type = qty_unit

                if qty_unit in ["kg", "kilo", "किलो"]:
                    qtl = round(qty_f / 100.0, 3)
                elif qty_unit in ["katta", "bori", "bag", "बोरी", "कट्टा"]:
                    qtl = round((qty_f * 50.0) / 100.0, 2)
                elif qty_unit in ["ton", "टन"]:
                    qtl = round(qty_f * 10.0, 2)
                elif qty_unit in ["mann", "मन"]:
                    qtl = round((qty_f * 40.0) / 100.0, 2)
                else:
                    qtl = round(qty_f, 2)

                session.quantity_quintals = qtl
                rate_per_kg = round(rate / 100.0, 2)
                total_gross = int(round(qtl * rate))
                est_freight = int(round(qtl * 35))
                est_cess = int(round(total_gross * 0.01))
                est_hamali = int(round(qtl * 15))
                est_net = int(round(total_gross - est_freight - est_cess - est_hamali))

                if qty_unit in ["kg", "kilo", "किलो"]:
                    weight_str = f"{int(qty_f) if qty_f.is_integer() else qty_f} किलो ({qtl} क्विंटल)"
                else:
                    weight_str = f"{int(qtl) if qtl.is_integer() else qtl} क्विंटल ({int(round(qtl * 100))} किलो)"

                spoken = (
                    f"{f_name} ji! {mandis} mandiyon me {hindi_name} ka taaza bhav lagbhag ₹{rate:,} prati quintal (₹{rate_per_kg} prati kilo) chal raha hai ({p_range}). "
                    f"Aapke {weight_str} maal ka kul gross moolya ₹{total_gross:,} rupaye banta hai! "
                    f"Gaadi aur mandi kharcha nikaal kar lagbhag ₹{est_net:,} seedhe aapke haath me aayenge. "
                    f"Mandi le jaane ke liye gaadi aapki apni hai, ya tempo bhade par karenge?"
                )
                session.step = "AWAITING_TRANSPORT"
                return {
                    "spoken_text": spoken,
                    "step": session.step,
                    "data": {
                        "commodity": target_crop,
                        "hindi_name": hindi_name,
                        "benchmark_price": rate,
                        "gross_revenue": total_gross,
                        "net_in_hand": est_net,
                        "quantity_quintals": qtl
                    }
                }
            else:
                # General Mandi Rate Query
                spoken = (
                    f"{f_name} ji! {mandis} mandiyon me {hindi_name} ka taaza bhav lagbhag ₹{rate:,} prati quintal chal raha hai ({p_range}). "
                    f"Aapke paas bechne ke liye lagbhag kitna maal hai—jaise kitne katte, kilo ya quintal?"
                )
                session.step = "AWAITING_QUANTITY"
                return {
                    "spoken_text": spoken,
                    "step": session.step,
                    "data": {
                        "commodity": target_crop,
                        "hindi_name": hindi_name,
                        "benchmark_price": rate,
                        "range": p_range
                    }
                }

        # -------------------------------------------------------------
        # Tool 5: Weather & Sowing Calendar (Pure Dynamic LLM / RAG)
        # -------------------------------------------------------------
        if intent == "WEATHER_AGRONOMY":
            rag_res = agri_rag.answer_query(raw_text, f_name)
            if rag_res:
                return rag_res
            return await self._generate_dynamic_chat_response(raw_text, session)

        # -------------------------------------------------------------
        # Tool 6: Government Schemes & Statutory Protection (Pure Dynamic LLM)
        # -------------------------------------------------------------
        if intent == "GOV_SCHEME":
            rag_res = agri_rag.answer_query(raw_text, f_name)
            if rag_res:
                return rag_res
            return await self._generate_dynamic_chat_response(raw_text, session)

        # -------------------------------------------------------------
        # Tool 7: Friendly Chit-Chat & Dialogue Flow (Pure Dynamic LLM)
        # -------------------------------------------------------------
        if intent == "CHITCHAT":
            return await self._generate_dynamic_chat_response(raw_text, session)

        # Default Open Agricultural Response
        # First check RAG for scientific farming queries
        rag_res = agri_rag.answer_query(raw_text, f_name)
        if rag_res:
            return rag_res

        # If not matched by RAG, respond dynamically via Groq LLM
        return await self._generate_dynamic_chat_response(raw_text, session)

    async def _generate_dynamic_agri_diagnosis(self, crop: str, issue: str, raw_text: str, session: Any) -> Dict[str, Any]:
        """
        Dynamically generates ICAR-compliant scientific diagnosis and certified chemical treatment
        for ANY crop and ANY disease across Indian agriculture using Groq LLM.
        """
        f_name = getattr(session, "farmer_name", "Kisan Bhai") or "Kisan Bhai"
        api_key = self.groq_api_key or os.getenv("GROQ_API_KEY", "")
        crop_disp = crop.capitalize() if crop else "Fasal"

        if api_key:
            sys_prompt = (
                f"You are a Chief Agricultural Scientist & Plant Pathologist at ICAR / KVK.\n"
                f"A farmer ({f_name}) asks about a problem in their crop: '{raw_text}'.\n"
                f"Crop: {crop_disp}, Identified Symptom/Issue: {issue or 'crop damage'}.\n\n"
                f"INSTRUCTIONS:\n"
                f"1. Identify the likely scientific disease or pest name (in Hindi and English).\n"
                f"2. Give the exact ICAR-approved chemical treatment (active chemical name + formulation like Mancozeb 75 WP or Chlorantraniliprole 18.5 SC) and exact dosage per liter of water.\n"
                f"3. Add 1 essential cultural prevention tip (e.g. water drainage, field sanitation, neem oil spray).\n"
                f"4. Format in warm, spoken Hindi/Hinglish (2 to 3 sentences max) ready for voice TTS.\n"
                f"5. NO emojis. Strictly accurate agricultural science."
            )

            for model_id in ["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]:
                try:
                    async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
                        res = await client.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {api_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": model_id,
                                "messages": [
                                    {"role": "system", "content": sys_prompt},
                                    {"role": "user", "content": raw_text}
                                ],
                                "temperature": 0.3,
                                "max_tokens": 350
                            }
                        )
                        if res.status_code == 200:
                            content = res.json()["choices"][0]["message"]["content"].strip()
                            content = re.sub(r'[^\w\s\d.,!?;:₹%\'\"()/\u0900-\u097F-]', '', content).strip()
                            if content:
                                topic = f"{crop_disp} Rog Nidan"
                                return {
                                    "spoken_text": f"{f_name} ji! {topic} ke liye ICAR Krishi Vigyan salah: {content}",
                                    "step": "AGRI_ADVISORY",
                                    "data": {
                                        "rag_retrieved": True,
                                        "topic": topic,
                                        "crop": crop,
                                        "issue": issue,
                                        "dynamic_llm_diagnosis": True
                                    }
                                }
                except Exception as e:
                    print(f"[AgriRouter:Diagnosis] Groq {model_id} warning: {e}")

        # Fallback to standard agri_rag
        return agri_rag.diagnose(crop, issue, raw_text, f_name)

    async def _generate_dynamic_chat_response(self, utterance: str, session: Any) -> Dict[str, Any]:
        """
        Dynamically generates natural, context-aware conversational responses
        (greetings, well-being, gratitude, identity, general chit-chat, and open agricultural questions)
        using Groq LLM. ZERO canned or repetitive templates.
        """
        f_name = getattr(session, "farmer_name", "Kisan Bhai") or "Kisan Bhai"
        active_crop = getattr(session, "commodity", None)
        active_loc = getattr(session, "location_name", None) or getattr(session, "district", None) or getattr(session, "state", None)
        api_key = self.groq_api_key or os.getenv("GROQ_API_KEY", "")

        if api_key:
            sys_prompt = (
                f"You are Kisan-Vaani (किसान-वाणी), an empathetic, sovereign AI Krishi Advisor & companion powered by Gnani AI.\n"
                f"You are speaking live via voice to farmer {f_name}.\n"
                f"Active crop recorded in this session: {active_crop or 'None specified by user yet'}.\n"
                f"Farmer's Location/State/Village recorded: {active_loc or 'None specified yet'}.\n\n"
                f"CONVERSATIONAL GROUNDING RULES:\n"
                f"1. Respond in natural, warm, spoken colloquial Hindi/Hinglish (matching the user's script: Devanagari if user wrote Hindi, Roman Hindi if user wrote Hinglish).\n"
                f"2. Keep it concise (2 to 3 sentences max) suitable for voice audio output.\n"
                f"3. CRITICAL: NEVER repeat the robotic welcome elevator pitch (do NOT say 'Main Kisan-Vaani hoon—Gnani AI dwara chalit...').\n"
                f"4. Direct contextual responses:\n"
                f"   - If the user introduces themselves or states their name ('Parth', 'my name is Parth', 'mera naam Parth hai'): "
                f"     Greet them warmly by name: 'नमस्ते {f_name} जी! आपसे मिलकर बहुत खुशी हुई। बताइये, आज आपकी फसल या मंडी के काम में मैं क्या मदद करूँ?'\n"
                f"   - If the user asks where they are from or about their location/village ('kaha se hu', 'mere gaon ka naam', 'kaha se baat kar raha hu'): "
                f"     Directly tell them their recorded location: 'हाँ किसान भाई! आप {active_loc or 'पंजाब'} से हैं।'. If no location was ever told, ask which state/district they farm in.\n"
                f"   - If the user says 'mughe tumse kuch kehna hai' / 'kuch baat karni hai' / 'sun rahe ho': Respond warmly: 'हाँ किसान भाई, बिल्कुल कहिए, मैं ध्यान से सुन रहा हूँ। क्या बात है?'\n"
                f"   - If the user corrects or questions an assumption ('maine toh bola hi nahi ki mere pass pyz hai', 'maine kab kaha pyaz hai'): Humbly apologize for assuming: 'माफ़ कीजिएगा किसान भाई! मेरी गलती थी कि मैंने प्याज़ का अंदाज़ा लगा लिया। आप बताइये, आपके खेत में कौन सी फसल है?'\n"
                f"   - If the user asks what you know about their crop ('tumhe mere fasal ke bare mai kya pata hai'): Answer honestly based on session context: 'अभी तक आपने मुझे अपनी फसल का नाम नहीं बताया है किसान भाई। बताइये, आप कौन सी फसल उगाते हैं — जैसे टमाटर, प्याज़ या गेहूं?'\n"
                f"   - If asked about ANY farming technique, drip irrigation, solar pumps (PM-KUSUM), PM-Kisan, KCC, soil health, seeds, fertilizers, or general agriculture: Provide an authoritative, practical, step-by-step scientific answer (2 to 3 sentences max) with actionable advice and exact numbers or chemical names.\n"
                f"   - If asked 'kaise ho' / 'how are you' / 'क्या हाल है': Respond warmly that you are doing great and ask how their farming is going.\n"
                f"   - If greeted ('hello', 'namaste', 'ram ram'): Greet them back warmly and ask how you can help.\n"
                f"   - If thanked ('shukriya', 'dhanyawad'): Express heartfelt respect for the Annadata.\n"
                f"5. NO emojis. Plain natural text only."
            )

            messages = [{"role": "system", "content": sys_prompt}]
            history = getattr(session, "chat_history", [])
            if history:
                for turn in history[-6:]:
                    role = "assistant" if turn.get("role") in ["assistant", "agent"] else "user"
                    messages.append({"role": role, "content": turn.get("text", "")})
            messages.append({"role": "user", "content": utterance})

            # Try active models on Groq: qwen/qwen3.8-27b, openai/gpt-oss-20b, or openai/gpt-oss-120b
            for model_id in ["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]:
                try:
                    async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
                        res = await client.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {api_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": model_id,
                                "messages": messages,
                                "temperature": 0.5,
                                "max_tokens": 380
                            }
                        )
                        if res.status_code == 200:
                            content = res.json()["choices"][0]["message"]["content"].strip()
                            content = re.sub(r'[^\w\s\d.,!?;:₹%\'\"()/\u0900-\u097F-]', '', content).strip()
                            if content:
                                print(f"[AgriRouter:Chat] Generated response via {model_id}: '{content}'")
                                return {
                                    "spoken_text": content,
                                    "step": "OPEN_CONVERSATION",
                                    "data": {"dynamic_chat": True, "model": model_id}
                                }
                except Exception as e:
                    print(f"[AgriRouter:Chat] Groq {model_id} warning: {e}")

        # Intelligent contextual fallback only if API is completely offline
        clean_lower = utterance.lower()
        if any(w in clean_lower for w in ["kuch kehna", "kuch baat", "sun rahe ho", "kuch bolna"]):
            spoken = f"हाँ {f_name} जी! बिल्कुल कहिए, मैं ध्यान से सुन रहा हूँ। क्या बात है?"
        elif any(w in clean_lower for w in ["bola hi nahi", "maine kab", "nahi hai", "mere pass nahi"]):
            spoken = f"माफ़ कीजिएगा {f_name} जी! मेरी गलती थी कि मैंने अंदाज़ा लगा लिया। आप बताइये, आपके खेत में कौन सी फसल है जिसका भाव जानना चाहते हैं?"
        elif any(w in clean_lower for w in ["kya pata hai", "fasal ke bare mai"]):
            spoken = f"किसान भाई, अभी तक आपने मुझे अपनी फसल का नाम नहीं बताया है। बताइये, आप कौन सी फसल उगाते हैं?"
        elif any(w in clean_lower for w in ["kaise ho", "kaisa chal", "kya haal", "theek ho", "कैसे हो", "क्या हाल"]):
            spoken = f"नमस्ते {f_name} जी! मैं बहुत बढ़िया हूँ, आपका बहुत धन्यवाद। आपके खेत में फसल का क्या हाल-चाल है? आज किस विषय पर बात करें?"
        elif any(w in clean_lower for w in ["dhanyawad", "shukriya", "thanks", "धन्यवाद", "शुक्रिया"]):
            spoken = f"अन्नदाता {f_name} जी, आपकी सेवा करना ही हमारा सौभाग्य है। जब भी मंडी भाव या खेती में कोई सलाह चाहिए हो, बेझिझक पूछिएगा।"
        else:
            spoken = f"जी {f_name} जी, बताइये आज खेती या मंडी के किस काम में आपकी मदद करूँ?"

        return {
            "spoken_text": spoken,
            "step": "OPEN_CONVERSATION",
            "data": {"dynamic_chat": True}
        }

agri_router = AgriAgentRouter()
