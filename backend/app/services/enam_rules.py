import json
import os
from typing import List, Dict, Any, Optional

class ENAMAdvisor:
    def __init__(self):
        self.rules_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "enam_rules.json"
        )
        self.rules: List[Dict[str, Any]] = []
        self._load_rules()

    def _load_rules(self):
        try:
            with open(self.rules_path, "r", encoding="utf-8") as f:
                self.rules = json.load(f)
        except Exception as e:
            print(f"[ENAMAdvisor] Error loading rules: {e}")
            self.rules = []

    def get_commission_rule_advice(self) -> str:
        for r in self.rules:
            if r.get("category") == "commission_fees":
                return r["spoken_summary_hi"]
        return "eNAM niyam ke mutabik kisan se koi commission nahi kaata ja sakta."

    def get_advice_for_query(self, user_query: str) -> Optional[str]:
        q = user_query.lower()
        if any(w in q for w in ["commission", "aadhat", "arhatiya", "dalali", "dalal", "katoti", "katauti"]):
            return (
                "Kisan bhai, zaroori baat yaad rakhein: eNAM aur APMC niyam ke tehat, "
                "kisan ke paise se koi aadhat ya commission nahi kat sakta. "
                "Commission hamesha khareedne wala vyapari deta hai. Agar koi zabardasti kaate, "
                "toh Mandi Sachiv karyalaya me turant shikayat karein."
            )
        if any(w in q for w in ["tol", "kanta", "tulai", "wajan", "vajan"]):
            return (
                "Kisan bhai, tulai hamesha computerized electronic kanta par hi karayein. "
                "Computer wali kanta parchi zaroor lein. Haath wali taraju ya andaze se tulai manna kanoonan galat hai."
            )
        if any(w in q for w in ["quality", "check", "lab", "assaying", "kharab"]):
            return (
                "Mandi me eNAM ki sarkari quality lab hoti hai jahan muft me nami aur dana test hota hai. "
                "Vyapari ke andaze par na jayein, pehle lab se quality parchi lein taaki poora daam mile."
            )
        return None

enam_advisor = ENAMAdvisor()
