"""
Agentic Agricultural Router & Dynamic Generative Orchestrator for Kisan-Vaani.
Zero Pre-fed Dialogues • Complete ChatGPT-Level Agricultural Flexibility

Powered by:
- Semantic Entity & Context Extractor (Groq / Qwen / Llama)
- Dynamic Context Aggregator (Live Agmarknet Data, Arbitrage Calculator, ICAR Knowledge)
- Sovereign LLM Generative Voice Reasoner (llm_service)
"""

import os
import re
import json
import httpx
from typing import Dict, Any, Optional, List
from app.config import settings
from app.services.llm_service import llm_service
from app.services.agri_rag import agri_rag
from app.services.mandi_service import mandi_service
from app.services.arbitrage_engine import arbitrage_engine
from app.services.enam_rules import enam_advisor

ROUTER_PARSER_PROMPT = """Analyze the farmer's raw speech in the context of recent chat history.
Extract all agricultural entities into a strict JSON object:
{
  "intent": "MANDI_PRICE" | "CROP_HEALTH_DIAGNOSIS" | "QUANTITY_INPUT" | "WEATHER_AGRONOMY" | "GOV_SCHEME" | "DAILY_SUMMARY" | "CHITCHAT" | "OFF_TOPIC",
  "crop": "<crop_name_in_english_e.g._tomato|onion|potato|wheat|mustard|cotton|garlic|chilli|paddy|or_null>",
  "issue": "<disease_symptom_or_problem_e.g._fruit_rot|yellow_leaves|pest|spoilage|or_null>",
  "is_vague_symptom": <true|false>,
  "quantity_num": <float_or_int_or_null>,
  "quantity_unit": "<kg|quintal|ton|bori|katta|mann|or_null>",
  "location": "<district_or_mandi_or_village_or_null>",
  "has_own_vehicle": <true|false|null>,
  "farmer_name": "<farmer_name_if_introduced_e.g._Parth|or_null>"
}

RULES:
1. If the farmer reports an underspecified crop issue ("tamatar kharab hai", "mirch me dikkat hai", "fasal sukh rahi hai"), set is_vague_symptom = true.
2. If the user mentions quantity ("20 bori", "10 kg", "5 quintal"), set intent = "QUANTITY_INPUT".
3. If off-topic (movies, cricket, politics, crypto, coding), set intent = "OFF_TOPIC".
4. If asking for a summary/receipt/WhatsApp message, set intent = "DAILY_SUMMARY".
5. If the user introduces themselves or states their name, extract farmer_name.
Output valid JSON only. Do not wrap in markdown or backticks."""

class AgriAgentRouter:
    """
    Agentic Router that dynamically extracts entities, gathers real-time data,
    and delegates all conversational speech generation to the LLM.
    Zero pre-fed dialogues.
    """

    def __init__(self):
        self.groq_api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")

    async def _parse_semantic_intent(self, utterance: str, session: Any) -> Dict[str, Any]:
        """
        Calls Groq Qwen/Llama to extract structured semantic intent and entities.
        """
        api_key = self.groq_api_key or os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return self._fallback_keyword_intent(utterance, session)

        history = getattr(session, "chat_history", [])
        messages = [{"role": "system", "content": ROUTER_PARSER_PROMPT}]

        if history:
            for turn in history[-4:]:
                role = "assistant" if turn.get("role") in ["assistant", "agent", "model"] else "user"
                messages.append({"role": role, "content": turn.get("text") or turn.get("content") or ""})

        messages.append({"role": "user", "content": utterance})

        candidate_models = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]

        for model_id in candidate_models:
            try:
                async with httpx.AsyncClient(timeout=6.0, verify=False) as client:
                    res = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={
                            "model": model_id,
                            "messages": messages,
                            "temperature": 0.1,
                            "max_tokens": 250
                        }
                    )
                    if res.status_code == 200:
                        content = res.json()["choices"][0]["message"]["content"].strip()
                        if content.startswith("```"):
                            content = content.strip("`").replace("json\n", "", 1).strip()
                        return json.loads(content)
            except Exception:
                continue

        return self._fallback_keyword_intent(utterance, session)

    def _fallback_keyword_intent(self, utterance: str, session: Any) -> Dict[str, Any]:
        clean = utterance.lower()
        active_crop = getattr(session, "commodity", None)
        num_clean = clean.translate(str.maketrans('०१२३४५६७८९', '0123456789'))

        crop_aliases = {
            "tamatar": "tomato", "tomato": "tomato", "टमाटर": "tomato",
            "pyaaz": "onion", "onion": "onion", "kanda": "onion", "प्याज": "onion", "कांदा": "onion",
            "aloo": "potato", "potato": "potato", "आलू": "potato",
            "gehun": "wheat", "wheat": "wheat", "गेहूं": "wheat",
            "sarson": "mustard", "mustard": "mustard", "सरसों": "mustard",
            "kapas": "cotton", "cotton": "cotton", "कपास": "cotton",
            "mirch": "chilli", "mirchi": "chilli", "मिर्च": "chilli",
            "lahsun": "garlic", "garlic": "garlic", "लहसुन": "garlic"
        }
        found_crop = active_crop
        for alias, c_name in crop_aliases.items():
            if alias in clean:
                found_crop = c_name
                break

        if any(w in clean for w in ["kharab", "bimari", "keeda", "daag", "rog", "pila", "dawai", "spray", "sukh"]):
            return {"intent": "CROP_HEALTH_DIAGNOSIS", "crop": found_crop, "is_vague_symptom": "kharab" in clean or "dikkat" in clean}

        q_match = re.search(r"(\d+(?:\.\d+)?)\s*(kilo|kg|quintal|ton|bori|katta|क्विंटल|किलो|बोरी)", num_clean)
        if q_match:
            return {"intent": "QUANTITY_INPUT", "crop": found_crop, "quantity_num": float(q_match.group(1)), "quantity_unit": q_match.group(2)}

        if any(w in clean for w in ["bhav", "rate", "mandi", "bechna", "beche", "bikri"]):
            return {"intent": "MANDI_PRICE", "crop": found_crop}

        if any(w in clean for w in ["film", "cricket", "ipl", "modi", "crypto", "coding", "python"]):
            return {"intent": "OFF_TOPIC"}

        return {"intent": "CHITCHAT", "crop": found_crop}

    async def route_and_execute(self, utterance: str, session: Any) -> Dict[str, Any]:
        """
        Unified Agentic Pipeline:
        1. Analyzes intent and entities dynamically.
        2. Aggregates live data (Agmarknet Mandi rates, Arbitrage math, ICAR diagnostics).
        3. Calls LLM to synthesize natural, empathetic spoken voice (ZERO pre-fed templates).
        """
        raw_text = utterance.strip()
        f_name = getattr(session, "farmer_name", "Kisan Bhai") or "Kisan Bhai"

        # Step 1: Semantic Intent & Entity Extraction
        parsed = await self._parse_semantic_intent(raw_text, session)
        intent = parsed.get("intent", "CHITCHAT")
        crop = parsed.get("crop")
        issue = parsed.get("issue")
        is_vague = parsed.get("is_vague_symptom", False)
        qty_num = parsed.get("quantity_num")
        qty_unit = parsed.get("quantity_unit") or "quintal"

        # Update active commodity in session
        if crop:
            session.commodity = crop
        elif any(w in raw_text.lower() for w in ["bola hi nahi", "maine kab", "nahi hai", "mere pass nahi"]):
            session.commodity = None

        # Update farmer identity if stated
        extracted_name = parsed.get("farmer_name")
        if not extracted_name:
            m_name = re.search(r"(?:my name is|mera naam|naam hai)\s+([a-zA-Z\u0900-\u097F]+)", raw_text, re.IGNORECASE)
            if m_name:
                extracted_name = m_name.group(1).strip()

        if extracted_name and extracted_name.lower() not in ["kisan", "bhai", "ji", "ai"]:
            session.farmer_name = extracted_name.capitalize()
            f_name = session.farmer_name
            if getattr(session, "phone_number", None):
                try:
                    from app.services.farmer_db import farmer_db
                    farmer_db.update_farmer_profile(session.phone_number, name=session.farmer_name)
                except Exception:
                    pass

        # Update location in session
        loc_str = parsed.get("location")
        if loc_str:
            session.location_name = loc_str
            session.district = loc_str

        # Update quantity in session if provided
        if qty_num is not None:
            qty_f = float(qty_num)
            session.raw_quantity_num = qty_f
            session.unit_type = qty_unit
            if qty_unit in ["kg", "kilo", "किलो"]:
                session.quantity_quintals = round(qty_f / 100.0, 3)
            elif qty_unit in ["katta", "bori", "bag", "बोरी", "कट्टा"]:
                session.quantity_quintals = round((qty_f * 50.0) / 100.0, 2)
            elif qty_unit in ["ton", "टन"]:
                session.quantity_quintals = round(qty_f * 10.0, 2)
            elif qty_unit in ["mann", "मन"]:
                session.quantity_quintals = round((qty_f * 40.0) / 100.0, 2)
            else:
                session.quantity_quintals = round(qty_f, 2)

        # -----------------------------------------------------------------
        # SCENARIO A: MANDI PRICE INQUIRY OR QUANTITY EARNINGS
        # -----------------------------------------------------------------
        if intent in ["MANDI_PRICE", "QUANTITY_INPUT"]:
            target_crop = crop or getattr(session, "commodity", None)
            
            # If farmer asks about rates generally without mentioning any crop
            if not target_crop:
                spoken = await llm_service.generate_response(
                    user_query=raw_text,
                    farmer_name=f_name,
                    village=getattr(session, "location_name", ""),
                    district=getattr(session, "district", ""),
                    crops=None,
                    history=getattr(session, "chat_history", []),
                    context_data={"note": "The farmer asked for mandi rates but did not name a crop. Ask them warmly which crop they want the rates for."}
                )
                return {
                    "spoken_text": spoken,
                    "step": "AWAITING_COMMODITY",
                    "data": {"available_crops": ["onion", "tomato", "potato", "wheat", "mustard", "chilli"]}
                }

            # Determine location hint from extracted location, user speech, or session memory
            loc_hint = loc_str or getattr(session, "location_name", None) or getattr(session, "district", None)
            if not loc_hint:
                for kw in ["lasalgaon", "pimpalgaon", "nashik", "yeola", "pune", "delhi", "azadpur", "jaipur", "rajasthan", "punjab", "khanna", "ludhiana", "haryana", "sonipat", "agra", "indore", "mandsaur", "guntur"]:
                    if kw in raw_text.lower():
                        loc_hint = kw
                        break

            # Fetch live mandi rates matching location
            lat = getattr(session, "lat", 20.0800)
            lon = getattr(session, "lon", 74.1100)
            rates = mandi_service.get_rates_for_commodity(
                target_crop,
                user_lat=lat,
                user_lon=lon,
                location_hint=loc_hint
            )

            # Compute arbitrage math if quantity is known or use standard benchmark
            q_quintals = session.quantity_quintals or 10.0
            has_own = session.has_own_vehicle if session.has_own_vehicle is not None else True
            evaluated = arbitrage_engine.calculate_arbitrage(rates, q_quintals, has_own_vehicle=has_own)
            session.last_arbitrage_results = evaluated

            # Package live data as context for the LLM
            context_data = {
                "crop": target_crop,
                "requested_location": loc_hint or "Local Region",
                "quantity_quintals": q_quintals,
                "has_own_vehicle": has_own,
                "mandi_rates": rates[:5] if rates else [],
                "arbitrage": evaluated[:3] if evaluated else [],
                "enam_rules": "Statutory APMC law: Farmer commission is 0%. Buyer pays commission. Electronic weighbridge slip mandatory."
            }

            # The LLM generates the spoken reasoning dynamically
            spoken = await llm_service.generate_response(
                user_query=raw_text,
                farmer_name=f_name,
                village=getattr(session, "location_name", ""),
                district=getattr(session, "district", ""),
                crops=[target_crop],
                history=getattr(session, "chat_history", []),
                context_data=context_data
            )

            # Build digital receipt for WhatsApp
            from app.services.dialogue_manager import dialogue_manager
            slip = dialogue_manager._generate_enhanced_slip(session)
            session.mandi_slip = slip

            return {
                "spoken_text": spoken,
                "step": "ARBITRAGE_DELIVERED",
                "data": {
                    "evaluated_mandis": evaluated,
                    "commodity": target_crop,
                    "quantity_quintals": q_quintals,
                    "mandi_slip": slip
                }
            }

        # -----------------------------------------------------------------
        # SCENARIO B: CROP HEALTH, PESTS & DISEASE DIAGNOSIS
        # -----------------------------------------------------------------
        if intent == "CROP_HEALTH_DIAGNOSIS":
            target_crop = crop or getattr(session, "commodity", None) or "crop"
            session.commodity = target_crop

            # Retrieve verified scientific ICAR POP documents
            docs = agri_rag.retrieve(raw_text, top_k=2)
            icar_facts = {}
            if docs:
                best_doc = docs[0]
                icar_facts = {
                    "crop": best_doc.get("crop"),
                    "topic": best_doc.get("topic"),
                    "pathogen": best_doc.get("pathogen"),
                    "organic_cure": best_doc.get("organic_cure"),
                    "chemical_cure": best_doc.get("chemical_cure"),
                    "dosage": best_doc.get("dosage"),
                    "waiting_period_days": best_doc.get("waiting_period_days")
                }

            context_data = {
                "crop": target_crop,
                "crop_disease_info": icar_facts if icar_facts else {"symptom": issue or "damage"},
                "is_vague_symptom": is_vague
            }

            spoken = await llm_service.generate_response(
                user_query=raw_text,
                farmer_name=f_name,
                village=getattr(session, "location_name", ""),
                district=getattr(session, "district", ""),
                crops=[target_crop],
                history=getattr(session, "chat_history", []),
                context_data=context_data
            )

            return {
                "spoken_text": spoken,
                "step": "AWAITING_SYMPTOM" if is_vague else "AGRI_ADVISORY",
                "data": {
                    "crop": target_crop,
                    "issue": issue,
                    "diagnostic_mode": is_vague,
                    "icar_facts": icar_facts
                }
            }

        # -----------------------------------------------------------------
        # SCENARIO C: DAILY SUMMARY & WHATSAPP SLIP
        # -----------------------------------------------------------------
        if intent == "DAILY_SUMMARY":
            from app.services.dialogue_manager import dialogue_manager
            summary_res = dialogue_manager.generate_daily_crux_summary(session)
            
            # LLM dynamically formulates the delivery confirmation
            spoken = await llm_service.generate_response(
                user_query=raw_text,
                farmer_name=f_name,
                village=getattr(session, "location_name", ""),
                district=getattr(session, "district", ""),
                crops=[session.commodity] if session.commodity else None,
                history=getattr(session, "chat_history", []),
                context_data={"action": "WhatsApp summary slip dispatched", "phone": session.phone_number}
            )

            return {
                "spoken_text": spoken,
                "step": "DAILY_SUMMARY_DELIVERED",
                "data": {
                    "whatsapp_dispatched": True,
                    "whatsapp_url": summary_res.get("whatsapp_url", ""),
                    "whatsapp_text": summary_res.get("whatsapp_text", ""),
                    "phone_number": session.phone_number,
                    "dispatch_id": summary_res.get("dispatch_id", "")
                }
            }

        # -----------------------------------------------------------------
        # SCENARIO D: GENERAL AGRICULTURAL QUESTIONS & CHAT (Zero Scripts)
        # Covers: Soil, Fertilizers, Sowing, Irrigation, Weather, Schemes,
        # KCC loans, Machinery, Cattle/Dairy, Greetings, Identity & Guardrails
        # -----------------------------------------------------------------
        spoken = await llm_service.generate_response(
            user_query=raw_text,
            farmer_name=f_name,
            village=getattr(session, "location_name", ""),
            district=getattr(session, "district", ""),
            crops=[session.commodity] if session.commodity else None,
            history=getattr(session, "chat_history", []),
            context_data=None
        )

        return {
            "spoken_text": spoken,
            "step": "OPEN_CONVERSATION",
            "data": {"dynamic_generative": True}
        }

agri_router = AgriAgentRouter()
