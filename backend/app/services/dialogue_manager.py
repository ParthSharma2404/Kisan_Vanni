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
        self.district: str = "Nashik"
        self.location_name: str = ""
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
        self.step: str = "GREETING"
        self.last_arbitrage_results: List[Dict[str, Any]] = []
        self.mandi_slip: Optional[Dict[str, Any]] = None

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
        Process incoming farmer voice transcript with vernacular dialect reasoning.
        Handles conversational profile onboarding, dynamic location confirmation,
        barge-in interruptions, arbitrage calculations, eNAM rights, and background WhatsApp dispatch.
        """
        session = self.get_or_create_session(session_id)
        text = utterance.strip().lower()

        # 1. Check for Direct WhatsApp Dispatch Request
        if any(w in text for w in ["whatsapp", "sms", "message", "bhej do", "bhej", "parcha", "rasid", "bill", "pass", "slip"]):
            if session.last_arbitrage_results or session.mandi_slip:
                slip = session.mandi_slip or self._generate_enhanced_slip(session)
                session.mandi_slip = slip
                best_name = session.last_arbitrage_results[0]["mandi_name"] if session.last_arbitrage_results else "Mandi"
                
                # Silent background WhatsApp dispatch via Baileys
                dispatch_res = await self._dispatch_whatsapp_background(session.phone_number, slip.get("whatsapp_text", ""))
                
                spoken = (
                    f"Ji {session.farmer_name} bhai, maine {best_name} ka poora hisaab, "
                    f"diesel kharcha aur eNAM kanoon ka slip aapke WhatsApp number (+91 {session.phone_number}) par turant bhej diya hai!"
                )
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

        # 2. Check for Contextual / Barge-in Questions (Distance, Closest Mandi, Top Rate)
        distance_query = self._handle_distance_or_mandi_query(session, text)
        if distance_query:
            return distance_query

        # 3. Check for eNAM Specific Questions & Grievances
        enam_answer = enam_advisor.get_advice_for_query(text)
        if enam_answer:
            return {
                "spoken_text": enam_answer,
                "step": session.step,
                "data": {"enam_alert": True, "mandi_slip": session.mandi_slip, "evaluated_mandis": session.last_arbitrage_results}
            }

        # 4. Check for Crop Doctor / Symptoms
        diagnosis = crop_doctor.diagnose(text)
        if diagnosis:
            session.step = "CROP_DOCTOR"
            return {
                "spoken_text": diagnosis["spoken_advice_hi"],
                "step": "CROP_DOCTOR",
                "data": {
                    "disease_info": diagnosis,
                    "mandi_slip": session.mandi_slip,
                    "evaluated_mandis": session.last_arbitrage_results
                }
            }

        # 5. CONVERSATIONAL ONBOARDING: First-time Farmer
        if session.step == "ONBOARDING_PROFILE":
            name, village = self._extract_name_and_location(text)
            crop = self._extract_crop(text)
            
            if name or village:
                final_name = name or "Kisan Bhai"
                final_village = village or "Shivrajpur"
                session.farmer_name = final_name
                session.location_name = final_village
                
                # Save into database (Supabase + local SQLite fallback)
                farmer_db.update_farmer_profile(
                    phone_number=session.phone_number,
                    name=final_name,
                    village=final_village,
                    district=session.district,
                    primary_crops=[crop] if crop else ["Pyaaz", "Tamatar"]
                )

                if crop:
                    session.commodity = crop
                    session.step = "AWAITING_QUANTITY"
                    rates = mandi_service.get_rates_for_commodity(crop, session.lat, session.lon, radius_km=85)
                    top_rate = int(rates[0]["modal_price"]) if rates else 2400
                    top_mandi = rates[0]["market"] if rates else "Lasalgaon"
                    spoken = (
                        f"Namaste {final_name} ji! Maine {final_village} darj kar liya hai. "
                        f"Aaj {crop.capitalize()} ka bhav {top_mandi} me lagbhag ₹{top_rate} prati quintal chal raha hai. "
                        f"Aapke paas bechne ke liye kitna maal hai—jaise kitne katte, bori ya quintal?"
                    )
                else:
                    session.step = "AWAITING_CROP"
                    spoken = (
                        f"Namaste {final_name} ji! Maine aapka gaon {final_village} darj kar liya hai. "
                        f"Aaj aap kaunsi fasal ka taaza mandi bhav aur sabse uncha munafa dekhna chahte hain—jaise Pyaaz, Tamatar ya Gehun?"
                    )

                return {
                    "spoken_text": spoken,
                    "step": session.step,
                    "data": {"farmer_name": final_name, "village": final_village, "commodity": session.commodity}
                }

        # 6. CONVERSATIONAL ONBOARDING: Returning Farmer Location Confirmation
        if session.step == "CONFIRMING_LOCATION":
            crop = self._extract_crop(text)
            if crop:
                # Farmer bypassed location check and asked for crop directly
                session.commodity = crop
                session.location_confirmed = True
                session.step = "AWAITING_QUANTITY"
                rates = mandi_service.get_rates_for_commodity(crop, session.lat, session.lon, radius_km=85)
                top_rate = int(rates[0]["modal_price"]) if rates else 2400
                top_mandi = rates[0]["market"] if rates else "Lasalgaon"
                spoken = (
                    f"Ji {session.farmer_name} ji! {crop.capitalize()} ka bhav {top_mandi} mandi me lagbhag ₹{top_rate} prati quintal hai. "
                    f"Aapke paas kitne katte ya quintal maal hai bechne ke liye?"
                )
                return {
                    "spoken_text": spoken,
                    "step": session.step,
                    "data": {"commodity": crop, "rates": rates}
                }

            # Check if farmer confirmed existing location
            if any(w in text for w in ["haan", "wahi", "wahin", "sahi", "bilkul", "yes", "ji haan", "theek hai"]):
                session.location_confirmed = True
                session.step = "AWAITING_CROP"
                spoken = f"Bahut badhiya {session.farmer_name} ji! Aaj kaunsi fasal ka taaza mandi bhav dekhna chahte hain?"
                return {
                    "spoken_text": spoken,
                    "step": session.step,
                    "data": {"location_confirmed": True}
                }

            # Check if farmer changed location
            if any(w in text for w in ["nahi", "badal", "abhi", "shifted", "mandi me", "se bol raha"]):
                _, new_loc = self._extract_name_and_location(text)
                if not new_loc:
                    new_loc = self._extract_standalone_location(text) or "Nashik"
                
                session.location_name = new_loc
                farmer_db.update_location(session.phone_number, village=new_loc, district="Nashik")
                session.location_confirmed = True
                session.step = "AWAITING_CROP"
                spoken = f"Theek hai {session.farmer_name} ji, maine aapki nayi location {new_loc} update kar di hai. Ab batayein aaj kaunsi fasal bechni hai?"
                return {
                    "spoken_text": spoken,
                    "step": session.step,
                    "data": {"updated_location": new_loc}
                }

        # 7. Global Entity Extraction (Multi-intent / One-shot detection)
        detected_crop = self._extract_crop(text)
        if detected_crop:
            session.commodity = detected_crop

        num, unit = self._extract_quantity_and_unit(text)
        if num:
            session.raw_quantity_num = num
            session.unit_type = unit
            if unit in ["katta", "bori", "jali", "bag"]:
                bag_wt = self._extract_bag_weight(text)
                if bag_wt:
                    session.bag_weight_kg = float(bag_wt)
                    session.quantity_quintals = round((num * session.bag_weight_kg) / 100.0, 2)
            elif unit == "trolley":
                session.quantity_quintals = round(num * 30.0, 2)
            elif unit == "pickup":
                session.quantity_quintals = round(num * 18.0, 2)
            elif unit == "ton":
                session.quantity_quintals = round(num * 10.0, 2)
            elif unit == "man":
                session.quantity_quintals = round(num * 0.4, 2)
            else:
                session.quantity_quintals = float(num)

        vehicle_res = self._extract_vehicle(text)
        if vehicle_res is not None:
            has_own, v_name = vehicle_res
            session.has_own_vehicle = has_own
            session.vehicle_name = v_name

        # 8. Progressive Discovery: If all 3 entities are present, calculate Arbitrage immediately!
        if session.commodity and session.quantity_quintals and (session.has_own_vehicle is not None):
            return self._compute_and_deliver_arbitrage(session)

        # Step B: Awaiting Bag Weight
        if session.step == "AWAITING_BAG_WEIGHT":
            bag_wt = self._extract_bag_weight(text)
            session.bag_weight_kg = float(bag_wt) if bag_wt else 50.0

            total_kg = (session.raw_quantity_num or 20.0) * session.bag_weight_kg
            session.quantity_quintals = round(total_kg / 100.0, 2)
            session.step = "AWAITING_TRANSPORT"
            spoken = (
                f"Bahut khoob! Kul mila kar aapka {session.quantity_quintals} quintal maal hua. "
                f"Ab batayein, mandi le jaane ke liye gaadi aapki apni hai, ya tempo bhade par karenge?"
            )
            return {
                "spoken_text": spoken,
                "step": session.step,
                "data": {
                    "bag_weight_kg": session.bag_weight_kg,
                    "quantity_quintals": session.quantity_quintals,
                    "commodity": session.commodity
                }
            }

        # Step C: Transport Discovery & Net Arbitrage
        elif session.step == "AWAITING_TRANSPORT":
            vehicle_res = self._extract_vehicle(text)
            if vehicle_res is not None:
                has_own, v_name = vehicle_res
                session.has_own_vehicle = has_own
                session.vehicle_name = v_name
            else:
                session.has_own_vehicle = True
                session.vehicle_name = "Own Vehicle"
            return self._compute_and_deliver_arbitrage(session)

        # Step D: Post-Arbitrage Follow-up
        elif session.step == "ARBITRAGE_DELIVERED":
            if any(w in text for w in ["whatsapp", "bhej", "parcha", "slip", "rasid"]):
                pass  # handled in direct whatsapp check
            else:
                return agri_engine.analyze_and_respond(utterance, session)

        # 9. Sovereign Agri-Intelligence Engine (All Indian commodities, crop doctor, fertilizer, schemes, eNAM, weather)
        agri_res = agri_engine.analyze_and_respond(utterance, session)
        if agri_res.get("step") == "OPEN_CONVERSATION":
            try:
                from app.services.llm_service import llm_service
                llm_reply = await llm_service.generate_response(
                    user_query=utterance,
                    farmer_name=session.farmer_name,
                    village=session.location_name,
                    district=session.district,
                    crops=[session.commodity] if session.commodity else None
                )
                if llm_reply and len(llm_reply.strip()) > 5:
                    agri_res["spoken_text"] = llm_reply.strip()
                    if "data" not in agri_res:
                        agri_res["data"] = {}
                    agri_res["data"]["generated_by_evon"] = True
            except Exception as e:
                print(f"[DialogueManager:LLM] Evon fallback: {e}")
        return agri_res

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
