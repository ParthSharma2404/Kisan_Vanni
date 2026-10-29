import json
import math
import os
import re
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
    "tamil nadu": (11.1271, 78.6569)
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
    "lasalgaon": "Maharashtra",
    "pimpalgaon": "Maharashtra",
    "nashik": "Maharashtra",
    "yeola": "Maharashtra",
    "kalwan": "Maharashtra",
    "pune": "Maharashtra",
    "solapur": "Maharashtra",
    "latur": "Maharashtra",
    "maharashtra": "Maharashtra",
    "delhi": "Delhi",
    "azadpur": "Delhi",
    "punjab": "Punjab",
    "khanna": "Punjab",
    "ludhiana": "Punjab",
    "jalandhar": "Punjab",
    "haryana": "Haryana",
    "sonipat": "Haryana",
    "ganaur": "Haryana",
    "karnal": "Haryana",
    "panipat": "Haryana",
    "rajasthan": "Rajasthan",
    "jaipur": "Rajasthan",
    "alwar": "Rajasthan",
    "bharatpur": "Rajasthan",
    "kota": "Rajasthan",
    "uttar pradesh": "Uttar Pradesh",
    "up": "Uttar Pradesh",
    "agra": "Uttar Pradesh",
    "kanpur": "Uttar Pradesh",
    "bareilly": "Uttar Pradesh",
    "madhya pradesh": "Madhya Pradesh",
    "mp": "Madhya Pradesh",
    "indore": "Madhya Pradesh",
    "ujjain": "Madhya Pradesh",
    "mandsaur": "Madhya Pradesh",
    "guntur": "Andhra Pradesh",
    "karnataka": "Karnataka"
}

class MandiService:
    def __init__(self):
        self.sample_data_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "mandi_rates_sample.json"
        )
        self._local_cache: List[Dict[str, Any]] = []
        self._live_gov_cache: Dict[str, List[Dict[str, Any]]] = {}
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

        url = "https://api.data.gov.in/resource/" + settings.MANDI_RESOURCE_ID
        params = {
            "api-key": api_key,
            "format": "json",
            "limit": limit
        }
        if state:
            params["filters[state]"] = state
        if commodity:
            params["filters[commodity]"] = commodity.capitalize()

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
                    print(f"[MandiService:Live] Retrieved {len(records)} live records from data.gov.in for {commodity or state}")
                    cache_key = f"{commodity.lower() if commodity else 'all'}_{state.lower() if state else 'all'}"
                    self._live_gov_cache[cache_key] = records
                    if commodity:
                        self._live_gov_cache[commodity.lower()] = records
                    return records
        except Exception as err:
            print(f"[MandiService:Live] API notice: {err}")
        return []

    def _resolve_coordinates(self, market_name: str, district: str, state: str = "") -> tuple[float, float]:
        """Resolves accurate GPS coordinates for Indian mandis, falling back to state centroids."""
        m_lower = market_name.lower()
        d_lower = district.lower()
        s_lower = state.lower()

        # 1. Exact or partial market match
        for k, coords in MANDI_COORDINATES.items():
            if k in m_lower or k in d_lower:
                return coords

        # 2. State centroid fallback
        for st_key, coords in STATE_CENTROIDS.items():
            if st_key in s_lower or st_key in d_lower:
                return coords

        # 3. Default to Nashik centroid
        return (20.0800, 74.1100)

    def get_rates_for_commodity(
        self,
        commodity: str,
        user_lat: float = 20.0800,
        user_lon: float = 74.1100,
        location_hint: Optional[str] = None,
        radius_km: float = 150.0
    ) -> List[Dict[str, Any]]:
        """
        Location-aware mandi rate retriever.
        Combines live data.gov.in cache, on-demand government feed, and Agmarknet benchmark records.
        Prioritizes the exact mandi / district the farmer is inquiring about.
        """
        norm_comm = commodity.strip().lower()
        alias_map = {
            "pyaaz": "onion", "kanda": "onion", "pyaj": "onion", "कांदा": "onion", "प्याज": "onion",
            "tamatar": "tomato", "tamaatar": "tomato", "टमाटर": "tomato",
            "gehu": "wheat", "gehun": "wheat", "गेहूं": "wheat",
            "soya": "soyabean", "soybean": "soyabean", "सोयाबीन": "soyabean",
            "aloo": "potato", "alu": "potato", "आलू": "potato",
            "sarso": "mustard", "sarson": "mustard", "सरसों": "mustard",
            "mirch": "chilli", "mirchi": "chilli", "मिर्च": "chilli",
            "lahsun": "garlic", "garlic": "garlic", "लहसुन": "garlic"
        }
        search_comm = alias_map.get(norm_comm, norm_comm)

        # Detect target state and target location from hint
        target_state = None
        hint_clean = (location_hint or "").lower().strip()
        if hint_clean:
            for kw, st_name in STATE_LOCATION_KEYWORDS.items():
                if kw in hint_clean:
                    target_state = st_name
                    break

        # Check live cache
        live_records = []
        if target_state:
            live_records = self._live_gov_cache.get(f"{search_comm}_{target_state.lower()}", [])
        if not live_records:
            live_records = self._live_gov_cache.get(search_comm, [])

        # Synchronous fast-fetch with 4-second timeout if not in memory
        if not live_records and settings.DATA_GOV_API_KEY:
            try:
                import urllib.request
                import urllib.parse
                filter_param = f"&filters%5Bcommodity%5D={search_comm.capitalize()}"
                if target_state:
                    filter_param += f"&filters%5Bstate%5D={urllib.parse.quote(target_state)}"
                url = f"https://api.data.gov.in/resource/{settings.MANDI_RESOURCE_ID}?api-key={settings.DATA_GOV_API_KEY}&format=json&limit=50{filter_param}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=4.0) as resp:
                    if resp.status == 200:
                        gov_data = json.loads(resp.read())
                        live_records = gov_data.get("records", [])
                        if target_state:
                            self._live_gov_cache[f"{search_comm}_{target_state.lower()}"] = live_records
                        self._live_gov_cache[search_comm] = live_records
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
                dist = haversine_distance(user_lat, user_lon, m_lat, m_lon)

                entry = {
                    "state": st_name,
                    "district": dist_name,
                    "market": m_name,
                    "commodity": search_comm.capitalize(),
                    "variety": rec.get("variety", "Standard"),
                    "arrival_date": arr_date,
                    "min_price": min_p,
                    "max_price": max_p,
                    "modal_price": modal,
                    "lat": m_lat,
                    "lon": m_lon,
                    "apmc_cess_pct": 1.0,
                    "enam_active": True,
                    "distance_km": dist,
                    "data_source": "data.gov.in (Agmarknet Live)"
                }

                # Location relevance matching
                is_exact_match = False
                if hint_clean:
                    if hint_clean in m_name.lower() or hint_clean in dist_name.lower() or hint_clean in st_name.lower():
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
        for item in self._local_cache:
            if item.get("commodity", "").lower() == search_comm:
                m_name = item.get("market", "")
                dist_name = item.get("district", "")
                st_name = item.get("state", "")
                key = f"{m_name}_{dist_name}".lower()

                m_lat = item.get("lat", 20.0800)
                m_lon = item.get("lon", 74.1100)
                dist = haversine_distance(user_lat, user_lon, m_lat, m_lon)
                entry = dict(item)
                entry["distance_km"] = dist

                is_exact_match = False
                if hint_clean:
                    if hint_clean in m_name.lower() or hint_clean in dist_name.lower() or hint_clean in st_name.lower():
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
