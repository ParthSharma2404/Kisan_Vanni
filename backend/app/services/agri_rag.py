"""
Agri-RAG Retrieval and Reasoning Engine for Kisan-Vaani.
Retrieves scientific ICAR/KVK Package of Practices (POP) documents and synthesizes
concise, actionable, voice-optimized Indic advisory for farmers.
"""

import re
from typing import List, Dict, Any, Optional
from app.services.agri_knowledge_base import AGRI_KNOWLEDGE_DOCUMENTS

HINDI_STOPWORDS = {
    "में", "है", "हैं", "की", "का", "के", "को", "पर", "से", "और", "या", "न", "नहीं", 
    "कर", "करें", "रहा", "रही", "रहे", "होता", "होती", "सकता", "सकते", "सकती", 
    "डालें", "डालना", "बताओ", "क्या", "आ", "रहा", "गया", "गई", "हैं", "था", "थी",
    "kya", "hai", "hain", "ka", "ki", "ke", "ko", "se", "me", "mein", "aur", "ya", "batao", "bataiye"
}

CROP_ALIASES = {
    "tomato": ["tamatar", "tomato", "टमाटर"],
    "potato": ["aloo", "alu", "potato", "आलू"],
    "onion": ["pyaaz", "pyaj", "kanda", "onion", "प्याज", "कांदा"],
    "wheat": ["gehun", "gehu", "wheat", "गेहूं", "गेंहू"],
    "mustard": ["sarson", "sarso", "mustard", "rai", "सरसों", "राई"],
    "cotton": ["kapas", "cotton", "narma", "कपास", "नरमा"],
    "paddy": ["dhan", "dhaan", "chawal", "paddy", "rice", "धान", "चावल"],
    "maize": ["makka", "makai", "corn", "maize", "मक्का", "मकई"],
    "chana": ["chana", "gram", "chane", "चना", "चने"]
}

class AgriRAGService:
    def __init__(self):
        self.documents = AGRI_KNOWLEDGE_DOCUMENTS

    def _detect_crop(self, query: str) -> Optional[str]:
        q_lower = query.lower()
        for crop_key, aliases in CROP_ALIASES.items():
            for alias in aliases:
                if alias in q_lower:
                    return crop_key
        return None

    def retrieve(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        clean_query = query.lower()
        words = re.findall(r"[\w]+", clean_query)
        filtered_words = [w for w in words if w not in HINDI_STOPWORDS and len(w) > 1]

        detected_crop = self._detect_crop(clean_query)

        scored_docs = []
        for doc in self.documents:
            score = 0.0
            doc_crop = doc.get("crop", "all")

            # Crop compatibility filter
            if detected_crop and doc_crop not in [detected_crop, "all"]:
                continue

            # 1. Exact keyword match in keywords list
            for kw in doc.get("keywords", []):
                kw_lower = kw.lower()
                if kw_lower in clean_query:
                    score += 10.0
                else:
                    for qw in filtered_words:
                        if qw == kw_lower:
                            score += 6.0
                        elif qw in kw_lower and len(qw) > 2:
                            score += 2.0

            # 2. Topic keyword matches
            topic_lower = doc.get("topic", "").lower()
            for qw in filtered_words:
                if qw in topic_lower:
                    score += 4.0

            # 3. Boost if specific crop matches directly
            if detected_crop and doc_crop == detected_crop:
                score += 5.0

            if score > 5.0:  # Minimum relevance threshold
                scored_docs.append((score, doc))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored_docs[:top_k]]

    def answer_query(self, query: str, farmer_name: str = "Kisan Bhai") -> Optional[Dict[str, Any]]:
        clean = query.lower()

        # Strict Guardrail: Do NOT trigger disease/pest RAG on commodity/stock/mandi queries!
        advisory_intent_words = [
            "bimari", "beemari", "rog", "keeda", "keede", "faphund", "fungus", "virus", "sundi", "thrips",
            "safed makhi", "whitefly", "curl", "dawai", "spray", "chhidkaav", "ilaj", "upchar", "khad",
            "urea", "dap", "potash", "pila", "peele", "chhed", "sukh", "murjha", "jod", "patti", "patte",
            "blight", "borer", "pest", "disease", "treatment", "medicine", "fertilizer",
            "झुलसा", "रोग", "बीमारी", "दवाई", "दवा", "स्प्रे", "कीड़ा", "कीड़े", "इलाज", "उपचार", "खाद", "यूरिया", "पत्ते", "पीले", "छिड़काव"
        ]
        has_advisory_intent = any(w in clean for w in advisory_intent_words)
        if not has_advisory_intent:
            return None

        matched_docs = self.retrieve(query, top_k=1)
        if not matched_docs:
            return None

        doc = matched_docs[0]
        topic = doc.get("topic", "")
        content = doc.get("content", "")

        spoken = f"{farmer_name} ji! {topic} ke baare me ICAR krishi vigyan kendra ki scientific salah yeh hai: {content}"

        return {
            "spoken_text": spoken,
            "step": "AGRI_ADVISORY",
            "data": {
                "rag_retrieved": True,
                "doc_id": doc.get("id"),
                "topic": topic,
                "category": doc.get("category")
            }
        }

    def diagnose(self, crop: Optional[str], issue: Optional[str], query: str, farmer_name: str = "Kisan Bhai") -> Dict[str, Any]:
        """
        Direct semantic diagnosis called by the LLM Agentic Router.
        Zero rigid keywords: matches ICAR knowledge base or synthesizes standard ICAR treatment.
        """
        search_query = f"{crop or ''} {issue or ''} {query}".strip()
        matched_docs = self.retrieve(search_query, top_k=1)
        
        if matched_docs:
            doc = matched_docs[0]
            topic = doc.get("topic", f"{crop.capitalize() if crop else 'Fasal'} Rog Salah")
            content = doc.get("content", "")
            spoken = f"{farmer_name} ji! {topic} ke liye ICAR krishi vigyan kendra ki scientific salah: {content}"
            return {
                "spoken_text": spoken,
                "step": "AGRI_ADVISORY",
                "data": {
                    "rag_retrieved": True,
                    "doc_id": doc.get("id"),
                    "topic": topic,
                    "crop": crop,
                    "issue": issue
                }
            }
        
        # Standard ICAR treatment fallback for crops
        crop_key = (crop or "").lower()
        crop_disp = crop.capitalize() if crop else "Fasal"
        
        issue_clean = (issue or "").lower()
        remedy = None

        if crop_key == "tomato":
            if any(w in issue_clean for w in ["fruit_rot", "rot", "blight", "dhabbe", "sadne", "sadan", "spot"]):
                topic = "Tamatar Fal Sadan (Fruit Rot / Blight)"
                remedy = "Tamatar me fal sadne (Fruit Rot / Blight) ke liye: 1) Mancozeb 75 WP @ 2 gram prati liter paani me gholkar chhidkaav karein. 2) Khet me jal-jamaav na hone dein aur rogggrast falon ko nikal dein."
            elif any(w in issue_clean for w in ["leaf_curl", "curl", "peeli", "mud", "whitefly", "virus"]):
                topic = "Tamatar Leaf Curl Virus (पर्ण कुंचन रोग)"
                remedy = "Tamatar me pattiya mudne par safed makhi rokne ke liye: 1) Imidacloprid 17.8 SL @ 1 ml prati 3 liter paani me spray karein. 2) Neem ka tel 1500 PPM @ 3 ml/liter milayein."
            elif any(w in issue_clean for w in ["borer", "keeda", "chhed", "worm"]):
                topic = "Tamatar Fal Chhedak Keeda (Fruit Borer)"
                remedy = "Tamatar fal chhedak keede ke nidan ke liye: 1) Emamectin Benzoate 5 SG @ 4 gram prati 10 liter paani me milakar chhidkaav karein."
            else:
                topic = "Tamatar Fasal Rog Nidan"
                remedy = "Tamatar me rogon ke bachav ke liye Mancozeb 75 WP @ 2 gram prati liter paani me milakar chhidkaav karein."
        elif crop_key == "potato":
            topic = "Aloo Pichheti Jhulsa (Late Blight)"
            remedy = "Aloo me jhulsa rog ke liye: 1) Metalaxyl + Mancozeb (Ridomil MZ) @ 2.5 gram prati liter paani me gholkar chhidkaav karein."
        elif crop_key == "onion":
            topic = "Pyaaz Purpule Blotch Rog"
            remedy = "Pyaaz me purpule blotch ya jhulsa ke liye: 1) Difenoconazole 25 EC @ 1 ml prati liter paani me milakar chhidkaav karein."
        elif crop_key == "chilli":
            topic = "Mirch Chhoord Kurchan / Thrips"
            remedy = "Mirch me pattiya mudne ya thrips ke liye: 1) Fipronil 5 SC @ 2 ml prati liter paani me milakar chhidkaav karein."
        elif crop_key == "wheat":
            topic = "Gehun Peela Ratua (Yellow Rust)"
            remedy = "Gehun me peela ratua (yellow rust) ke liye: 1) Propiconazole 25 EC (Tilt) @ 1 ml prati liter paani me chhidkaav karein."
        else:
            topic = f"{crop_disp} Rog Nidan"
            remedy = f"{crop_disp} me samasya ke nidan ke liye saf saafai rakhein aur nazdeeki KVK ya Krishi Seva Kendra se sampark karein."

        spoken = f"{farmer_name} ji! {topic} ke liye ICAR Krishi Vigyan salah: {remedy}"
        return {
            "spoken_text": spoken,
            "step": "AGRI_ADVISORY",
            "data": {
                "rag_retrieved": False,
                "topic": topic,
                "crop": crop,
                "issue": issue
            }
        }

agri_rag = AgriRAGService()
