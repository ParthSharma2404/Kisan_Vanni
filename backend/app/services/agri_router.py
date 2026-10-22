"""
Agentic Agricultural Router & Guardrails Engine for Kisan-Vaani.
Implements:
1. Strict Agricultural Domain Guardrails (Politely declines non-farming topics).
2. Dynamic Tool Orchestration:
   - Tool A: Mandi Pricing & Arbitrage (Agmarknet data.gov.in)
   - Tool B: ICAR / KVK Agri-RAG (Scientific remedies, dosages, fertilizers)
   - Tool C: Weather, Agronomy & Government Schemes
3. Context-Aware Sliding Window Resolution (Resolves pronouns 'यह', 'इसमें' from history).
4. Voice-First Brevity (Strictly concise, under 35 words for zero voice lag).
"""

import re
from typing import Dict, Any, Optional, List
from app.services.agri_rag import agri_rag
from app.services.agri_knowledge_base import AGRI_KNOWLEDGE_DOCUMENTS

# Strict Non-Agri Topics for Guardrail Classification
NON_AGRI_TRIGGERS = [
    # Entertainment / Bollywood / Cinema
    "film", "movie", "actor", "actress", "shahrukh", "salman", "song", "gana", "hero", "heroine",
    "फिल्म", "मूवी", "गाना", "गाना सुनाओ", "एक्टर", "शाहरुख", "सलमान",
    # Sports / Cricket
    "cricket", "ipl", "match", "football", "world cup", "virat", "dhoni", "rohit",
    "क्रिकेट", "आईपीएल", "मैच", "विराट", "धोनी",
    # Politics & General Non-Rural News
    "election", "chunav", "vote", "modi vs", "rahul gandhi", "bjp", "congress", "president",
    "चुनाव", "वोट", "राजनीति",
    # Tech / Coding / Space
    "python code", "programming", "software", "mars", "moon", "chandrayaan", "space", "crypto", "bitcoin",
    "कोडिंग", "सॉफ्टवेयर", "अंतरिक्ष", "बिटकॉइन"
]

class AgriAgentRouter:
    """
    Intelligent Agentic Router that dynamically decides tools
    and enforces strict Krishi Scientist guardrails.
    """

    def check_guardrails(self, utterance: str) -> Optional[str]:
        """
        Enforces strict domain boundary: only agriculture, crops, weather,
        livestock, and rural economy are permitted.
        """
        clean = utterance.lower()
        for trigger in NON_AGRI_TRIGGERS:
            if trigger in clean:
                return (
                    "क्षमा करें किसान भाई, मैं केवल और केवल आपकी खेती-बाड़ी, फसल, खाद-दवाई और मंडी भाव में मदद कर सकता हूँ। "
                    "कृपया अपनी फसल या मंडी से जुड़ा सवाल पूछें।"
                )
        return None

    def resolve_contextual_pronouns(self, text: str, session: Any) -> str:
        """
        Uses rolling conversation context to resolve pronouns ('यह', 'it', 'इसमें', 'उसका भाव')
        back to the active crop or topic discussed in the last 2-3 turns.
        """
        clean = text.lower()
        pronoun_triggers = [
            "yah", "ye", "iska", "iske", "iski", "isme", "ismein", "vahan", "wahan", "it", "this",
            "यह", "ये", "इसका", "इसके", "इसकी", "इसमें", "उसका", "उसके", "उसकी", "वहां"
        ]

        has_pronoun = any(p in clean.split() or p in clean for p in pronoun_triggers)
        active_commodity = getattr(session, "commodity", None)

        if has_pronoun and active_commodity:
            # If farmer asks "क्या यह पिछले हफ्ते से ज्यादा है?" or "इसमें क्या डालें?"
            # Append contextually resolved crop name for tool retrieval
            resolved_text = f"{text} ({active_commodity})"
            return resolved_text

        return text

    def route_and_execute(self, utterance: str, session: Any) -> Dict[str, Any]:
        """
        Dynamic Agentic Routing:
        1. Guardrails Check -> Reject off-topic queries immediately.
        2. Context Resolution -> Inject rolling window pronouns.
        3. Dynamic Tool Decision ->
           • If Price / Mandi query -> Tool A (Mandi Engine)
           • If Crop Doctor / Fertilizer / Law -> Tool B (Agri-RAG ICAR Engine)
           • If Weather / Sowing / Scheme -> Tool C (Agronomy & Schemes)
           • Else -> Concise Conversational Chit-chat
        """
        raw_text = utterance.strip().translate(str.maketrans('०१२३४५६७८९', '0123456789'))
        f_name = getattr(session, "farmer_name", "Kisan Bhai") or "Kisan Bhai"

        # 1. Strict Domain Guardrail Check
        guardrail_violation = self.check_guardrails(raw_text)
        if guardrail_violation:
            return {
                "spoken_text": guardrail_violation,
                "step": "GUARDRAIL_BLOCKED",
                "data": {"guardrail": "off_topic_rejected"}
            }

        # 2. Context-Aware Sliding Window Pronoun Resolution
        enriched_text = self.resolve_contextual_pronouns(raw_text, session)
        clean = enriched_text.lower()

        # Check for Daily Crux Summary Request (End of conversation or explicit request)
        summary_triggers = [
            "summary", "whatsapp summary", "hisaab bhej do", "saara hisaab", "whatsapp par bhej do",
            "parcha bhej do", "rasid bhej do", "done from my side", "done for today", "send to whatsapp",
            "समरी", "व्हाट्सएप समरी", "व्हाट्सएप पर भेज दो", "हिसाब भेजो", "पर्चा भेजो", "आज का हिसाब"
        ]
        if any(w in clean for w in summary_triggers):
            from app.services.dialogue_manager import dialogue_manager
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

        from app.services.agri_intelligence import agri_engine

        # 3. Handle Active Multi-Turn Slot Filling States (Location, Quantity, Transport)
        current_step = getattr(session, "step", "")
        if current_step == "AWAITING_QUANTITY":
            qty_res = agri_engine._handle_quantity_response(enriched_text, session)
            if qty_res:
                return qty_res

        if current_step == "AWAITING_TRANSPORT":
            trans_res = agri_engine._handle_transport_response(enriched_text, session)
            if trans_res:
                return trans_res

        if current_step == "AWAITING_LOCATION":
            loc_res = agri_engine._handle_location_response(enriched_text, session)
            if loc_res:
                return loc_res

        # 4. TOOL A: Mandi Price / Stock Weight / Selling / Market Arbitrage Tool
        num, unit = agri_engine._extract_quantity(clean)
        is_stock_or_weight_query = (num is not None) or any(w in clean for w in [
            "bechna", "bechu", "maal", "stock", "kamai", "munafa", "earning", "kitna milega", "kitna banta",
            "क्विंटल", "कुंतल", "quintal", "kilo", "किलो", "kg", "बोरी", "कट्टा", "bori", "katta", "ton", "टन"
        ])

        is_mandi_query = is_stock_or_weight_query or any(w in clean for w in [
            "bhav", "rate", "bhav kya", "rate kya", "kimat", "mandi", "mandi bhav", "aaj ka rate",
            "भाव", "रेट", "भाव क्या", "मंडी भाव", "रेट बताओ", "दाम", "कीमत", "बिकेगा"
        ])

        # If user states crop/commodity directly (e.g. potato, tomato, onion), treat as Mandi inquiry first
        matched_comm = agri_engine._match_commodity(clean)
        if matched_comm and is_mandi_query:
            return agri_engine._handle_commodity_query(enriched_text, session) or agri_engine.analyze_and_respond(enriched_text, session)

        if is_mandi_query:
            mandi_res = agri_engine._handle_commodity_query(enriched_text, session) or agri_engine.analyze_and_respond(enriched_text, session)
            if mandi_res:
                return mandi_res

        # 5. TOOL B: Agri-RAG ICAR / KVK Scientific Advisory Tool (Only for actual diseases, pests, remedies)
        rag_result = agri_rag.answer_query(enriched_text, f_name)
        if rag_result:
            return rag_result

        # 5. TOOL C: Weather, Agronomy, Government Schemes
        from app.services.agri_intelligence import agri_engine
        scheme_res = agri_engine._handle_government_schemes(clean, session)
        if scheme_res:
            return scheme_res

        agronomy_res = agri_engine._handle_agronomy_and_weather(clean, session)
        if agronomy_res:
            return agronomy_res

        # 6. TOOL D: Conversational Chit-Chat / Greetings / Capabilities
        chitchat_res = agri_engine._handle_chitchat_and_general(clean, session)
        if chitchat_res:
            return chitchat_res

        # 7. Fallback to Open Conversational Agricultural Response
        return agri_engine._generate_open_agri_response(raw_text, session)

agri_router = AgriAgentRouter()
