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
        raw_text = utterance.strip()
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

        # 3. TOOL A: Mandi Price / Rate / Market Arbitrage Tool
        is_mandi_query = any(w in clean for w in [
            "bhav", "rate", "bhav kya", "rate kya", "kimat", "mandi", "mandi bhav", "aaj ka rate",
            "भाव", "रेट", "भाव क्या", "मंडी भाव", "रेट बताओ", "दाम", "कीमत", "बिकेगा"
        ])

        if is_mandi_query:
            from app.services.agri_intelligence import agri_engine
            return agri_engine._handle_commodity_query(enriched_text, session) or agri_engine.analyze_and_respond(enriched_text, session)

        # 4. TOOL B: Agri-RAG ICAR / KVK Scientific Advisory Tool
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
