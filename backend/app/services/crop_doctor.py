import json
import os
from typing import List, Dict, Any, Optional

class CropDoctor:
    def __init__(self):
        self.kb_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "crop_diseases.json"
        )
        self.diseases: List[Dict[str, Any]] = []
        self._load_kb()

    def _load_kb(self):
        try:
            with open(self.kb_path, "r", encoding="utf-8") as f:
                self.diseases = json.load(f)
        except Exception as e:
            print(f"[CropDoctor] Error loading diseases KB: {e}")
            self.diseases = []

    def diagnose(self, spoken_text: str) -> Optional[Dict[str, Any]]:
        text = spoken_text.lower()
        
        # Check matched crop
        matched_disease = None
        for entry in self.diseases:
            crop_match = any(alias in text for alias in entry.get("aliases", []))
            if crop_match:
                # Check symptom matches
                for symptom in entry.get("symptoms", []):
                    # Check individual words or phrase
                    s_words = symptom.split()
                    if all(w in text for w in s_words) or symptom in text:
                        matched_disease = entry
                        break
            if matched_disease:
                break
                
        return matched_disease

crop_doctor = CropDoctor()
