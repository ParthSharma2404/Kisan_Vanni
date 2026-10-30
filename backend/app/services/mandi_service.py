import json
import math
import os
import re
import time
import asyncio
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in kilometers between two GPS coordinates."""
    R = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)

STATE_CENTROIDS = {
    # All 28 States & Major Union Territories
    "maharashtra": (19.7515, 75.7139),
    "punjab": (31.1471, 75.3412),
    "haryana": (29.0588, 76.0856),
    "rajasthan": (27.0238, 74.2179),
    "uttar pradesh": (26.8467, 80.9462),
    "up": (26.8467, 80.9462),
    "madhya pradesh": (22.9734, 78.6569),
    "mp": (22.9734, 78.6569),
    "delhi": (28.7041, 77.1025),
    "gujarat": (22.2587, 71.1924),
    "karnataka": (15.3173, 75.7139),
    "andhra pradesh": (15.9129, 79.7400),
    "telangana": (18.1124, 79.0193),
    "bihar": (25.0961, 85.3131),
    "west bengal": (22.9868, 87.8550),
    "kerala": (10.8505, 76.2711),
    "keralam": (10.8505, 76.2711),
    "tamil nadu": (11.1271, 78.6569),
    "odisha": (20.9517, 85.0985),
    "orissa": (20.9517, 85.0985),
    "himachal pradesh": (31.1048, 77.1734),
    "chhattisgarh": (21.2787, 81.8661),
    "chattisgarh": (21.2787, 81.8661),
    "assam": (26.2006, 92.9376),
    "uttarakhand": (30.0668, 79.0193),
    "jharkhand": (23.6102, 85.2799),
    "jammu and kashmir": (33.7782, 76.5762),
    "jammu & kashmir": (33.7782, 76.5762),
    "tripura": (23.9408, 91.9882),
    "meghalaya": (25.4670, 91.3662),
    "goa": (15.2993, 74.1240)
}

MANDI_COORDINATES = {
    # Maharashtra
    "lasalgaon": (20.1477, 74.2263),
    "pimpalgaon": (20.1706, 73.9877),
    "nashik": (19.9975, 73.7898),
    "yeola": (20.0421, 74.4880),
    "kalwan": (20.4852, 73.9840),
    "sinnar": (19.8456, 74.0012),
    "devala": (20.2100, 74.1800),
    "shrirampur": (19.6200, 74.6500),
    "kopargaon": (19.8833, 74.4833),
    "pune": (18.5204, 73.8567),
    "vashi": (19.0760, 72.9980),
    "solapur": (17.6599, 75.9064),
    "latur": (18.4088, 76.5604),
    "akola": (20.7002, 77.0082),
    "nagpur": (21.1458, 79.0882),
    "ahilyanagar": (19.0948, 74.7480),
    "ahmednagar": (19.0948, 74.7480),
    # North India (Delhi, Punjab, Haryana, Rajasthan, UP)
    "azadpur": (28.7159, 77.1788),
    "delhi": (28.7041, 77.1025),
    "khanna": (30.7027, 76.2206),
    "ludhiana": (30.9010, 75.8573),
    "jalandhar": (31.3260, 75.5762),
    "amritsar": (31.6340, 74.8723),
    "rayya": (31.5414, 75.2312),
    "lalru": (30.4867, 76.8369),
    "mohali": (30.7046, 76.7179),
    "sas nagar": (30.7046, 76.7179),
    "phagwara": (31.2240, 75.7708),
    "kapurthala": (31.3800, 75.3800),
    "patiala": (30.3398, 76.3869),
    "dera bassi": (30.5964, 76.8433),
    "kharar": (30.7441, 76.6466),
    "samrala": (30.8335, 76.1896),
    "batala": (31.8186, 75.2028),
    "dasuya": (31.8156, 75.6583),
    "ahmedgarh": (30.6844, 75.8278),
    "chamkaur sahib": (30.8879, 76.4258),
    "bhagta bhai ka": (30.4439, 75.1219),
    "bathinda": (30.2110, 74.9455),
    "fazilka": (30.4036, 74.0255),
    "gurdaspur": (32.0419, 75.4053),
    "hoshiarpur": (31.5273, 75.9142),
    "sangrur": (30.2458, 75.8421),
    "ropar": (30.9664, 76.5331),
    "rupnagar": (30.9664, 76.5331),
    "karnal": (29.6857, 76.9905),
    "sonipat": (28.9931, 77.0151),
    "ganaur": (29.1314, 77.0194),
    "panipat": (29.3909, 76.9635),
    "hisar": (29.1492, 75.7217),
    "jaipur": (26.9124, 75.7873),
    "muhana": (26.7800, 75.7500),
    "alwar": (27.5530, 76.6346),
    "bharatpur": (27.2152, 77.5030),
    "kota": (25.2138, 75.8648),
    "agra": (27.1767, 78.0081),
    "kanpur": (26.4499, 80.3319),
    "bareilly": (28.3670, 79.4304),
    "varanasi": (25.3176, 82.9739),
    "lucknow": (26.8467, 80.9462),
    "gorakhpur": (26.7606, 83.3732),
    # Central & South India
    "indore": (22.7196, 75.8577),
    "ujjain": (23.1765, 75.7885),
    "mandsaur": (24.0722, 75.0674),
    "neemuch": (24.4744, 74.8703),
    "bhopal": (23.2599, 77.4126),
    "guntur": (16.3067, 80.4365),
    "bengaluru": (12.9716, 77.5946),
    "kolar": (13.1367, 78.1292),
    "palakkad": (10.7867, 76.6548)
}

STATE_LOCATION_KEYWORDS = {
    # Punjab & North India (with typo tolerance e.g. 'pubjab')
    "punjab": "Punjab", "pubjab": "Punjab", "punjaab": "Punjab", "panjab": "Punjab", "पंजाब": "Punjab",
    "khanna": "Punjab", "ludhiana": "Punjab", "jalandhar": "Punjab", "amritsar": "Punjab", "patiala": "Punjab",
    "bathinda": "Punjab", "bhatinda": "Punjab", "fazilka": "Punjab", "gurdaspur": "Punjab", "batala": "Punjab",
    "hoshiarpur": "Punjab", "mohali": "Punjab", "sangrur": "Punjab", "ropar": "Punjab",
    
    # Haryana
    "haryana": "Haryana", "hariyana": "Haryana", "हरियाणा": "Haryana",
    "sonipat": "Haryana", "ganaur": "Haryana", "karnal": "Haryana", "panipat": "Haryana", "hisar": "Haryana",
    "rohtak": "Haryana", "ambala": "Haryana", "gurugram": "Haryana", "gurgaon": "Haryana",

    # Delhi
    "delhi": "Delhi", "azadpur": "Delhi", "dilli": "Delhi", "दिल्ली": "Delhi", "nct": "Delhi",

    # Rajasthan
    "rajasthan": "Rajasthan", "rajsthan": "Rajasthan", "राजस्थान": "Rajasthan",
    "jaipur": "Rajasthan", "muhana": "Rajasthan", "alwar": "Rajasthan", "bharatpur": "Rajasthan",
    "kota": "Rajasthan", "bikaner": "Rajasthan", "jodhpur": "Rajasthan", "sriganganagar": "Rajasthan",

    # Uttar Pradesh
    "uttar pradesh": "Uttar Pradesh", "up": "Uttar Pradesh", "उत्तर प्रदेश": "Uttar Pradesh",
    "agra": "Uttar Pradesh", "kanpur": "Uttar Pradesh", "bareilly": "Uttar Pradesh", "lucknow": "Uttar Pradesh",
    "varanasi": "Uttar Pradesh", "gorakhpur": "Uttar Pradesh", "aligarh": "Uttar Pradesh", "mathura": "Uttar Pradesh",

    # Madhya Pradesh
    "madhya pradesh": "Madhya Pradesh", "mp": "Madhya Pradesh", "मध्य प्रदेश": "Madhya Pradesh",
    "indore": "Madhya Pradesh", "ujjain": "Madhya Pradesh", "mandsaur": "Madhya Pradesh", "neemuch": "Madhya Pradesh",
    "bhopal": "Madhya Pradesh", "jabalpur": "Madhya Pradesh", "gwalior": "Madhya Pradesh", "ratlam": "Madhya Pradesh",

    # Maharashtra
    "maharashtra": "Maharashtra", "maharastra": "Maharashtra", "महाराष्ट्र": "Maharashtra",
    "lasalgaon": "Maharashtra", "pimpalgaon": "Maharashtra", "nashik": "Maharashtra", "yeola": "Maharashtra",
    "kalwan": "Maharashtra", "pune": "Maharashtra", "solapur": "Maharashtra", "latur": "Maharashtra",
    "akola": "Maharashtra", "nagpur": "Maharashtra", "vashi": "Maharashtra", "mumbai": "Maharashtra",
    "ahmednagar": "Maharashtra", "ahilyanagar": "Maharashtra", "shrirampur": "Maharashtra",

    # Gujarat
    "gujarat": "Gujarat", "gujrat": "Gujarat", "गुजरात": "Gujarat",
    "rajkot": "Gujarat", "ahmedabad": "Gujarat", "surat": "Gujarat", "vadodara": "Gujarat", "gondal": "Gujarat",

    # South India
    "andhra pradesh": "Andhra Pradesh", "andhra": "Andhra Pradesh", "guntur": "Andhra Pradesh",
    "telangana": "Telangana", "hyderabad": "Telangana", "warangal": "Telangana",
    "karnataka": "Karnataka", "bengaluru": "Karnataka", "bangalore": "Karnataka", "kolar": "Karnataka",
    "tamil nadu": "Tamil Nadu", "chennai": "Tamil Nadu",
    "kerala": "Kerala", "keralam": "Kerala",

    # East & Central India
    "bihar": "Bihar", "patna": "Bihar",
    "west bengal": "West Bengal", "kolkata": "West Bengal",
    "odisha": "Odisha", "orissa": "Odisha",
    "chhattisgarh": "Chhattisgarh", "chattisgarh": "Chhattisgarh", "raipur": "Chhattisgarh",
    "jharkhand": "Jharkhand", "ranchi": "Jharkhand",
    "himachal pradesh": "Himachal Pradesh", "himachal": "Himachal Pradesh", "shimla": "Himachal Pradesh",
    "uttarakhand": "Uttarakhand", "dehradun": "Uttarakhand"
}

COMMODITY_ALIASES = {
    # Onion
    "onion": "Onion", "pyaaz": "Onion", "kanda": "Onion", "pyaj": "Onion", "कांदा": "Onion", "प्याज": "Onion",
    # Tomato
    "tomato": "Tomato", "tamatar": "Tomato", "tamaatar": "Tomato", "टमाटर": "Tomato",
    # Wheat
    "wheat": "Wheat", "gehu": "Wheat", "gehun": "Wheat", "गेहूं": "Wheat",
    # Potato
    "potato": "Potato", "aloo": "Potato", "alu": "Potato", "आलू": "Potato",
    # Soyabean
    "soyabean": "Soyabean", "soybean": "Soyabean", "soya": "Soyabean", "सोयाबीन": "Soyabean",
    # Mustard
    "mustard": "Mustard", "sarso": "Mustard", "sarson": "Mustard", "सरसों": "Mustard", "rai": "Mustard",
    # Gram / Chana / Chickpea
    "chana": "Bengal Gram(Gram)(Whole)", "gram": "Bengal Gram(Gram)(Whole)", "bengal gram": "Bengal Gram(Gram)(Whole)",
    "chickpea": "Bengal Gram(Gram)(Whole)", "chickpeas": "Bengal Gram(Gram)(Whole)",
    "चना": "Bengal Gram(Gram)(Whole)", "harbara": "Bengal Gram(Gram)(Whole)",
    # Moong / Green Gram / Mung Bean
    "moong": "Green Gram(Moong)(Whole)", "mung": "Green Gram(Moong)(Whole)", "green gram": "Green Gram(Moong)(Whole)",
    "mung bean": "Green Gram(Moong)(Whole)", "moong bean": "Green Gram(Moong)(Whole)", "मूंग": "Green Gram(Moong)(Whole)",
    # Urad / Black Gram
    "urad": "Black Gram(Urd Beans)(Whole)", "udad": "Black Gram(Urd Beans)(Whole)", "black gram": "Black Gram(Urd Beans)(Whole)",
    "black lentil": "Black Gram(Urd Beans)(Whole)", "उड़द": "Black Gram(Urd Beans)(Whole)",
    # Tur / Arhar / Pigeon Pea
    "tur": "Red gram/Arhar/Tur(whole)", "toor": "Red gram/Arhar/Tur(whole)", "arhar": "Red gram/Arhar/Tur(whole)",
    "pigeon pea": "Red gram/Arhar/Tur(whole)", "pigeon peas": "Red gram/Arhar/Tur(whole)", "red gram": "Red gram/Arhar/Tur(whole)",
    "तूर": "Red gram/Arhar/Tur(whole)", "अरहर": "Red gram/Arhar/Tur(whole)",
    # Paddy / Rice
    "paddy": "Paddy(Common)", "dhan": "Paddy(Common)", "धान": "Paddy(Common)", "chawal": "Rice", "rice": "Rice", "चावल": "Rice",
    "basmati": "Paddy(Basmati)",
    # Chilli
    "chilli": "Green Chilli", "mirch": "Green Chilli", "mirchi": "Green Chilli", "मिर्च": "Green Chilli", "green chilli": "Green Chilli",
    "sukhi mirch": "Dry Chillies", "dry chillies": "Dry Chillies",
    # Garlic
    "garlic": "Garlic", "lahsun": "Garlic", "lahsunn": "Garlic", "लहसुन": "Garlic",
    # Maize
    "maize": "Maize", "makka": "Maize", "makai": "Maize", "bhutta": "Maize", "corn": "Maize", "मक्का": "Maize",
    # Bajra
    "bajra": "Bajra(Pearl Millet/Cumbu)", "bajri": "Bajra(Pearl Millet/Cumbu)", "pearl millet": "Bajra(Pearl Millet/Cumbu)", "बाजरा": "Bajra(Pearl Millet/Cumbu)",
    # Jowar
    "jowar": "Jowar(Sorghum)", "jwari": "Jowar(Sorghum)", "sorghum": "Jowar(Sorghum)", "ज्वार": "Jowar(Sorghum)",
    # Cotton
    "cotton": "Cotton", "kapas": "Cotton", "rui": "Cotton", "कपास": "Cotton",
    # Groundnut
    "groundnut": "Groundnut", "mungfali": "Groundnut", "moongfali": "Groundnut", "peanut": "Groundnut", "shengdana": "Groundnut", "मूंगफली": "Groundnut",
    # Cumin / Jeera
    "jeera": "Cummin Seed(Jeera)", "zeera": "Cummin Seed(Jeera)", "cumin": "Cummin Seed(Jeera)", "जीरा": "Cummin Seed(Jeera)",
    # Coriander / Dhaniya
    "dhaniya": "Coriander(Leaves)", "coriander": "Coriander(Leaves)", "धनिया": "Coriander(Leaves)",
    # Ginger / Adrak
    "adrak": "Ginger(Green)", "ginger": "Ginger(Green)", "अदरक": "Ginger(Green)",
    # Bhindi / Okra
    "bhindi": "Bhindi(Ladies Finger)", "okra": "Bhindi(Ladies Finger)", "ladies finger": "Bhindi(Ladies Finger)", "भिंडी": "Bhindi(Ladies Finger)",
    # Cucumber / Kheera
    "kheera": "Cucumbar(Kheera)", "cucumber": "Cucumbar(Kheera)", "kakdi": "Cucumbar(Kheera)", "खीरा": "Cucumbar(Kheera)"
}

class MandiService:
    CACHE_TTL_SECONDS: float = 6 * 3600  # 6 Hours expiration (covers daily morning/evening market arrivals)

    def __init__(self):
        self.sample_data_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "mandi_rates_sample.json"
        )
        self._local_cache: List[Dict[str, Any]] = []
        self._live_gov_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_timestamp: Dict[str, float] = {}
        self._load_local_data()

    def _load_local_data(self):
        try:
            with open(self.sample_data_path, "r", encoding="utf-8") as f:
                self._local_cache = json.load(f)
                print(f"[MandiService] Loaded {len(self._local_cache)} Agmarknet benchmark records from local database.")
        except Exception as e:
            print(f"[MandiService] Warning: Could not load local mandi cache: {e}")
            self._local_cache = []

    async def fetch_rates_from_gov_api(
        self,
        state: Optional[str] = None,
        commodity: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Fetch real-time commodity pricing records from data.gov.in.
        """
        api_key = settings.DATA_GOV_API_KEY or os.getenv("DATA_GOV_API_KEY", "")
        if not api_key:
            return []

        canonical_comm = None
        if commodity:
            c_clean = commodity.strip().lower()
            canonical_comm = COMMODITY_ALIASES.get(c_clean, commodity.capitalize())

        url = "https://api.data.gov.in/resource/" + settings.MANDI_RESOURCE_ID
        params = {
            "api-key": api_key,
            "format": "json",
            "limit": limit
        }
        if state:
            params["filters[state]"] = state
        if canonical_comm:
            params["filters[commodity]"] = canonical_comm

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=12.0, headers=headers, verify=False) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    records = data.get("records", [])
                    print(f"[MandiService:Live] Retrieved {len(records)} live records from data.gov.in for {canonical_comm or state}")
                    lookup_name = canonical_comm or (commodity or "all")
                    cache_key = f"{lookup_name.lower()}_{state.lower() if state else 'all'}"
                    now_ts = time.time()
                    self._live_gov_cache[cache_key] = records
                    self._cache_timestamp[cache_key] = now_ts
                    self._live_gov_cache[lookup_name.lower()] = records
                    self._cache_timestamp[lookup_name.lower()] = now_ts
                    if commodity:
                        self._live_gov_cache[commodity.lower()] = records
                        self._cache_timestamp[commodity.lower()] = now_ts
                    return records
                elif res.status_code == 429:
                    print(f"[MandiService:Live] Rate limit reached (HTTP 429). Using existing cache and benchmarks.")
        except Exception as err:
            print(f"[MandiService:Live] API notice: {err}")
        return []

    def _resolve_coordinates(self, market_name: str, district: str, state: str = "") -> tuple[float, float]:
        """Resolves accurate GPS coordinates for Indian mandis, prioritizing specific market over district."""
        m_lower = market_name.lower()
        d_lower = district.lower()
        s_lower = state.lower()

        # 1. Exact or partial market match FIRST (e.g. 'rayya' before 'amritsar')
        for k, coords in MANDI_COORDINATES.items():
            if k in m_lower:
                return coords

        # 2. District match fallback
        for k, coords in MANDI_COORDINATES.items():
            if k in d_lower:
                return coords

        # 3. State centroid fallback
        for st_key, coords in STATE_CENTROIDS.items():
            if st_key in s_lower or st_key in d_lower:
                return coords

        # 3. Unresolved fallback (flag with zeros so distance can be marked safely)
        return (0.0, 0.0)

    def get_rates_for_commodity(
        self,
        commodity: str,
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
        location_hint: Optional[str] = None,
        radius_km: float = 150.0
    ) -> List[Dict[str, Any]]:
        """
        Location-aware mandi rate retriever.
        Combines live data.gov.in cache, on-demand government feed, and Agmarknet benchmark records.
        Prioritizes the exact state / mandi / district the farmer is inquiring about.
        Zero hardcoded assumptions (no automatic fallback to Nashik).
        """
        norm_comm = commodity.strip().lower()
        canonical_comm = COMMODITY_ALIASES.get(norm_comm, commodity.strip().capitalize())

        # Detect target state and target location from hint
        target_state = None
        hint_clean = (location_hint or "").lower().strip()
        if hint_clean:
            for kw, st_name in STATE_LOCATION_KEYWORDS.items():
                if kw in hint_clean:
                    target_state = st_name
                    break

        # Dynamically center coordinates around target state if user_lat is not explicitly provided
        if target_state and (user_lat is None or user_lon is None):
            st_coords = STATE_CENTROIDS.get(target_state.lower())
            if st_coords:
                user_lat, user_lon = st_coords
        elif user_lat is None or user_lon is None:
            # Neutral national center of India (Madhya Pradesh centroid)
            user_lat, user_lon = (22.9734, 78.6569)

        # Check live cache with 6-Hour freshness TTL
        live_records = []
        now_ts = time.time()
        if target_state:
            cache_key = f"{canonical_comm.lower()}_{target_state.lower()}"
            cached_ts = self._cache_timestamp.get(cache_key, 0)
            if (now_ts - cached_ts) < self.CACHE_TTL_SECONDS:
                live_records = self._live_gov_cache.get(cache_key, [])
        else:
            cache_key = canonical_comm.lower()
            cached_ts = self._cache_timestamp.get(cache_key, 0)
            if (now_ts - cached_ts) < self.CACHE_TTL_SECONDS:
                live_records = self._live_gov_cache.get(canonical_comm.lower(), [])
                if not live_records:
                    live_records = self._live_gov_cache.get(norm_comm, [])

        # Synchronous fast-fetch with 6-second timeout if not in memory or expired
        if not live_records and settings.DATA_GOV_API_KEY:
            try:
                import urllib.request
                import urllib.parse
                filter_param = f"&filters%5Bcommodity%5D={urllib.parse.quote(canonical_comm)}"
                if target_state:
                    filter_param += f"&filters%5Bstate%5D={urllib.parse.quote(target_state)}"
                url = f"https://api.data.gov.in/resource/{settings.MANDI_RESOURCE_ID}?api-key={settings.DATA_GOV_API_KEY}&format=json&limit=50{filter_param}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=6.0) as resp:
                    if resp.status == 200:
                        gov_data = json.loads(resp.read().decode('utf-8'))
                        live_records = gov_data.get("records", [])
                        fetch_ts = time.time()
                        if target_state:
                            self._live_gov_cache[f"{canonical_comm.lower()}_{target_state.lower()}"] = live_records
                            self._cache_timestamp[f"{canonical_comm.lower()}_{target_state.lower()}"] = fetch_ts
                        else:
                            self._live_gov_cache[canonical_comm.lower()] = live_records
                            self._cache_timestamp[canonical_comm.lower()] = fetch_ts
                            self._live_gov_cache[norm_comm] = live_records
                            self._cache_timestamp[norm_comm] = fetch_ts
                        print(f"[MandiService:Live] Live on-demand fetched {len(live_records)} records for {canonical_comm} (state={target_state or 'all'})")
            except Exception as e:
                print(f"[MandiService] Live on-demand fetch notice: {e}")

        matched_results = []
        other_results = []
        seen_markets = set()

        # 1. Process Live data.gov.in Records
        for rec in live_records:
            try:
                m_name = rec.get("market", "").strip()
                dist_name = rec.get("district", "").strip()
                st_name = rec.get("state", "").strip()
                modal = int(float(rec.get("modal_price", 0)))
                min_p = int(float(rec.get("min_price", modal * 0.88)))
                max_p = int(float(rec.get("max_price", modal * 1.12)))
                arr_date = rec.get("arrival_date", "29/10/2026")

                m_lat, m_lon = self._resolve_coordinates(m_name, dist_name, st_name)
                if m_lat != 0.0 or m_lon != 0.0:
                    dist = haversine_distance(user_lat, user_lon, m_lat, m_lon)
                else:
                    dist = 999.0

                entry = {
                    "state": st_name,
                    "district": dist_name,
                    "market": m_name,
                    "commodity": canonical_comm,
                    "variety": rec.get("variety", "Standard"),
                    "arrival_date": arr_date,
                    "min_price": min_p,
                    "max_price": max_p,
                    "modal_price": modal,
                    "lat": m_lat if m_lat != 0.0 else user_lat,
                    "lon": m_lon if m_lon != 0.0 else user_lon,
                    "apmc_cess_pct": 1.0,
                    "enam_active": True,
                    "distance_km": dist,
                    "data_source": "data.gov.in (Agmarknet Live)"
                }

                # Location relevance matching
                is_exact_match = False
                if hint_clean:
                    if (target_state and st_name.lower() == target_state.lower()) or (hint_clean in m_name.lower() or hint_clean in dist_name.lower() or hint_clean in st_name.lower()):
                        is_exact_match = True

                key = f"{m_name}_{dist_name}".lower()
                if key not in seen_markets:
                    seen_markets.add(key)
                    if is_exact_match:
                        matched_results.append(entry)
                    else:
                        other_results.append(entry)
            except Exception:
                continue

        # 2. Process Agmarknet Benchmark Database Records
        # If target_state was explicitly requested, DO NOT leak records from unrelated states (e.g. Nashik)
        norm_targets = {norm_comm, canonical_comm.lower(), canonical_comm.split('(')[0].strip().lower()}
        for item in self._local_cache:
            item_comm = item.get("commodity", "").lower()
            item_state = item.get("state", "")
            if target_state and item_state.lower() != target_state.lower():
                continue

            if item_comm in norm_targets or any(t in item_comm for t in norm_targets if len(t) > 3):
                m_name = item.get("market", "")
                dist_name = item.get("district", "")
                st_name = item.get("state", "")
                key = f"{m_name}_{dist_name}".lower()

                m_lat = item.get("lat") or user_lat
                m_lon = item.get("lon") or user_lon
                dist = haversine_distance(user_lat, user_lon, m_lat, m_lon)
                entry = dict(item)
                entry["distance_km"] = dist

                is_exact_match = False
                if hint_clean:
                    if (target_state and st_name.lower() == target_state.lower()) or (hint_clean in m_name.lower() or hint_clean in dist_name.lower() or hint_clean in st_name.lower()):
                        is_exact_match = True

                if key not in seen_markets:
                    seen_markets.add(key)
                    if is_exact_match:
                        matched_results.append(entry)
                    else:
                        other_results.append(entry)

        # Combine results: Target location mandis first, followed by nearby mandis sorted by distance
        matched_results.sort(key=lambda x: x.get("modal_price", 0), reverse=True)
        other_results.sort(key=lambda x: x.get("distance_km", 9999))

        final_rates = matched_results + other_results
        return final_rates[:8]

mandi_service = MandiService()
