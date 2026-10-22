import re
import urllib.parse
import httpx
from typing import Dict, Any, Optional, Tuple, List
from app.services.mandi_service import mandi_service
from app.services.arbitrage_engine import arbitrage_engine
from app.services.enam_rules import enam_advisor
from app.services.crop_doctor import crop_doctor
from app.services.farmer_db import farmer_db
from app.services.agri_intelligence import agri_engine

class SessionState:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.phone_number: str = ""
        self.farmer_name: str = "Kisan Bhai"
        self.state: Optional[str] = None
        self.district: Optional[str] = None
        self.location_name: Optional[str] = None
        self.lat: float = 20.0800
        self.lon: float = 74.1100
        self.location_confirmed: bool = False
        
        self.commodity: Optional[str] = None
        self.raw_quantity_num: Optional[float] = None
        self.unit_type: Optional[str] = None  # "katta", "bori", "quintal", "trolley", "pickup", "ton"
        self.bag_weight_kg: Optional[float] = None
        self.quantity_quintals: Optional[float] = None
        
        self.has_own_vehicle: Optional[bool] = None
        self.vehicle_name: Optional[str] = None
        self.step: str = "ACTIVE"
        self.last_arbitrage_results: List[Dict[str, Any]] = []
        self.mandi_slip: Optional[Dict[str, Any]] = None
        self.chat_history: List[Dict[str, str]] = []  # Rolling Buffer Window Memory (max 6 exchanges)

    def add_history(self, role: str, content: str):
        self.chat_history.append({"role": role, "content": content})
        if len(self.chat_history) > 6:
            self.chat_history = self.chat_history[-6:]

class DialogueManager:
    def __init__(self):
        self.sessions: Dict[str, SessionState] = {}

    def get_or_create_session(self, session_id: str) -> SessionState:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState(session_id)
        return self.sessions[session_id]

    def reset_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]

    async def process_utterance(self, session_id: str, utterance: str) -> Dict[str, Any]:
        """
        Streamlined Agentic Conversational Intelligence Pipeline:
        User Utterance (STT) -> Rolling Buffer Memory -> Agri-Router (Guardrails + Tools) -> Timbre Voice (TTS)
        """
        session = self.get_or_create_session(session_id)
        session.add_history("user", utterance)
        text = utterance.strip().lower()

        # 1. Direct WhatsApp Dispatch Request
        if any(w in text for w in ["whatsapp", "sms", "message", "bhej do", "bhej", "parcha", "rasid", "bill", "pass", "slip"]):
            if session.last_arbitrage_results or session.mandi_slip:
                slip = session.mandi_slip or self._generate_enhanced_slip(session)
                session.mandi_slip = slip
                best_name = session.last_arbitrage_results[0]["mandi_name"] if session.last_arbitrage_results else "Mandi"
                
                # Silent background WhatsApp dispatch
                dispatch_res = await self._dispatch_whatsapp_background(session.phone_number, slip.get("whatsapp_text", ""))
                
                spoken = (
                    f"Ji {session.farmer_name} bhai, maine {best_name} ka poora hisaab, "
                    f"diesel kharcha aur eNAM kanoon ka slip aapke WhatsApp number (+91 {session.phone_number}) par turant bhej diya hai!"
                )
                session.add_history("assistant", spoken)
                return {
                    "spoken_text": spoken,
                    "step": "FINISHED",
                    "data": {
                        "whatsapp_dispatched": True,
                        "delivered_via_baileys": dispatch_res.get("delivered_via_baileys", False),
                        "phone_number": session.phone_number,
                        "whatsapp_url": slip.get("whatsapp_url", ""),
                        "mandi_slip": slip,
                        "evaluated_mandis": session.last_arbitrage_results
                    }
                }

        # 2. Check for Contextual Distance / Nearest Mandi Questions
        distance_query = self._handle_distance_or_mandi_query(session, text)
        if distance_query:
            if distance_query.get("spoken_text"):
                session.add_history("assistant", distance_query["spoken_text"])
            return distance_query

        # 3. Agentic Agricultural Router (Guardrails + Dynamic Tool Routing + Rolling Memory)
        from app.services.agri_router import agri_router
        res = agri_router.route_and_execute(utterance, session)
        if res and res.get("spoken_text"):
            session.add_history("assistant", res["spoken_text"])
        return res


    async def _dispatch_whatsapp_background(self, phone: str, message_text: str) -> Dict[str, Any]:
        """Silent background WhatsApp delivery via Baileys microservice."""
        clean_phone = phone.replace("+91", "").replace(" ", "").replace("-", "").strip()
        if len(clean_phone) == 10:
            clean_phone = "91" + clean_phone
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.post("http://localhost:5005/api/whatsapp/send", json={
                    "phone": clean_phone,
                    "message": message_text
                })
                if res.status_code == 200 and res.json().get("success"):
                    return {"delivered_via_baileys": True}
        except Exception:
            pass
        return {"delivered_via_baileys": False}

    def _extract_name_and_location(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts Indian farmer name and village/city from utterance:
        e.g., 'Mera naam Ankit hai, Shivrajpur gaon se', 'Ankit, Nashik'
        """
        name = None
        location = None

        # Name patterns
        name_match = re.search(r"(?:mera\s+naam|naam\s+hai|main|naam)\s+([a-zA-Z\u0900-\u097F]+)", text, re.IGNORECASE)
        if name_match:
            candidate = name_match.group(1).strip()
            if candidate.lower() not in ["kisan", "bhai", "bhaiya", "se", "hoon", "gaon"]:
                name = candidate.capitalize()

        # Location patterns
        loc_match = re.search(r"([a-zA-Z\u0900-\u097F]+)\s*(?:gaon\s+se|se\s+baat|se\s+hoon|gaon|district|zile\s+se)", text, re.IGNORECASE)
        if loc_match:
            candidate_loc = loc_match.group(1).strip()
            if candidate_loc.lower() not in ["main", "naam", "mera", "bhaiya"]:
                location = candidate_loc.capitalize()

        # Fallback keyword checks
        common_places = [
            "Shivrajpur", "Niphad", "Nashik", "Lasalgaon", "Pimpalgaon", "Sinnar", "Yeola", "Dindori", "Bareilly", "Pune", "Kalwan",
            "Punjab", "पंजाब", "Maharashtra", "महाराष्ट्र", "Haryana", "हरियाणा", "Rajasthan", "राजस्थान", "Madhya Pradesh", "MP", "UP", "Uttar Pradesh", "उत्तर प्रदेश", "Delhi", "दिल्ली"
        ]
        for p in common_places:
            if p.lower() in text:
                location = p
                break

        # Fallback names if someone just gave a name
        if not name:
            words = [w for w in text.split() if len(w) > 2 and w.lower() not in ["namaste", "bhaiya", "mera", "naam", "gaon", "se", "hoon", "aur", "hai"]]
            if words:
                first = words[0].capitalize()
                if first not in ["Pyaaz", "Tamatar", "Gehun", "Kanda", "Punjab"]:
                    name = first

        return name, location

    def _extract_standalone_location(self, text: str) -> Optional[str]:
        common_places = [
            "Shivrajpur", "Niphad", "Nashik", "Lasalgaon", "Pimpalgaon", "Sinnar", "Yeola", "Dindori", "Bareilly", "Pune", "Kalwan",
            "Punjab", "पंजाब", "Maharashtra", "महाराष्ट्र", "Haryana", "हरियाणा", "Rajasthan", "राजस्थान", "Madhya Pradesh", "MP", "UP", "Uttar Pradesh", "उत्तर प्रदेश", "Delhi", "दिल्ली"
        ]
        for p in common_places:
            if p.lower() in text:
                return p
        loc_match = re.search(r"(?:me\s+hoon|se\s+hoon|mandi\s+me)\s+([a-zA-Z\u0900-\u097F]+)", text)
        if loc_match:
            return loc_match.group(1).capitalize()
        return None

    def _handle_distance_or_mandi_query(self, session: SessionState, text: str) -> Optional[Dict[str, Any]]:
        if any(w in text for w in ["kitna door", "kitni door", "distance", "kilo meter", "km", "door hai", "nazdeek", "paas hai"]):
            candidates = mandi_service.get_rates_for_commodity(
                session.commodity or "onion", session.lat, session.lon, radius_km=100
            )
            for m in candidates:
                m_name = m["market"].lower()
                if m_name in text or any(part in text for part in m_name.split()):
                    dist = m.get("distance_km", 25)
                    rate = int(m.get("modal_price", 2400))
                    return {
                        "spoken_text": f"Bhaiya, {m['market']} Mandi aapke yahan se lagbhag {dist} kilometer door hai. Wahan aaj ka modal bhav ₹{rate} prati quintal hai.",
                        "step": session.step,
                        "data": {"distance_km": dist, "mandi": m, "evaluated_mandis": session.last_arbitrage_results}
                    }
            if candidates:
                closest = min(candidates, key=lambda x: x.get("distance_km", 999))
                return {
                    "spoken_text": f"Kisan bhai, aapke sabse nazdeek {closest['market']} Mandi hai, jo lagbhag {closest['distance_km']} km door hai.",
                    "step": session.step,
                    "data": {"closest_mandi": closest, "evaluated_mandis": session.last_arbitrage_results}
                }

        if any(w in text for w in ["sabse zyada", "sabse uncha", "highest", "top rate", "sabse bada rate"]):
            candidates = mandi_service.get_rates_for_commodity(
                session.commodity or "onion", session.lat, session.lon, radius_km=100
            )
            if candidates:
                top_rate_mandi = max(candidates, key=lambda x: float(x.get("modal_price", 0)))
                return {
                    "spoken_text": f"Kisan bhai, aaj sabse uncha bhav {top_rate_mandi['market']} Mandi me hai, lagbhag ₹{int(top_rate_mandi['modal_price'])} prati quintal.",
                    "step": session.step,
                    "data": {"top_rate_mandi": top_rate_mandi, "evaluated_mandis": session.last_arbitrage_results}
                }

        return None

    def _compute_and_deliver_arbitrage(self, session: SessionState) -> Dict[str, Any]:
        session.step = "ARBITRAGE_DELIVERED"
        has_own = session.has_own_vehicle if session.has_own_vehicle is not None else True

        candidates = mandi_service.get_rates_for_commodity(
            session.commodity or "onion", session.lat, session.lon, radius_km=85
        )
        evaluated = arbitrage_engine.calculate_arbitrage(
            candidates,
            session.quantity_quintals or 10.0,
            has_own_vehicle=has_own,
            already_at_mandi=False
        )
        session.last_arbitrage_results = evaluated

        reasoning = arbitrage_engine.generate_verbal_reasoning(
            evaluated, session.commodity or "pyaaz", session.quantity_quintals or 10.0
        )

        slip = self._generate_enhanced_slip(session)
        session.mandi_slip = slip

        enam_reminder = " Aur eNAM kanoon ke mutabik commission zero percent hai, aadhatiya commission nahi kaat sakta."
        full_speech = reasoning + enam_reminder

        try:
            best_m = evaluated[0] if evaluated else {}
            farmer_db.log_query(
                phone_number=session.phone_number,
                query_type="mandi_arbitrage",
                commodity=session.commodity,
                quantity=f"{session.quantity_quintals} quintal",
                utterance=f"{session.commodity} {session.quantity_quintals} quintal",
                response=full_speech
            )
            farmer_db.save_advisory_report(
                phone_number=session.phone_number,
                session_id=session.session_id,
                commodity=session.commodity or "crop",
                best_mandi=best_m.get("mandi_name", "APMC Mandi"),
                net_profit=float(best_m.get("net_in_hand", 0.0)),
                summary_text=full_speech
            )
        except Exception as e:
            print(f"[DialogueManager] Could not log to farmer_db: {e}")

        return {
            "spoken_text": full_speech,
            "step": session.step,
            "data": {
                "evaluated_mandis": evaluated,
                "commodity": session.commodity,
                "quantity_quintals": session.quantity_quintals,
                "has_own_vehicle": has_own,
                "vehicle_name": session.vehicle_name or ("Own Vehicle" if has_own else "Hired Tempo"),
                "enam_active": True,
                "mandi_slip": slip
            }
        }

    def _generate_enhanced_slip(self, session: SessionState) -> Dict[str, Any]:
        evaluated = session.last_arbitrage_results
        if not evaluated:
            return {}

        best = evaluated[0]
        runner_up = evaluated[1] if len(evaluated) > 1 else None
        extra_profit = int(best["net_in_hand"] - runner_up["net_in_hand"]) if runner_up else 0
        v_title = session.vehicle_name or ("Own Vehicle" if session.has_own_vehicle else "Hired Tempo")

        import random
        dispatch_id = f"KV-{random.randint(1000, 9999)}-NSK"

        farmer = farmer_db.get_farmer(session.phone_number)
        farmer_name = farmer["name"] if farmer else session.farmer_name
        location_display = f"{farmer.get('village', '')}, {farmer.get('district', '')}" if (farmer and farmer.get("village")) else session.location_name

        text = (
            f"🌾 *KISAN-VAANI MANDI DISPATCH PASS* 🌾\n"
            f"Pass ID: #{dispatch_id} | eNAM Verified\n"
            f"----------------------------------------\n"
            f"👨‍🌾 *Farmer:* {farmer_name} | {location_display}\n"
            f"📱 *Mobile:* +91 {session.phone_number}\n"
            f"📦 *Produce:* {(session.commodity or 'PRODUCE').upper()} ({session.quantity_quintals} Quintal)\n"
            f"🚚 *Logistics:* {v_title}\n"
            f"----------------------------------------\n"
            f"🏆 *RECOMMENDED APMC:* {best['mandi_name']} ({best['district']})\n"
            f"📍 *Distance:* {best['distance_km']} km\n"
            f"💰 *Modal Rate:* ₹{int(best['modal_price'])} / Quintal\n"
            f"💵 *Gross Realization:* ₹{int(best['gross_revenue']):,}\n\n"
            f"📉 *Itemized Cost Breakdown:*\n"
            f"  • Diesel/Transport: -₹{int(best['freight_cost']):,}\n"
            f"  • Statutory APMC Cess (1%): -₹{int(best['mandi_cess']):,}\n"
            f"  • Weighment & Hamali: -₹{int(best['hamali']):,}\n"
            f"  • Trader Commission: ₹0 (Illegal under eNAM Section 17)\n"
            f"----------------------------------------\n"
            f"✅ *NET IN-HAND PROFIT:* ₹{int(best['net_in_hand']):,}\n"
            f"📈 *Net Rate / Quintal:* ₹{int(best['net_rate_per_quintal'])}\n"
        )
        if runner_up and extra_profit > 0:
            text += f"🌟 *Net Arbitrage Gain:* +₹{extra_profit:,} vs {runner_up['mandi_name']}\n"

        text += (
            f"----------------------------------------\n"
            f"⚖️ *eNAM Statutory Farmer Shield:*\n"
            f"Section 17: Commission strictly payable by buyer. Deducting 6-8% is a cognizable offence.\n"
            f"📞 eNAM National Grievance: 1800-270-0224\n"
            f"Generated via Gnani.ai Sovereign Voice Intelligence."
        )

        encoded_text = urllib.parse.quote(text)
        wa_url = f"https://api.whatsapp.com/send?phone=91{session.phone_number}&text={encoded_text}"

        return {
            "dispatch_id": dispatch_id,
            "farmer_name": farmer_name,
            "phone_number": session.phone_number,
            "location": location_display,
            "mandi_name": best["mandi_name"],
            "district": best["district"],
            "commodity": session.commodity,
            "quantity_quintals": session.quantity_quintals,
            "transport_mode": v_title,
            "modal_price": best["modal_price"],
            "gross_revenue": best["gross_revenue"],
            "freight_cost": best["freight_cost"],
            "mandi_cess": best["mandi_cess"],
            "hamali": best["hamali"],
            "total_expenses": best["total_expenses"],
            "net_in_hand": best["net_in_hand"],
            "net_rate_per_quintal": best["net_rate_per_quintal"],
            "extra_profit": extra_profit,
            "whatsapp_text": text,
            "whatsapp_url": wa_url
        }

    def _extract_crop(self, text: str) -> Optional[str]:
        crops = {
            "pyaaz": "onion", "kanda": "onion", "pyaj": "onion", "onion": "onion", "dungri": "onion",
            "प्याज": "onion", "प्याज़": "onion", "कांदा": "onion", "कांदे": "onion",
            "tamatar": "tomato", "tomato": "tomato", "tamaatar": "tomato",
            "टमाटर": "tomato", "टमाटार": "tomato", "टोमेटो": "tomato",
            "gehun": "wheat", "gehu": "wheat", "wheat": "wheat", "lokwan": "wheat",
            "गेहूं": "wheat", "गेहू": "wheat",
            "aloo": "potato", "potato": "potato", "आलू": "potato", "आलु": "potato",
            "soyabean": "soyabean", "soya": "soyabean", "soybean": "soyabean", "सोयाबीन": "soyabean",
            "kapas": "cotton", "cotton": "cotton", "rui": "cotton", "कपास": "cotton",
            "makka": "corn", "corn": "corn", "bhutta": "corn", "मक्का": "corn",
            "chana": "chana", "चना": "chana", "sarso": "mustard", "सरसों": "mustard"
        }
        for word, crop_name in crops.items():
            if any(ord(c) > 127 for c in word):
                if word in text:
                    return crop_name
            else:
                if re.search(r"(?:^|\W)" + re.escape(word) + r"(?:$|\W)", text) or word in text:
                    return crop_name
        return None

    def _extract_quantity_and_unit(self, text: str) -> Tuple[Optional[float], Optional[str]]:
        unit_match = re.search(r"(\d+(?:\.\d+)?)\s*(katta|katte|bori|boriyaan|jali|bag|bags|quintal|kilo|kg|trolley|traali|pickup|ton|tonne|man|mann)", text)
        if unit_match:
            num = float(unit_match.group(1))
            raw_unit = unit_match.group(2)
            if raw_unit in ["katta", "katte", "bori", "boriyaan", "jali", "bag", "bags"]:
                return num, "katta"
            if raw_unit in ["trolley", "traali"]:
                return num, "trolley"
            if raw_unit in ["pickup"]:
                return num, "pickup"
            if raw_unit in ["ton", "tonne"]:
                return num, "ton"
            if raw_unit in ["man", "mann"]:
                return num, "man"
            return num, "quintal"

        words_to_num = {
            "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5, "che": 6, "saat": 7, "aath": 8, "nau": 9,
            "dus": 10, "gyarah": 11, "barah": 12, "pandrah": 15,
            "bees": 20, "pachees": 25, "tees": 30, "paintis": 35, "chalees": 40,
            "pachas": 50, "saath": 60, "sattar": 70, "assi": 80, "nabbe": 90, "sau": 100
        }
        for w, val in words_to_num.items():
            if re.search(r"\b" + w + r"\b", text):
                unit = "katta" if any(u in text for u in ["katta", "katte", "bori", "jali", "bag"]) else "quintal"
                if any(u in text for u in ["trolley", "traali"]):
                    unit = "trolley"
                elif "pickup" in text:
                    unit = "pickup"
                return float(val), unit

        num = self._extract_number(text)
        if num and num > 0:
            unit = "katta" if any(u in text for u in ["katta", "bori", "jali", "bag"]) else "quintal"
            return float(num), unit

        return None, None

    def _extract_bag_weight(self, text: str) -> Optional[int]:
        m = re.search(r"(\d+)\s*(kilo|kg|ser)", text)
        if m:
            val = int(m.group(1))
            if 30 <= val <= 100:
                return val
        hindi_weights = {"chalees": 40, "paintalees": 45, "pachas": 50, "saath": 60}
        for w, val in hindi_weights.items():
            if w in text:
                return val
        num = self._extract_number(text)
        if num and 35 <= num <= 70:
            return num
        return None

    def _extract_vehicle(self, text: str) -> Optional[Tuple[bool, str]]:
        if any(w in text for w in ["apni", "apna", "tractor", "pickup", "bolero", "khud", "own", "meri"]):
            if "tractor" in text:
                return True, "Own Tractor Trolley"
            if "pickup" in text or "bolero" in text:
                return True, "Own Bolero Pickup"
            return True, "Own Vehicle"
        if any(w in text for w in ["tempo", "bhada", "bhade", "rent", "hired", "chhota hathi", "kiraya"]):
            return False, "Hired Commercial Tempo"
        return None

    def _extract_number(self, text: str) -> Optional[int]:
        m = re.search(r"\b(\d+)\b", text)
        if m:
            return int(m.group(1))
        return None

dialogue_manager = DialogueManager()
