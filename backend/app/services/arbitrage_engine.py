from typing import List, Dict, Any
from app.config import settings

class ArbitrageEngine:
    def calculate_arbitrage(
        self,
        mandi_candidates: List[Dict[str, Any]],
        quantity_quintals: float,
        has_own_vehicle: bool = False,
        already_at_mandi: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Calculate Net Realizable Value (NRV) for each candidate mandi.
        Factors in:
        1. Gross Value = Modal Price * Weight
        2. Transport:
           - Already at mandi: 0
           - Own vehicle: Diesel cost only (distance * 2 for round trip * consumption)
           - Rented tempo: Base freight + per km rate
        3. Statutory Mandi Cess (e.g. 1.05%)
        4. Handling / Hamali per quintal
        """
        if quantity_quintals <= 0:
            quantity_quintals = 1.0

        evaluated = []
        for m in mandi_candidates:
            modal_price = float(m["modal_price"])
            distance_km = float(m.get("distance_km", 10.0))
            gross_revenue = modal_price * quantity_quintals

            # Transport Cost Calculation
            # Micro-lots (< 100 kg / 1 quintal) realistically move via personal two-wheeler, bus, or shared auto for local distances
            is_micro_lot = quantity_quintals < 1.0

            if already_at_mandi or distance_km < 1.0:
                freight_cost = 0.0
                transport_mode = "Local / Zero Distance"
            elif has_own_vehicle:
                if is_micro_lot and distance_km <= 25.0:
                    # Two-wheeler / personal scooter trip for small bag (10-50 kg)
                    freight_cost = round(min(80.0, max(25.0, distance_km * 2 * 2.5)), 2)
                    transport_mode = "Two-Wheeler / Personal Trip"
                else:
                    # Own vehicle (Bolero/Tractor): Only calculate diesel for round-trip
                    round_trip_km = distance_km * 2
                    freight_cost = round(round_trip_km * settings.DIESEL_COST_PER_KM, 2)
                    transport_mode = "Own Vehicle (Diesel only)"
            else:
                if is_micro_lot and distance_km <= 15.0:
                    # Shared auto or local bus parcel for micro-lot
                    freight_cost = 40.0
                    transport_mode = "Shared Auto / Local Transit"
                else:
                    # Hired Tempo / Commercial freight
                    extra_km = max(0.0, distance_km - 10.0)
                    freight_cost = round(settings.BASE_FREIGHT_COST + (extra_km * settings.PER_KM_FREIGHT_RATE), 2)
                    transport_mode = "Hired Tempo"

            # Statutory Mandi Cess (percentage of gross)
            cess_pct = float(m.get("apmc_cess_pct", 1.0)) / 100.0
            mandi_cess = round(gross_revenue * cess_pct, 2)

            # Hamali / Handling charges (statutory cap)
            hamali = round(settings.HAMALI_PER_QUINTAL * quantity_quintals, 2)

            # Total deductions
            total_expenses = freight_cost + mandi_cess + hamali
            net_in_hand = round(gross_revenue - total_expenses, 2)

            # Viability Guardrail: Never blow up into absurd negative rates per quintal (e.g. -₹34,152/qtl)
            if net_in_hand <= 0:
                is_viable = False
                viability_status = "UNVIABLE_HIGH_LOGISTICS"
                net_rate_per_quintal = 0.0
                deficit_amount = round(abs(net_in_hand), 2)
                viability_reason = f"Logistics expense (₹{total_expenses:.0f}) exceeds total crop gross value (₹{gross_revenue:.0f}) for {quantity_quintals} qtl."
            else:
                is_viable = True
                viability_status = "VIABLE"
                net_rate_per_quintal = round(net_in_hand / quantity_quintals, 2)
                deficit_amount = 0.0
                viability_reason = "Profitable realization after logistics and statutory charges."

            evaluated.append({
                "mandi_name": m["market"],
                "district": m["district"],
                "state": m.get("state", ""),
                "modal_price": modal_price,
                "distance_km": distance_km,
                "gross_revenue": gross_revenue,
                "freight_cost": freight_cost,
                "mandi_cess": mandi_cess,
                "hamali": hamali,
                "total_expenses": total_expenses,
                "net_in_hand": net_in_hand,
                "net_rate_per_quintal": net_rate_per_quintal,
                "is_viable": is_viable,
                "viability_status": viability_status,
                "deficit_amount": deficit_amount,
                "viability_reason": viability_reason,
                "is_arrival_surge": m.get("is_arrival_surge", False),
                "transport_mode": transport_mode
            })

        # Sort: Viable mandis first sorted by net_in_hand descending,
        # then unviable mandis sorted by distance_km ascending (closest first)
        evaluated.sort(
            key=lambda x: (1 if x["is_viable"] else 0, x["net_in_hand"] if x["is_viable"] else -x["distance_km"]),
            reverse=True
        )
        return evaluated

    def generate_verbal_reasoning(
        self,
        evaluated: List[Dict[str, Any]],
        commodity: str,
        quantity_quintals: float
    ) -> str:
        """
        Generate clear, honest, and persuasive Hindi verbal reasoning
        comparing the best mandi against alternatives.
        """
        if not evaluated:
            return "Maaf kijiye kisan bhai, aapke aas-paas is fasal ka taza rate abhi darj nahi hua hai."

        best = evaluated[0]
        if len(evaluated) == 1:
            return (
                f"Kisan bhai, aapke sabse paas {best['mandi_name']} Mandi hai. "
                f"Yahan {commodity} ka modal bhav ₹{int(best['modal_price'])} prati quintal hai. "
                f"Aapke {quantity_quintals} quintal maal ka kharcha nikaal kar lagbhag ₹{int(best['net_in_hand'])} haath me aayenge."
            )

        runner_up = evaluated[1]
        diff_profit = int(best["net_in_hand"] - runner_up["net_in_hand"])

        if diff_profit > 200:
            return (
                f"Kisan bhai, dhyan se suniye: {runner_up['mandi_name']} Mandi me rate ₹{int(runner_up['modal_price'])} hai, "
                f"jahan aapko kul ₹{int(runner_up['net_in_hand'])} milenge. "
                f"Lekin agar aap {best['mandi_name']} Mandi jaate hain, toh rate ₹{int(best['modal_price'])} chal raha hai. "
                f"Gaadi ka kharcha kaatne ke baad bhi {best['mandi_name']} me aapko ₹{diff_profit} ka seedha munafa zyada hoga! "
                f"Isliye aaj {best['mandi_name']} Mandi jaana hi sabse faydemand hai."
            )
        else:
            return (
                f"Kisan bhai, {best['mandi_name']} me rate ₹{int(best['modal_price'])} aur {runner_up['mandi_name']} me ₹{int(runner_up['modal_price'])} hai. "
                f"Dono mandiyon ke kharche kaatne ke baad lagbhag barabar hi munafa hai, "
                f"isliye jo mandi aapke ghar ke zyada paas ho, wahan jaana behtar rahega."
            )

    def generate_whatsapp_slip(
        self,
        farmer_name: str,
        location: str,
        commodity: str,
        quantity_quintals: float,
        evaluated: List[Dict[str, Any]],
        transport_mode: str = "Own Vehicle"
    ) -> Dict[str, Any]:
        """
        Generate production WhatsApp / SMS digital Mandi dispatch slip.
        Gives farmer transparent proof of price arbitrage, deductions & statutory rights.
        """
        if not evaluated:
            return {}

        best = evaluated[0]
        runner_up = evaluated[1] if len(evaluated) > 1 else None
        extra_profit = int(best["net_in_hand"] - runner_up["net_in_hand"]) if runner_up else 0

        text = (
            f"*KISAN-VAANI MANDI DISPATCH SLIP*\n"
            f"----------------------------------------\n"
            f"*Farmer:* {farmer_name} | {location}\n"
            f"*Produce:* {commodity.upper()} ({quantity_quintals} Quintal)\n"
            f"*Logistics:* {transport_mode}\n"
            f"----------------------------------------\n"
            f"*RECOMMENDED MANDI:* {best['mandi_name']} ({best['district']})\n"
            f"*Distance:* {best['distance_km']} km\n"
            f"*Mandi Modal Rate:* ₹{int(best['modal_price'])} / Quintal\n"
            f"*Gross Realization:* ₹{int(best['gross_revenue'])}\n\n"
            f"*Itemized Deductions:*\n"
            f"  • Diesel/Freight: -₹{int(best['freight_cost'])}\n"
            f"  • Statutory APMC Cess (1%): -₹{int(best['mandi_cess'])}\n"
            f"  • Handling / Hamali: -₹{int(best['hamali'])}\n"
            f"  • Trader Commission (Aadhatiya): ₹0 (Illegal under eNAM)\n"
            f"----------------------------------------\n"
            f"*NET IN-HAND PROFIT:* ₹{int(best['net_in_hand'])}\n"
            f"*Net Rate / Quintal:* ₹{int(best['net_rate_per_quintal'])}\n"
        )

        if runner_up and extra_profit > 0:
            text += f"*Arbitrage Gain:* +₹{extra_profit} compared to {runner_up['mandi_name']}\n"

        text += (
            f"----------------------------------------\n"
            f"*eNAM Legal Rights Reminder:*\n"
            f"Under APMC Model Act, commission is strictly payable by the buyer. "
            f"Do not allow middleman to deduct 5-8% from your sale proceeds!\n"
            f"Helpline: 1800-270-0224 (eNAM National Portal)\n"
            f"Generated via Gnani.ai Sovereign Voice Intelligence."
        )

        return {
            "mandi_name": best["mandi_name"],
            "district": best["district"],
            "commodity": commodity,
            "quantity_quintals": quantity_quintals,
            "gross_revenue": best["gross_revenue"],
            "net_in_hand": best["net_in_hand"],
            "net_rate_per_quintal": best["net_rate_per_quintal"],
            "total_expenses": best["total_expenses"],
            "extra_profit": extra_profit,
            "whatsapp_text": text
        }

arbitrage_engine = ArbitrageEngine()

