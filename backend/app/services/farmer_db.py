"""
Kisan-Vaani Farmer Memory & Personal Assistant Database
Supports:
1. Supabase Cloud Database (PostgreSQL)
2. Resilient local SQLite fallback
3. 100% Pure, Zero Pre-seeded Data (True Conversational Profile Onboarding)
"""

import sqlite3
import os
import json
import time
from typing import Dict, Any, List, Optional
from app.config import settings

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "farmers_memory.db")

class FarmerDatabase:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.supabase = None
        self._init_db()
        self._init_supabase()

    def _init_supabase(self):
        url = (settings.SUPABASE_URL or "").strip()
        key = (settings.SUPABASE_SECRET_KEY or settings.SUPABASE_PUBLISHABLE_KEY or "").strip()
        if url and key:
            try:
                from supabase import create_client
                self.supabase = create_client(url, key)
                print(f"[FarmerDB] Connected to Supabase at {url}")
            except Exception as e:
                print(f"[FarmerDB] Supabase connection error: {e}. Using local SQLite database.")
                self.supabase = None
        else:
            self.supabase = None

    def _get_connection(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS farmers (
                phone_number TEXT PRIMARY KEY,
                name TEXT,
                village TEXT,
                district TEXT,
                state TEXT,
                acreage REAL DEFAULT 0.0,
                primary_crops TEXT DEFAULT '[]',
                own_transport TEXT,
                created_at INTEGER,
                updated_at INTEGER
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS farmer_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT,
                timestamp INTEGER,
                query_type TEXT,
                commodity TEXT,
                quantity TEXT,
                farmer_utterance TEXT,
                assistant_response TEXT,
                FOREIGN KEY (phone_number) REFERENCES farmers(phone_number)
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS advisory_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT,
                session_id TEXT,
                timestamp INTEGER,
                commodity TEXT,
                best_mandi TEXT,
                net_profit REAL,
                summary_text TEXT,
                whatsapp_sent INTEGER DEFAULT 0,
                FOREIGN KEY (phone_number) REFERENCES farmers(phone_number)
            );
            """)
            conn.commit()

    def clean_phone(self, phone_number: str) -> str:
        cleaned = phone_number.replace("+91", "").replace(" ", "").replace("-", "").strip()
        if len(cleaned) > 10:
            cleaned = cleaned[-10:]
        return cleaned

    def get_farmer(self, phone_number: str) -> Optional[Dict[str, Any]]:
        phone = self.clean_phone(phone_number)
        if not phone:
            return None

        # 1. Try Supabase first if available
        if self.supabase:
            try:
                res = self.supabase.table("farmers").select("*").eq("phone_number", phone).execute()
                if res.data and len(res.data) > 0:
                    farmer = res.data[0]
                    if isinstance(farmer.get("primary_crops"), str):
                        try:
                            farmer["primary_crops"] = json.loads(farmer["primary_crops"])
                        except Exception:
                            farmer["primary_crops"] = [farmer["primary_crops"]]
                    # Sync to local SQLite
                    self._sync_farmer_to_sqlite(farmer)
                    return farmer
            except Exception as e:
                print(f"[FarmerDB:Supabase] get_farmer error: {e}")

        # 2. Local SQLite lookup
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM farmers WHERE phone_number = ? OR phone_number LIKE ?", (phone, f"%{phone}%"))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                try:
                    d["primary_crops"] = json.loads(d["primary_crops"]) if d.get("primary_crops") else []
                except Exception:
                    d["primary_crops"] = []
                return d
        return None

    def _sync_farmer_to_sqlite(self, farmer: Dict[str, Any]):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO farmers (phone_number, name, village, district, state, acreage, primary_crops, own_transport, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    farmer["phone_number"],
                    farmer.get("name", "Kisan Bhai"),
                    farmer.get("village", ""),
                    farmer.get("district", ""),
                    farmer.get("state", ""),
                    float(farmer.get("acreage") or 0.0),
                    json.dumps(farmer.get("primary_crops", [])),
                    farmer.get("own_transport", ""),
                    int(time.time())
                ))
                conn.commit()
        except Exception as e:
            print(f"[FarmerDB:SQLite] sync error: {e}")

    def update_farmer_profile(
        self,
        phone_number: str,
        name: Optional[str] = None,
        village: Optional[str] = None,
        district: Optional[str] = None,
        state: Optional[str] = None,
        acreage: Optional[float] = None,
        primary_crops: Optional[List[str]] = None,
        own_transport: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        phone = self.clean_phone(phone_number)
        existing = self.get_farmer(phone)
        now_ts = int(time.time())

        new_name = name if name else (existing["name"] if existing else "Kisan Bhai")
        new_village = village if village is not None else (existing.get("village", "") if existing else "")
        new_district = district if district is not None else (existing.get("district", "") if existing else "")
        new_state = state if state is not None else (existing.get("state", "") if existing else "")
        new_acreage = acreage if acreage is not None else (existing.get("acreage", 0.0) if existing else 0.0)
        new_crops = primary_crops if primary_crops is not None else (existing.get("primary_crops", []) if existing else [])
        new_transport = own_transport if own_transport is not None else (existing.get("own_transport", "") if existing else "")
        new_lang = language if language is not None else (existing.get("language", "en-US") if existing else "en-US")

        farmer_record = {
            "phone_number": phone,
            "name": new_name,
            "village": new_village,
            "district": new_district,
            "state": new_state,
            "acreage": new_acreage,
            "primary_crops": new_crops,
            "own_transport": new_transport,
            "language": new_lang,
            "updated_at": now_ts
        }

        # 1. Update in Supabase
        if self.supabase:
            try:
                payload = {
                    "phone_number": phone,
                    "name": new_name,
                    "village": new_village,
                    "district": new_district,
                    "state": new_state,
                    "acreage": float(new_acreage or 0.0),
                    "primary_crops": new_crops if isinstance(new_crops, list) else [str(new_crops)],
                    "own_transport": new_transport,
                    "updated_at": now_ts
                }
                res = self.supabase.table("farmers").upsert(payload).execute()
                print(f"[FarmerDB:Supabase] Upserted farmer {phone}: {res.data}")
            except Exception as e:
                print(f"[FarmerDB:Supabase] update_farmer error: {e}")

        # 2. Update in SQLite
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO farmers (phone_number, name, village, district, state, acreage, primary_crops, own_transport, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(phone_number) DO UPDATE SET
                name=excluded.name,
                village=excluded.village,
                district=excluded.district,
                state=excluded.state,
                acreage=excluded.acreage,
                primary_crops=excluded.primary_crops,
                own_transport=excluded.own_transport,
                updated_at=excluded.updated_at
            """, (
                phone,
                new_name,
                new_village,
                new_district,
                new_state,
                new_acreage,
                json.dumps(new_crops),
                new_transport,
                now_ts,
                now_ts
            ))
            conn.commit()

        return farmer_record

    def update_location(self, phone_number: str, village: str, district: Optional[str] = None):
        return self.update_farmer_profile(phone_number, village=village, district=district)

    def get_all_farmers(self) -> List[Dict[str, Any]]:
        # 1. Supabase check
        if self.supabase:
            try:
                res = self.supabase.table("farmers").select("*").order("updated_at", desc=True).execute()
                if res.data:
                    for row in res.data:
                        if isinstance(row.get("primary_crops"), str):
                            try:
                                row["primary_crops"] = json.loads(row["primary_crops"])
                            except Exception:
                                pass
                    return res.data
            except Exception as e:
                print(f"[FarmerDB:Supabase] get_all_farmers error: {e}")

        # 2. SQLite fallback
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM farmers ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                try:
                    d["primary_crops"] = json.loads(d["primary_crops"]) if d.get("primary_crops") else []
                except Exception:
                    d["primary_crops"] = []
                result.append(d)
            return result

    def get_farmer_history(self, phone_number: str) -> List[Dict[str, Any]]:
        phone = self.clean_phone(phone_number)
        if self.supabase:
            try:
                res = self.supabase.table("farmer_queries").select("*").eq("phone_number", phone).order("timestamp", desc=True).limit(8).execute()
                if res.data:
                    return res.data
            except Exception as e:
                print(f"[FarmerDB:Supabase] get_history error: {e}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM farmer_queries 
            WHERE phone_number = ? 
            ORDER BY timestamp DESC LIMIT 8
            """, (phone,))
            return [dict(r) for r in cursor.fetchall()]

    def log_query(
        self,
        phone_number: str,
        query_type: str,
        commodity: Optional[str],
        quantity: Optional[str],
        utterance: str,
        response: str
    ):
        phone = self.clean_phone(phone_number)
        now_ts = int(time.time())

        if self.supabase:
            try:
                self.supabase.table("farmer_queries").insert({
                    "phone_number": phone,
                    "query_type": query_type,
                    "commodity": commodity or "",
                    "quantity": quantity or "",
                    "farmer_utterance": utterance,
                    "assistant_response": response,
                    "timestamp": now_ts
                }).execute()
            except Exception as e:
                print(f"[FarmerDB:Supabase] log_query error: {e}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO farmer_queries (phone_number, timestamp, query_type, commodity, quantity, farmer_utterance, assistant_response)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (phone, now_ts, query_type, commodity, quantity, utterance, response))
            conn.commit()

    def save_advisory_report(
        self,
        phone_number: str,
        session_id: str,
        commodity: str,
        best_mandi: str,
        net_profit: float,
        summary_text: str,
        whatsapp_sent: bool = False
    ):
        phone = self.clean_phone(phone_number)
        now_ts = int(time.time())

        if self.supabase:
            try:
                self.supabase.table("advisory_reports").insert({
                    "phone_number": phone,
                    "session_id": session_id,
                    "commodity": commodity,
                    "best_mandi": best_mandi,
                    "net_profit": net_profit,
                    "summary_text": summary_text,
                    "whatsapp_sent": whatsapp_sent,
                    "timestamp": now_ts
                }).execute()
            except Exception as e:
                print(f"[FarmerDB:Supabase] save_advisory error: {e}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO advisory_reports (phone_number, session_id, timestamp, commodity, best_mandi, net_profit, summary_text, whatsapp_sent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (phone, session_id, now_ts, commodity, best_mandi, net_profit, summary_text, 1 if whatsapp_sent else 0))
            conn.commit()

    def get_personalized_greeting(self, phone_number: str) -> Dict[str, Any]:
        """
        Returns greeting dict:
        - is_new: bool
        - farmer: Optional[Dict]
        - greeting_text: str
        """
        farmer = self.get_farmer(phone_number)
        lang = farmer.get("language", "en-US") if farmer else "en-US"
        name = farmer.get("name") if farmer and farmer.get("name") != "Kisan Bhai" else None

        if "hi" in (lang or "").lower() or "hinglish" in (lang or "").lower():
            salutation = f"Namaste {name} ji" if name else "Namaste Kisan Bhai"
            greeting = f"{salutation}, boliye! Aaj mandi bhav ya fasal me kaise madad kar sakta hoon?"
        elif "pa" in (lang or "").lower():
            salutation = f"Sat Sri Akal {name} ji" if name else "Sat Sri Akal Kisan Veer ji"
            greeting = f"{salutation}, dasso! Aaj mandi de bhaav ya fasal baare ki jaankari chahidi hai?"
        else:
            salutation = f"Hello {name}" if name else "Hello Farmer"
            greeting = f"{salutation}, welcome to Kisan-Vaani! How can I assist you with mandi prices or crop advisory today?"

        return {
            "is_new": not bool(farmer),
            "farmer": farmer,
            "greeting_text": greeting
        }

farmer_db = FarmerDatabase()
