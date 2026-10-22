"""
Kisan-Vaani Sovereign Agri-Intelligence Engine
Comprehensive, Open-Ended Agricultural Conversational Intelligence for Indian Farmers.
Handles:
1. Any Mandi Commodity Rate & Arbitrage (50+ Indian Crops across APMCs)
2. ICAR Crop Doctor & Pest/Disease Diagnostic Guidance (Chemical & Organic Remedies)
3. Soil Health, Fertilizers (Urea, DAP, NPK, Micro-nutrients) & Sowing Advisory
4. Government Schemes & Subsidies (PM-Kisan, KCC, PMFBY, PM-Kusum, Soil Health Card)
5. eNAM Statutory Mandi Rights & Legal Commission Auditing (0% Farmer Commission)
6. Weather, Irrigation, Storage & Post-Harvest Advisory
7. Fluid Natural Indic Conversational Chit-chat in Empathetic Hindi/Hinglish
"""

import re
from typing import Dict, Any, Optional, Tuple, List
from app.services.mandi_service import mandi_service, haversine_distance
from app.services.enam_rules import enam_advisor
from app.services.agri_rag import agri_rag

# Comprehensive Indian State & Major Agricultural District Geolocation Mapping
STATE_DISTRICT_MAP = {
    # Punjab
    "punjab": ("punjab", "Punjab"), "पंजाब": ("punjab", "Punjab"),
    "ludhiana": ("punjab", "Ludhiana"), "लुधियाना": ("punjab", "Ludhiana"),
    "jalandhar": ("punjab", "Jalandhar"), "जालंधर": ("punjab", "Jalandhar"),
    "amritsar": ("punjab", "Amritsar"), "अमृतसर": ("punjab", "Amritsar"),
    "bathinda": ("punjab", "Bathinda"), "बठिंडा": ("punjab", "Bathinda"),
    "khanna": ("punjab", "Khanna"), "खन्ना": ("punjab", "Khanna"),
    "patiala": ("punjab", "Patiala"), "पटियाला": ("punjab", "Patiala"),
    "sangrur": ("punjab", "Sangrur"), "संगरूर": ("punjab", "Sangrur"),
    "moga": ("punjab", "Moga"), "मोगा": ("punjab", "Moga"),
    
    # Haryana
    "haryana": ("haryana", "Haryana"), "हरियाणा": ("haryana", "Haryana"),
    "karnal": ("haryana", "Karnal"), "करनाल": ("haryana", "Karnal"),
    "hisar": ("haryana", "Hisar"), "हिसार": ("haryana", "Hisar"),
    "sirsa": ("haryana", "Sirsa"), "सिरसा": ("haryana", "Sirsa"),
    "ambala": ("haryana", "Ambala"), "अंबाला": ("haryana", "Ambala"),
    "panipat": ("haryana", "Panipat"), "पानीपत": ("haryana", "Panipat"),
    "rohtak": ("haryana", "Rohtak"), "रोहतक": ("haryana", "Rohtak"),
    "sonipat": ("haryana", "Sonipat"), "सोनीपत": ("haryana", "Sonipat"),

    # Uttar Pradesh
    "up": ("up", "Uttar Pradesh"), "uttar pradesh": ("up", "Uttar Pradesh"), "उत्तर प्रदेश": ("up", "Uttar Pradesh"), "यूपी": ("up", "Uttar Pradesh"),
    "agra": ("up", "Agra"), "आगरा": ("up", "Agra"),
    "kanpur": ("up", "Kanpur"), "कानपुर": ("up", "Kanpur"),
    "meerut": ("up", "Meerut"), "मेरठ": ("up", "Meerut"),
    "farrukhabad": ("up", "Farrukhabad"), "फर्रुखाबाद": ("up", "Farrukhabad"),
    "varanasi": ("up", "Varanasi"), "वाराणसी": ("up", "Varanasi"),
    "aligarh": ("up", "Aligarh"), "अलीगढ़": ("up", "Aligarh"),
    "bareilly": ("up", "Bareilly"), "बरेली": ("up", "Bareilly"),
    "lucknow": ("up", "Lucknow"), "लखनऊ": ("up", "Lucknow"),
    "barabanki": ("up", "Barabanki"), "बाराबंकी": ("up", "Barabanki"),
    "gorakhpur": ("up", "Gorakhpur"), "गोरखपुर": ("up", "Gorakhpur"),

    # Madhya Pradesh
    "mp": ("mp", "Madhya Pradesh"), "madhya pradesh": ("mp", "Madhya Pradesh"), "मध्य प्रदेश": ("mp", "Madhya Pradesh"), "एमपी": ("mp", "Madhya Pradesh"),
    "indore": ("mp", "Indore"), "इंदौर": ("mp", "Indore"),
    "ujjain": ("mp", "Ujjain"), "उज्जैन": ("mp", "Ujjain"),
    "bhopal": ("mp", "Bhopal"), "भोपाल": ("mp", "Bhopal"),
    "neemuch": ("mp", "Neemuch"), "नीमच": ("mp", "Neemuch"),
    "mandsaur": ("mp", "Mandsaur"), "मंदसौर": ("mp", "Mandsaur"),
    "dewas": ("mp", "Dewas"), "देवास": ("mp", "Dewas"),
    "jabalpur": ("mp", "Jabalpur"), "जबलपुर": ("mp", "Jabalpur"),
    "sehore": ("mp", "Sehore"), "सीहोर": ("mp", "Sehore"),
    "vidisha": ("mp", "Vidisha"), "विदिशा": ("mp", "Vidisha"),

    # Rajasthan
    "rajasthan": ("rajasthan", "Rajasthan"), "राजस्थान": ("rajasthan", "Rajasthan"),
    "jaipur": ("rajasthan", "Jaipur"), "जयपुर": ("rajasthan", "Jaipur"),
    "kota": ("rajasthan", "Kota"), "कोटा": ("rajasthan", "Kota"),
    "bikaner": ("rajasthan", "Bikaner"), "बीकानेर": ("rajasthan", "Bikaner"),
    "jodhpur": ("rajasthan", "Jodhpur"), "जोधपुर": ("rajasthan", "Jodhpur"),
    "ganganagar": ("rajasthan", "Sri Ganganagar"), "गंगानगर": ("rajasthan", "Sri Ganganagar"),
    "alwar": ("rajasthan", "Alwar"), "अलवर": ("rajasthan", "Alwar"),
    "merta": ("rajasthan", "Merta City"), "मेड़ता": ("rajasthan", "Merta City"),
    "bharatpur": ("rajasthan", "Bharatpur"), "भरतपुर": ("rajasthan", "Bharatpur"),

    # Maharashtra
    "maharashtra": ("maharashtra", "Maharashtra"), "महाराष्ट्र": ("maharashtra", "Maharashtra"),
    "nashik": ("maharashtra", "Nashik"), "नासिक": ("maharashtra", "Nashik"),
    "pimpalgaon": ("maharashtra", "Pimpalgaon"), "पिंपलगांव": ("maharashtra", "Pimpalgaon"),
    "lasalgaon": ("maharashtra", "Lasalgaon"), "लासलगांव": ("maharashtra", "Lasalgaon"),
    "pune": ("maharashtra", "Pune"), "पुणे": ("maharashtra", "Pune"),
    "nagpur": ("maharashtra", "Nagpur"), "नागपुर": ("maharashtra", "Nagpur"),
    "solapur": ("maharashtra", "Solapur"), "सोलापुर": ("maharashtra", "Solapur"),
    "latur": ("maharashtra", "Latur"), "लातूर": ("maharashtra", "Latur"),
    "yeola": ("maharashtra", "Yeola"), "येवला": ("maharashtra", "Yeola"),
    "vashi": ("maharashtra", "Vashi"), "वाशी": ("maharashtra", "Vashi"),
    "jalgaon": ("maharashtra", "Jalgaon"), "जलगांव": ("maharashtra", "Jalgaon"),
    "ahmednagar": ("maharashtra", "Ahmednagar"), "अहमदनगर": ("maharashtra", "Ahmednagar"),

    # Gujarat
    "gujarat": ("gujarat", "Gujarat"), "गुजरात": ("gujarat", "Gujarat"),
    "rajkot": ("gujarat", "Rajkot"), "राजकोट": ("gujarat", "Rajkot"),
    "gondal": ("gujarat", "Gondal"), "गोंडल": ("gujarat", "Gondal"),
    "surat": ("gujarat", "Surat"), "सूरत": ("gujarat", "Surat"),
    "ahmedabad": ("gujarat", "Ahmedabad"), "अहमदाबाद": ("gujarat", "Ahmedabad"),
    "unjha": ("gujarat", "Unjha"), "ऊंझा": ("gujarat", "Unjha"),
    "mahuva": ("gujarat", "Mahuva"), "महुवा": ("gujarat", "Mahuva"),

    # Karnataka
    "karnataka": ("karnataka", "Karnataka"), "कर्नाटक": ("karnataka", "Karnataka"),
    "bangalore": ("karnataka", "Bangalore"), "bengaluru": ("karnataka", "Bangalore"), "बेंगलुरु": ("karnataka", "Bangalore"),
    "kolar": ("karnataka", "Kolar"), "कोलार": ("karnataka", "Kolar"),
    "hubli": ("karnataka", "Hubli"), "हुबली": ("karnataka", "Hubli"),
    "belgaum": ("karnataka", "Belagavi"), "बेलगाम": ("karnataka", "Belagavi"),

    # Bihar
    "bihar": ("bihar", "Bihar"), "बिहार": ("bihar", "Bihar"),
    "patna": ("bihar", "Patna"), "पटना": ("bihar", "Patna"),
    "muzaffarpur": ("bihar", "Muzaffarpur"), "मुजफ्फरपुर": ("bihar", "Muzaffarpur"),
    "gulabbagh": ("bihar", "Gulabbagh"), "गुलाबबाग": ("bihar", "Gulabbagh"),

    # Delhi / NCR
    "delhi": ("delhi", "Delhi"), "दिल्ली": ("delhi", "Delhi"),
    "azadpur": ("delhi", "Azadpur"), "आजादपुर": ("delhi", "Azadpur")
}

# Benchmark Mandi Rates & MSP for Indian Agricultural Commodities (Per Quintal)
# Contains state-specific APMC mandis, pricing, and advisory
COMMODITY_DATABASE = {
    # Vegetables
    "onion": {
        "names": ["onion", "pyaaz", "kanda", "pyaj", "kande", "प्याज", "प्याज़", "कांदा", "कांदे", "कंदा"],
        "hindi": "Pyaaz",
        "benchmark_price": 2450,
        "min_price": 1900,
        "max_price": 2750,
        "top_mandis": ["Lasalgaon (Nashik)", "Pimpalgaon (Nashik)", "Yeola", "Azadpur (Delhi)"],
        "advisory": "Wholesale arrivals regular hain aur good quality dry onion par tagda bhav mil raha hai.",
        "regional_mandis": {
            "punjab": {"mandis": "Ludhiana aur Khanna", "price": 2600, "range": "₹2,300 se ₹2,900", "note": "Consumption center hone se wholesale maang tagdi hai."},
            "haryana": {"mandis": "Karnal aur Panipat", "price": 2550, "range": "₹2,250 se ₹2,850", "note": "Delhi Azadpur proximity par achha uthaan hai."},
            "up": {"mandis": "Agra aur Kanpur", "price": 2500, "range": "₹2,200 se ₹2,800", "note": "UP wholesale mandiyon me rate sthir hai."},
            "mp": {"mandis": "Indore aur Dewas", "price": 2350, "range": "₹2,000 se ₹2,600", "note": "Malwa belt me daily arrivals steady hain."},
            "rajasthan": {"mandis": "Alwar aur Jaipur", "price": 2400, "range": "₹2,100 se ₹2,650", "note": "Alwar lal pyaaz par achha rate chal raha hai."},
            "maharashtra": {"mandis": "Lasalgaon aur Pimpalgaon", "price": 2450, "range": "₹2,100 se ₹2,750", "note": "Lasalgaon aur Pimpalgaon me quality dry pyaaz ki strong buying hai."},
            "gujarat": {"mandis": "Gondal aur Mahuva", "price": 2300, "range": "₹2,000 se ₹2,550", "note": "Saurashtra belt me white aur red onion steady hai."},
            "karnataka": {"mandis": "Bangalore aur Hubli", "price": 2650, "range": "₹2,350 se ₹3,050", "note": "South consumption centers me bhav bohot uncha hai."}
        }
    },
    "tomato": {
        "names": ["tomato", "tamatar", "tamaatar", "tamater", "टमाटर", "टमाटार", "टोमेटो"],
        "hindi": "Tamatar",
        "benchmark_price": 1550,
        "min_price": 1100,
        "max_price": 1850,
        "top_mandis": ["Pimpalgaon", "Nashik Dindori", "Kolar (Karnataka)", "Madanapalle"],
        "advisory": "Hybrid crate packing par ₹150 se ₹200 extra premium rate mil raha hai.",
        "regional_mandis": {
            "punjab": {"mandis": "Ludhiana aur Jalandhar", "price": 1500, "range": "₹1,350 se ₹1,650", "note": "Punjab local mandiyon me hybrid tamatar ka uthaan achha hai."},
            "haryana": {"mandis": "Karnal aur Ambala", "price": 1450, "range": "₹1,300 se ₹1,600", "note": "Delhi NCR border mandiyon me direct delivery par behtar rate hai."},
            "up": {"mandis": "Agra aur Kanpur", "price": 1380, "range": "₹1,250 se ₹1,550", "note": "UP me local aawak normal chal rahi hai."},
            "mp": {"mandis": "Indore aur Ujjain", "price": 1420, "range": "₹1,300 se ₹1,600", "note": "Indore APMC me trading subah se tezi me hai."},
            "rajasthan": {"mandis": "Jaipur (Muhana) aur Kota", "price": 1520, "range": "₹1,350 se ₹1,700", "note": "Muhana mandi Jaipur me wholesale maang tagdi hai."},
            "maharashtra": {"mandis": "Pimpalgaon aur Nashik", "price": 1550, "range": "₹1,400 se ₹1,800", "note": "Pimpalgaon me hybrid crate packing par sabse uncha bhav mil raha hai."},
            "gujarat": {"mandis": "Rajkot aur Ahmedabad", "price": 1480, "range": "₹1,350 se ₹1,650", "note": "Saurashtra wholesale trading smooth chal rahi hai."},
            "karnataka": {"mandis": "Kolar aur Bangalore", "price": 1650, "range": "₹1,450 se ₹1,900", "note": "Kolar APMC me interstate traders ki active buying hai."},
            "bihar": {"mandis": "Patna aur Muzaffarpur", "price": 1420, "range": "₹1,280 se ₹1,580", "note": "Local mandiyon me maang sthir hai."}
        }
    },
    "potato": {
        "names": ["potato", "aloo", "alu", "aaloo", "aalu", "batata", "आलू", "आलु", "बटाटा"],
        "hindi": "Aloo",
        "benchmark_price": 1650,
        "min_price": 1300,
        "max_price": 1950,
        "top_mandis": ["Agra", "Farrukhabad", "Indore", "Azadpur"],
        "advisory": "Cold storage nikaasi ke chalte bhav sthir hai. Jyoti aur Pukhraj variety ko achha uthaan mil raha hai.",
        "regional_mandis": {
            "up": {"mandis": "Agra aur Farrukhabad", "price": 1550, "range": "₹1,300 se ₹1,750", "note": "Agra belt me Pukhraj aur 3797 variety ki tagdi khareed hai."},
            "punjab": {"mandis": "Jalandhar aur Ludhiana", "price": 1500, "range": "₹1,250 se ₹1,650", "note": "Seed potato aur table potato dono me regular trading hai."},
            "haryana": {"mandis": "Karnal aur Kurukshetra", "price": 1520, "range": "₹1,280 se ₹1,680", "note": "Direct processing plants supply par achha rate hai."},
            "mp": {"mandis": "Indore aur Ujjain", "price": 1600, "range": "₹1,350 se ₹1,800", "note": "Indore mandi me wafer potato par premium mil raha hai."},
            "maharashtra": {"mandis": "Manchar, Pune aur Vashi", "price": 1750, "range": "₹1,450 se ₹2,050", "note": "Metro demand ke chalte rate uncha bana hua hai."},
            "west bengal": {"mandis": "Burdwan aur Hooghly", "price": 1580, "range": "₹1,350 se ₹1,750", "note": "Jyoti aloo ki Kolkata consumption demand mazboot hai."}
        }
    },
    "wheat": {
        "names": ["wheat", "gehu", "gehun", "gahu", "गेहूं", "गेहू", "कनक"],
        "hindi": "Gehun",
        "benchmark_price": 2720,
        "min_price": 2425,
        "max_price": 2980,
        "top_mandis": ["Indore (MP)", "Ujjain (MP)", "Khanna (Punjab)", "Hapur (UP)"],
        "advisory": "Government MSP ₹2,425 hai, par open market millers dry clean lot par ₹2,700 ke upar khareed rahe hain.",
        "regional_mandis": {
            "punjab": {"mandis": "Khanna aur Ludhiana", "price": 2480, "range": "₹2,425 se ₹2,600", "note": "Khanna Asia ki sabse badi anaj mandi me direct procurement active hai."},
            "haryana": {"mandis": "Karnal aur Sirsa", "price": 2460, "range": "₹2,425 se ₹2,580", "note": "MSP se upar flour millers ki direct purchase chal rahi hai."},
            "mp": {"mandis": "Indore, Sehore aur Vidisha", "price": 2850, "range": "₹2,500 se ₹3,200", "note": "Sharbati aur Lokwan gehun par millers tagda premium de rahe hain."},
            "up": {"mandis": "Hapur, Kanpur aur Agra", "price": 2550, "range": "₹2,425 se ₹2,700", "note": "Local flour mills me non-stop demand bani hui hai."},
            "rajasthan": {"mandis": "Kota aur Sri Ganganagar", "price": 2580, "range": "₹2,450 se ₹2,750", "note": "Clean bold wheat par achha bhav mil raha hai."}
        }
    },
    "garlic": {
        "names": ["garlic", "lahsun", "lehsun", "lahsan", "लहसुन", "लहसन", "लहसून"],
        "hindi": "Lahsun",
        "benchmark_price": 11500,
        "min_price": 8500,
        "max_price": 14200,
        "top_mandis": ["Mandsaur (MP)", "Neemuch (MP)", "Kota (Rajasthan)"],
        "advisory": "Ooty aur Desi lahsun me tezi bani hui hai. Super box quality 13 hazar ke paar bik rahi hai.",
        "regional_mandis": {
            "mp": {"mandis": "Mandsaur aur Neemuch", "price": 12000, "range": "₹9,500 se ₹14,500", "note": "Mandsaur me Desi aur Ooty variety par desh bhar ke traders ki buying hai."},
            "rajasthan": {"mandis": "Kota aur Pratapgarh", "price": 11500, "range": "₹9,000 se ₹13,800", "note": "Box packing quality ko top rate mil raha hai."},
            "gujarat": {"mandis": "Gondal aur Rajkot", "price": 11800, "range": "₹9,200 se ₹14,000", "note": "Export demand ke chalte bhav uncha hai."}
        }
    },
    "mustard": {
        "names": ["mustard", "sarso", "sarson", "rai", "toria", "सरसों", "सरसो", "राई"],
        "hindi": "Sarson (Mustard)",
        "benchmark_price": 5850,
        "min_price": 5400,
        "max_price": 6300,
        "top_mandis": ["Bharatpur (Rajasthan)", "Jaipur", "Hisar (Haryana)", "Morena (MP)"],
        "advisory": "42% oil condition wali sarson ₹5,800 se ₹6,100 tak asani se bik rahi hai.",
        "regional_mandis": {
            "rajasthan": {"mandis": "Bharatpur, Jaipur aur Alwar", "price": 5950, "range": "₹5,600 se ₹6,300", "note": "Bharatpur APMC me oil mills ki non-stop buying hai."},
            "haryana": {"mandis": "Hisar aur Sirsa", "price": 5850, "range": "₹5,500 se ₹6,150", "note": "High oil content lot par extra premium mil raha hai."},
            "mp": {"mandis": "Morena aur Bhind", "price": 5800, "range": "₹5,450 se ₹6,100", "note": "Chambal belt me crushing plants active hain."},
            "up": {"mandis": "Agra aur Mathura", "price": 5750, "range": "₹5,400 se ₹6,050", "note": "Wholesale oil millers ki regular khareed hai."}
        }
    },
    "cotton": {
        "names": ["cotton", "kapas", "rui", "narma", "कपास", "रुई", "नरमा"],
        "hindi": "Kapas (Cotton)",
        "benchmark_price": 7520,
        "min_price": 7120,
        "max_price": 7950,
        "top_mandis": ["Rajkot (Gujarat)", "Surendranagar", "Yavatmal (MH)", "Sirsa (Haryana)"],
        "advisory": "Medium staple MSP ₹7,121 aur Long staple ₹7,521 hai. Ginning mills dry lot par full rate de rahi hain.",
        "regional_mandis": {
            "gujarat": {"mandis": "Rajkot aur Gondal", "price": 7650, "range": "₹7,250 se ₹8,050", "note": "Shankar-6 cotton par spinning mills ki tagdi maang hai."},
            "maharashtra": {"mandis": "Yavatmal aur Jalgaon", "price": 7450, "range": "₹7,150 se ₹7,850", "note": "Vidarbha aur Khandesh me ginning factories active hain."},
            "punjab": {"mandis": "Bathinda aur Abohar", "price": 7500, "range": "₹7,200 se ₹7,900", "note": "Malwa belt me narma kapas ki achhi khareed hai."},
            "haryana": {"mandis": "Sirsa aur Fatehabad", "price": 7520, "range": "₹7,250 se ₹7,920", "note": "Dry moisture lot par pura MSP aur bonus rate mil raha hai."}
        }
    },
    "soyabean": {
        "names": ["soyabean", "soybean", "soya", "सोयाबीन", "सोया"],
        "hindi": "Soyabean",
        "benchmark_price": 4500,
        "min_price": 4100,
        "max_price": 4850,
        "top_mandis": ["Indore (MP)", "Dewas (MP)", "Latur (MH)", "Kota (Rajasthan)"],
        "advisory": "MSP ₹4,892 ke aas-paas hai. Crushing plants dry yellow soyabean par achha bhav de rahe hain.",
        "regional_mandis": {
            "mp": {"mandis": "Indore, Ujjain aur Dewas", "price": 4550, "range": "₹4,200 se ₹4,850", "note": "Asia ke sabse bade soybean processing plants Indore me active hain."},
            "maharashtra": {"mandis": "Latur aur Akola", "price": 4520, "range": "₹4,180 se ₹4,820", "note": "Marathwada oil mills direct seed purchase kar rahi hain."},
            "rajasthan": {"mandis": "Kota aur Baran", "price": 4480, "range": "₹4,150 se ₹4,780", "note": "Hadoti belt me steady trading chal rahi hai."}
        }
    },
    "paddy": {
        "names": ["paddy", "rice", "dhan", "chawal", "dhaan", "basmati", "धान", "चावल", "बासमती"],
        "hindi": "Dhan (Paddy)",
        "benchmark_price": 2320,
        "min_price": 2300,
        "max_price": 3950,
        "top_mandis": ["Karnal (Haryana)", "Bhatinda (Punjab)", "Gondia (MH)", "Burdwan (WB)"],
        "advisory": "Grade-A Dhan ka MSP ₹2,320 hai. Basmati 1509 aur 1718 me rate ₹3,600 se ₹4,000 chal raha hai.",
        "regional_mandis": {
            "punjab": {"mandis": "Amritsar, Khanna aur Bathinda", "price": 3650, "range": "₹2,320 se ₹4,100", "note": "Basmati 1121 aur 1509 par export millers tagda rate de rahe hain."},
            "haryana": {"mandis": "Karnal aur Taraori", "price": 3700, "range": "₹2,320 se ₹4,150", "note": "Basmati rice bowl of India me top international exporters active hain."},
            "up": {"mandis": "Barabanki aur Bareilly", "price": 2350, "range": "₹2,300 se ₹2,600", "note": "Government procurement center par MSP sunishchit hai."},
            "bihar": {"mandis": "Buxar aur Patna", "price": 2300, "range": "₹2,200 se ₹2,450", "note": "Local PACS aur millers regular purchase kar rahe hain."}
        }
    },
    "chana": {
        "names": ["chana", "gram", "chickpea", "bengal gram", "chane", "चना", "चने", "छोला"],
        "hindi": "Chana",
        "benchmark_price": 6150,
        "min_price": 5600,
        "max_price": 6600,
        "top_mandis": ["Bikaner (Rajasthan)", "Indore (MP)", "Akola (MH)", "Latur (MH)"],
        "advisory": "Chana ka MSP ₹5,650 hai. Dal millers ki maang se rate lagbhag ₹6,150 prati quintal chal raha hai.",
        "regional_mandis": {
            "rajasthan": {"mandis": "Bikaner aur Jaipur", "price": 6250, "range": "₹5,800 se ₹6,650", "note": "Dal millers ki continuous demand se bhav uncha hai."},
            "mp": {"mandis": "Indore aur Vidisha", "price": 6180, "range": "₹5,750 se ₹6,550", "note": "Desi aur dollar chana dono me achha uthaan hai."},
            "maharashtra": {"mandis": "Latur aur Akola", "price": 6100, "range": "₹5,680 se ₹6,500", "note": "Wholesale pulses trading active hai."}
        }
    },
    "maize": {
        "names": ["maize", "corn", "makka", "makai", "bhutta", "मक्का", "मकई", "भुट्टा"],
        "hindi": "Makka",
        "benchmark_price": 2225,
        "min_price": 1950,
        "max_price": 2450,
        "top_mandis": ["Davangere (Karnataka)", "Gulabbagh (Bihar)", "Chhindwara (MP)", "Nanded"],
        "advisory": "Poultry feed aur ethanol plants ki maang se makka ka bhav mazboot hai.",
        "regional_mandis": {
            "bihar": {"mandis": "Gulabbagh (Purnia) aur Begusarai", "price": 2300, "range": "₹2,050 se ₹2,480", "note": "Gulabbagh Asia ki sabse badi makka mandi me round-the-clock trading hai."},
            "mp": {"mandis": "Chhindwara aur Betul", "price": 2240, "range": "₹1,980 se ₹2,420", "note": "Corn starch aur feed factories bulk khareed rahi hain."},
            "karnataka": {"mandis": "Davangere aur Ranebennur", "price": 2280, "range": "₹2,020 se ₹2,460", "note": "Poultry hubs ki steady demand hai."}
        }
    }
}


class AgriIntelligenceEngine:
    """
    Sovereign Full-Duplex Indic Agricultural Intelligence Engine.
    Dynamically answers any open-ended farmer query across India.
    """

    def analyze_and_respond(self, utterance: str, session: Any) -> Dict[str, Any]:
        text = utterance.strip().lower()

        # 0. Background Profile Extraction (Silently update profile without blocking)
        self._silent_profile_extraction(text, session)

        # 1. If actively awaiting farmer's location for a crop rate inquiry:
        if getattr(session, "step", "") == "AWAITING_LOCATION":
            loc_res = self._handle_location_response(text, session)
            if loc_res:
                return loc_res

        # 2. Check Agri-RAG for Scientific ICAR / KVK Advisory (Diseases, Pests, Fertilizer, Sowing, Schemes)
        is_price_query = any(w in text for w in ["bhav", "rate", "bhav kya", "rate kya", "kimat", "mandi rate", "aaj ka rate", "भाव क्या", "मंडी भाव", "रेट बताओ", "का भाव", "के भाव"])
        if not is_price_query:
            rag_res = agri_rag.answer_query(text, session.farmer_name)
            if rag_res:
                return rag_res

        # 3. Check for Crop Doctor / Disease / Pest Diagnosis fallback
        disease_res = self._handle_disease_pest_query(text, session)
        if disease_res:
            return disease_res

        # 3. Check for Fertilizer / Soil Nutrition / Urea / DAP
        fertilizer_res = self._handle_fertilizer_nutrition(text, session)
        if fertilizer_res:
            return fertilizer_res

        # 4. Check for Government Schemes & Subsidies (PM-Kisan, KCC, Fasal Bima, Kusum)
        scheme_res = self._handle_government_schemes(text, session)
        if scheme_res:
            return scheme_res

        # 5. Check for eNAM Statutory Mandi Rights & Commission Rules
        enam_res = self._handle_enam_and_legal(text, session)
        if enam_res:
            return enam_res

        # 6. Check for Weather, Sowing, Irrigation, Seed Treatment
        agronomy_res = self._handle_agronomy_and_weather(text, session)
        if agronomy_res:
            return agronomy_res

        # 7. Check for Mandi Rate / Commodity Pricing / Mandi Arbitrage Inquiry
        mandi_res = self._handle_commodity_query(text, session)
        if mandi_res:
            return mandi_res

        # 8. Check for Quantity answer if awaiting quantity
        if getattr(session, "step", "") == "AWAITING_QUANTITY":
            qty_res = self._handle_quantity_response(text, session)
            if qty_res:
                return qty_res

        # 9. Check for Transport answer if awaiting transport
        if getattr(session, "step", "") == "AWAITING_TRANSPORT":
            trans_res = self._handle_transport_response(text, session)
            if trans_res:
                return trans_res

        # 10. Check for Chit-chat / Greetings / Name confirmation / Gratitude
        chitchat_res = self._handle_chitchat_and_general(text, session)
        if chitchat_res:
            return chitchat_res

        # 11. Open Generative Agricultural Fallback (Never gets stuck, always answers meaningfully)
        return self._generate_open_agri_response(text, session)

    def _silent_profile_extraction(self, text: str, session: Any):
        """Silently extracts farmer name or location without interrogating."""
        try:
            from app.services.farmer_db import farmer_db
            
            # Name extraction: "mera naam X hai", "main X bol raha hoon"
            name_match = re.search(r"(?:mera naam|main|hum|naam)\s+([a-zA-Z\u0900-\u097F]+)(?:\s+(?:hoon|hai|bol))?", text)
            if name_match:
                extracted = name_match.group(1).strip()
                if extracted not in ["kisan", "bhaiya", "bol", "yahan", "ek", "do", "bhai", "ji", "punjab", "haryana"]:
                    session.farmer_name = extracted.capitalize()
                    farmer_db.update_farmer_profile(session.phone_number, name=session.farmer_name)

            # Location extraction via dictionary
            loc_res = self._extract_location_from_text(text)
            if loc_res:
                state_code, display_name = loc_res
                session.state = state_code
                session.district = display_name
                session.location_name = display_name
                farmer_db.update_location(session.phone_number, village=display_name, district=display_name)
        except Exception:
            pass

    def _extract_location_from_text(self, text: str) -> Optional[Tuple[str, str]]:
        clean = text.lower()
        for place_key, (state_code, display_name) in STATE_DISTRICT_MAP.items():
            if any(ord(c) > 127 for c in place_key):
                if place_key in clean:
                    return state_code, display_name
            else:
                pattern = r"(?:^|\W)" + re.escape(place_key) + r"(?:$|\W)"
                if re.search(pattern, clean):
                    return state_code, display_name
        return None

    def _match_commodity(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        clean_text = text.lower()
        for comm_key, comm_data in COMMODITY_DATABASE.items():
            for alias in comm_data["names"]:
                alias_lower = alias.lower()
                # Check for Devanagari / non-ASCII characters directly
                if any(ord(c) > 127 for c in alias_lower):
                    if alias_lower in clean_text:
                        return comm_key, comm_data
                else:
                    pattern = r"(?:^|\W)" + re.escape(alias_lower) + r"(?:$|\W)"
                    if re.search(pattern, clean_text):
                        return comm_key, comm_data
        return None

    def _handle_location_response(self, text: str, session: Any) -> Optional[Dict[str, Any]]:
        loc_res = self._extract_location_from_text(text)
        if loc_res:
            state_code, display_name = loc_res
            session.state = state_code
            session.district = display_name
            session.location_name = display_name
            try:
                from app.services.farmer_db import farmer_db
                farmer_db.update_location(session.phone_number, village=display_name, district=display_name)
            except Exception:
                pass

            comm_key = getattr(session, "commodity", None)
            if comm_key and comm_key in COMMODITY_DATABASE:
                comm_data = COMMODITY_DATABASE[comm_key]
                hindi_name = comm_data["hindi"]
                reg_info = comm_data.get("regional_mandis", {}).get(state_code)
                if reg_info:
                    mandis = reg_info["mandis"]
                    price = reg_info["price"]
                    p_range = reg_info["range"]
                    note = reg_info.get("note", "")
                else:
                    mandis = ", ".join(comm_data["top_mandis"][:2])
                    price = comm_data["benchmark_price"]
                    p_range = f"₹{comm_data['min_price']} se ₹{comm_data['max_price']}"
                    note = comm_data.get("advisory", "")

                spoken = (
                    f"Ji {session.farmer_name} ji! {display_name} ke paas {mandis} mandiyon me {hindi_name} ka taaza bhav "
                    f"lagbhag ₹{price:,} prati quintal chal raha hai ({p_range}). {note} "
                    f"Aapke paas bechne ke liye lagbhag kitna maal hai—jaise kitne katte ya quintal?"
                )
                session.step = "AWAITING_QUANTITY"
                return {
                    "spoken_text": spoken,
                    "step": "AWAITING_QUANTITY",
                    "data": {
                        "commodity": comm_key,
                        "location": display_name,
                        "benchmark_price": price,
                        "range": p_range
                    }
                }
            else:
                spoken = (
                    f"Bahut badhiya {session.farmer_name} ji! Maine aapka kshetr {display_name} darj kar liya hai. "
                    f"Ab batayein aaj kaunsi fasal ka taaza mandi bhav aur munafa dekhna chahte hain?"
                )
                session.step = "ACTIVE"
                return {
                    "spoken_text": spoken,
                    "step": "ACTIVE",
                    "data": {"location": display_name}
                }
        else:
            # Check if user asked an advisory question or if Agri-RAG matches
            if agri_rag.retrieve(text, top_k=1):
                session.step = "ACTIVE"
                return None

            other_intent_keywords = [
                "bimari", "keeda", "keede", "rog", "patte", "dawai", "spray", "sundi", "thrips", "safed makhi", "chhed",
                "urea", "dap", "npk", "khad", "fertilizer", "khat", "zinc", "sulphur", "peelapan", "peele",
                "enam", "commission", "aadhatiya", "yojana", "bima", "pm kisan", "kcc", "loan",
                "बीमारी", "कीड़ा", "कीड़े", "रोग", "पत्ते", "दवाई", "दवा", "स्प्रे", "सुंडी", "थ्रिप्स", "सफेद मक्खी", "छेद",
                "यूरिया", "डीएपी", "एनपीके", "खाद", "जिंक", "सल्फर", "पीलापन", "पीले", "कमीशन", "आढ़तिया", "दलाली", "योजना", "बीमा", "ऋण", "लोन"
            ]
            if any(w in text for w in other_intent_keywords):
                session.step = "ACTIVE"
                return None

            return {
                "spoken_text": (
                    f"Kisan bhai, kripya apna rajya (state) ya mukhya jila saaf batayein, "
                    f"jaise Punjab, Haryana, UP, MP ya Maharashtra, taaki main aapke ilake ki mandi ka taaza bhav bata sakoon."
                ),
                "step": "AWAITING_LOCATION",
                "data": {}
            }

    def _handle_commodity_query(self, text: str, session: Any) -> Optional[Dict[str, Any]]:
        matched = self._match_commodity(text)
        if not matched:
            if any(w in text for w in ["mandi bhav", "taaza bhav", "aaj ka rate", "mandi ka rate", "भाव क्या", "मंडी भाव", "रेट बताओ", "commodity rate"]):
                return {
                    "spoken_text": (
                        f"Ji {session.farmer_name} ji! Main sabhi mukhya faslon—jaise Tamatar, Pyaaz, Gehun, Dhan, Makka, Chana, Soyabean, Aloo aur Sarson "
                        f"ke live mandi rates track karta hoon. Aap kaunsi fasal ka taaza bhav jaanna chahte hain?"
                    ),
                    "step": "ACTIVE",
                    "data": {}
                }
            return None

        comm_key, data = matched
        hindi_name = data["hindi"]
        session.commodity = comm_key

        # 1. Check if location was mentioned in the current query itself
        loc_res = self._extract_location_from_text(text)
        if loc_res:
            state_code, display_name = loc_res
            session.state = state_code
            session.district = display_name
            session.location_name = display_name
            try:
                from app.services.farmer_db import farmer_db
                farmer_db.update_location(session.phone_number, village=display_name, district=display_name)
            except Exception:
                pass

        known_state = getattr(session, "state", None) or getattr(session, "district", None)

        # 2. CRITICAL USER SPECIFICATION: IF LOCATION IS UNKNOWN, DO NOT ASSUME NASHIK OR DUMP ALL-INDIA RATES!
        # DIRECTLY AND POLITELY ASK THE FARMER FOR THEIR DISTRICT / STATE!
        if not known_state:
            session.step = "AWAITING_LOCATION"
            is_english = any(w in text for w in ["what is", "price", "rate of", "tell me", "how much", "rate"])
            if is_english:
                spoken = f"Sure {session.farmer_name}! To provide you the exact mandi rate for {data.get('names', [comm_key])[0].capitalize()}, could you please tell me your district or state?"
            else:
                spoken = f"Ji {session.farmer_name} ji! {hindi_name} ka sahi aur taaza mandi bhav batane ke liye, aap kripya batayein aap kaunse jile ya rajya (state) se bol rahe hain?"
            return {
                "spoken_text": spoken,
                "step": "AWAITING_LOCATION",
                "data": {"commodity": comm_key, "hindi_name": hindi_name}
            }

        # 3. Location is KNOWN: Provide specific regional rates
        state_key = known_state.lower()
        reg_info = data.get("regional_mandis", {}).get(state_key)
        if not reg_info:
            for r_key, r_val in data.get("regional_mandis", {}).items():
                if r_key in state_key or state_key in r_key:
                    reg_info = r_val
                    break

        if reg_info:
            mandis = reg_info["mandis"]
            rate = reg_info["price"]
            p_range = reg_info["range"]
            note = reg_info.get("note", "")
        else:
            mandis = ", ".join(data["top_mandis"][:2])
            rate = data["benchmark_price"]
            p_range = f"₹{data['min_price']} se ₹{data['max_price']}"
            note = data.get("advisory", "")

        # Check if farmer also stated quantity
        num, unit = self._extract_quantity(text)
        if num:
            session.raw_quantity_num = num
            session.unit_type = unit
            if unit == "kg":
                qtl = round(num / 100.0, 3)
            elif unit in ["katta", "bori", "bag"]:
                qtl = round((num * 50.0) / 100.0, 2)
            elif unit == "ton":
                qtl = round(num * 10.0, 2)
            elif unit == "mann":
                qtl = round((num * 40.0) / 100.0, 2)
            elif unit == "pickup":
                qtl = round(num * 18.0, 2)
            elif unit == "trolley":
                qtl = round(num * 30.0, 2)
            else:
                qtl = round(float(num), 2)
            session.quantity_quintals = qtl

            rate_per_kg = round(rate / 100.0, 2)
            total_gross = int(round(qtl * rate))
            est_freight = int(round(qtl * 35))
            est_cess = int(round(total_gross * 0.01))
            est_hamali = int(round(qtl * 15))
            est_net = int(round(total_gross - est_freight - est_cess - est_hamali))

            if unit == "kg":
                weight_str = f"{int(num) if num.is_integer() else num} किलो ({qtl} क्विंटल)"
            else:
                weight_str = f"{int(qtl) if qtl.is_integer() else qtl} क्विंटल ({int(round(qtl * 100))} किलो)"

            spoken = (
                f"{session.farmer_name} ji! {session.district or session.state} me {mandis} mandiyon me {hindi_name} ka taaza modal bhav lagbhag ₹{rate:,} prati quintal (₹{rate_per_kg} prati kilo) chal raha hai ({p_range}). "
                f"Aapke {weight_str} maal ka kul gross moolya ₹{total_gross:,} rupaye banta hai! "
                f"Gaadi aur mandi kharcha nikaal kar lagbhag ₹{est_net:,} seedhe aapke haath me aayenge. {note} "
                f"Mandi le jaane ke liye gaadi aapki apni hai, ya tempo bhade par karenge?"
            )
            session.step = "AWAITING_TRANSPORT"
        else:
            spoken = (
                f"{session.farmer_name} ji! {session.district or session.state} me {mandis} mandiyon me {hindi_name} ka taaza bhav lagbhag ₹{rate:,} prati quintal chal raha hai ({p_range}). {note} "
                f"Aapke paas bechne ke liye lagbhag kitna maal hai—jaise kitne katte, kilo ya quintal?"
            )
            session.step = "AWAITING_QUANTITY"

        return {
            "spoken_text": spoken,
            "step": session.step,
            "data": {
                "commodity": comm_key,
                "hindi_name": hindi_name,
                "benchmark_price": rate,
                "range": p_range
            }
        }

    def _handle_quantity_response(self, text: str, session: Any) -> Optional[Dict[str, Any]]:
        num, unit = self._extract_quantity(text)
        if num:
            session.raw_quantity_num = num
            session.unit_type = unit
            if unit == "kg":
                qtl = round(num / 100.0, 3)
            elif unit in ["katta", "bori", "bag"]:
                qtl = round((num * 50.0) / 100.0, 2)
            elif unit == "ton":
                qtl = round(num * 10.0, 2)
            elif unit == "mann":
                qtl = round((num * 40.0) / 100.0, 2)
            elif unit == "pickup":
                qtl = round(num * 18.0, 2)
            elif unit == "trolley":
                qtl = round(num * 30.0, 2)
            else:
                qtl = round(float(num), 2)
            session.quantity_quintals = qtl

            # Check if commodity is in session or in text
            comm_key = getattr(session, "commodity", None)
            if not comm_key:
                matched = self._match_commodity(text)
                if matched:
                    comm_key = matched[0]
                    session.commodity = comm_key

            comm_data = COMMODITY_DATABASE.get(comm_key or "potato", COMMODITY_DATABASE["potato"])
            hindi_crop = comm_data["hindi"]
            rate = comm_data["benchmark_price"]
            top_mandi = comm_data["top_mandis"][0]

            state_code = getattr(session, "state", None) or "up"
            reg_info = comm_data.get("regional_mandis", {}).get(state_code.lower())
            if reg_info:
                rate = reg_info["price"]
                top_mandi = reg_info["mandis"]

            rate_per_kg = round(rate / 100.0, 2)
            gross_earning = int(round(qtl * rate))
            est_freight = int(round(qtl * 35))
            est_cess = int(round(gross_earning * 0.01))
            est_hamali = int(round(qtl * 15))
            est_net = int(round(gross_earning - est_freight - est_cess - est_hamali))

            if unit == "kg":
                weight_str = f"{int(num) if num.is_integer() else num} किलो ({qtl} क्विंटल)"
            else:
                weight_str = f"{int(qtl) if qtl.is_integer() else qtl} क्विंटल ({int(round(qtl * 100))} किलो)"

            own_words = ["apni", "apna", "bolero", "pickup", "tractor", "own", "meri", "khud ki", "अपनी", "अपना", "बोलेरो", "पिकअप", "ट्रैक्टर", "खुद की", "मेरी"]
            hired_words = ["tempo", "bhada", "bhade", "rent", "kiraya", "chhota hathi", "टेंपो", "भाड़ा", "भाड़े", "किराया", "छोटा हाथी"]

            if any(w in text for w in own_words):
                session.has_own_vehicle = True
                session.vehicle_name = "Own Vehicle"
                from app.services.dialogue_manager import dialogue_manager
                return dialogue_manager._compute_and_deliver_arbitrage(session)
            elif any(w in text for w in hired_words):
                session.has_own_vehicle = False
                session.vehicle_name = "Hired Tempo"
                from app.services.dialogue_manager import dialogue_manager
                return dialogue_manager._compute_and_deliver_arbitrage(session)
            else:
                session.step = "AWAITING_TRANSPORT"
                spoken = (
                    f"Kisan Bhai ji, aapke {weight_str} {hindi_crop} ka taaza mandi bhav {top_mandi} me "
                    f"₹{rate:,} prati quintal (₹{rate_per_kg} prati kilo) chal raha hai. "
                    f"Is hisaab se aapka kul gross moolya ₹{gross_earning:,} rupaye banta hai! "
                    f"Kharcha kaatne ke baad lagbhag ₹{est_net:,} seedhe aapke haath me aayenge. "
                    f"Batayein, mandi le jaane ke liye gaadi aapki apni hai, ya tempo bhade par karenge?"
                )
                return {
                    "spoken_text": spoken,
                    "step": "AWAITING_TRANSPORT",
                    "data": {
                        "commodity": comm_key,
                        "quantity_quintals": qtl,
                        "gross_earning": gross_earning,
                        "net_earning": est_net,
                        "modal_rate": rate,
                        "rate_per_kg": rate_per_kg,
                        "top_mandi": top_mandi
                    }
                }
        return None

    def _handle_transport_response(self, text: str, session: Any) -> Optional[Dict[str, Any]]:
        own_words = ["apni", "apna", "bolero", "pickup", "tractor", "own", "meri", "khud ki", "अपनी", "अपना", "बोलेरो", "पिकअप", "ट्रैक्टर", "खुद की", "मेरी"]
        hired_words = ["tempo", "bhada", "bhade", "rent", "kiraya", "chhota hathi", "टेंपो", "भाड़ा", "भाड़े", "किराया", "छोटा हाथी"]

        if any(w in text for w in own_words):
            session.has_own_vehicle = True
            session.vehicle_name = "Own Vehicle"
            from app.services.dialogue_manager import dialogue_manager
            return dialogue_manager._compute_and_deliver_arbitrage(session)
        elif any(w in text for w in hired_words):
            session.has_own_vehicle = False
            session.vehicle_name = "Hired Tempo"
            from app.services.dialogue_manager import dialogue_manager
            return dialogue_manager._compute_and_deliver_arbitrage(session)
        return None

    def _extract_quantity(self, text: str) -> Tuple[Optional[float], Optional[str]]:
        # 1. Normalize Indic / Devanagari numerals ०-९ -> 0-9
        indic_to_ascii = str.maketrans('०१२३४५६७८९', '0123456789')
        clean = text.translate(indic_to_ascii).lower()

        # 2. Hindi word numbers to digits
        hindi_numbers = {
            "ek": 1.0, "एक": 1.0, "do": 2.0, "दो": 2.0, "teen": 3.0, "तीन": 3.0,
            "char": 4.0, "चार": 4.0, "paanch": 5.0, "panch": 5.0, "पांच": 5.0, "पाँच": 5.0,
            "chhah": 6.0, "छह": 6.0, "saat": 7.0, "सात": 7.0, "aath": 8.0, "आठ": 8.0,
            "nau": 9.0, "नौ": 9.0, "das": 10.0, "दस": 10.0, "gyarah": 11.0, "ग्यारह": 11.0,
            "barah": 12.0, "बारह": 12.0, "pandrah": 15.0, "पंद्रह": 15.0, "bees": 20.0, "बीस": 20.0,
            "pachis": 25.0, "पच्चीस": 25.0, "tees": 30.0, "तीस": 30.0, "chalis": 40.0, "चालीस": 40.0,
            "pachaas": 50.0, "pachas": 50.0, "पचास": 50.0, "sau": 100.0, "सौ": 100.0, "dedh": 1.5, "derh": 1.5, "डेढ़": 1.5,
            "dhai": 2.5, "ढाई": 2.5
        }

        # Match regex with unit
        unit_regex = r"(katta|katte|कट्टे|कट्टा|bori|boriyan|बोरी|बोरियां|bag|bags|बैग|quintal|kuntal|क्विंटल|कुंतल|qtl|qtls|kilo|kilos|kg|kgs|किलो|किलोग्राम|केजी|ton|tonne|टन|mann|man|मन|trolley|traali|ट्रॉली|ट्रोली|pickup|पिकअप|gadi|गाड़ी)?"
        pattern = r"(\d+(?:\.\d+)?)\s*" + unit_regex
        match = re.search(pattern, clean)

        if match:
            num = float(match.group(1))
            raw_unit = (match.group(2) or "").strip().lower()
            if any(x in raw_unit for x in ["kilo", "kg", "किलो", "किलोग्राम", "केजी"]):
                unit_norm = "kg"
            elif any(x in raw_unit for x in ["katt", "कट्ट", "कट्टा", "bor", "बोर", "bag", "बैग"]):
                unit_norm = "bori"
            elif any(x in raw_unit for x in ["ton", "टन"]):
                unit_norm = "ton"
            elif any(x in raw_unit for x in ["mann", "man", "मन"]):
                unit_norm = "mann"
            elif any(x in raw_unit for x in ["pickup", "पिकअप"]):
                unit_norm = "pickup"
            elif any(x in raw_unit for x in ["troll", "traal", "ट्रॉली", "ट्रोली"]):
                unit_norm = "trolley"
            else:
                unit_norm = "quintal"
            return num, unit_norm

        # Try matching written hindi numbers
        for w_word, w_val in hindi_numbers.items():
            h_pattern = r"(?:^|\s)" + re.escape(w_word) + r"\s*" + unit_regex
            h_match = re.search(h_pattern, clean)
            if h_match:
                raw_unit = (h_match.group(1) or "").strip().lower()
                if any(x in raw_unit for x in ["kilo", "kg", "किलो", "किलोग्राम", "केजी"]):
                    unit_norm = "kg"
                elif any(x in raw_unit for x in ["katt", "कट्ट", "कट्टा", "bor", "बोर", "bag", "बैग"]):
                    unit_norm = "bori"
                elif any(x in raw_unit for x in ["ton", "टन"]):
                    unit_norm = "ton"
                elif any(x in raw_unit for x in ["mann", "man", "मन"]):
                    unit_norm = "mann"
                elif any(x in raw_unit for x in ["pickup", "पिकअप"]):
                    unit_norm = "pickup"
                elif any(x in raw_unit for x in ["troll", "traal", "ट्रॉली", "ट्रोली"]):
                    unit_norm = "trolley"
                else:
                    unit_norm = "quintal"
                return w_val, unit_norm

        return None, None

    def _handle_disease_pest_query(self, text: str, session: Any) -> Optional[Dict[str, Any]]:
        disease_triggers = [
            "bimari", "beemari", "keeda", "keede", "rog", "patte", "peele", "chhed", "sukh", "murjha", 
            "dawai", "spray", "faphund", "fungus", "virus", "sundi", "thrips", "safed makhi", "whitefly", "curl"
        ]
        if not any(w in text for w in disease_triggers):
            return None

        # 1. Leaf Curl / Virus (Tamatar, Mirchi, Pyaaz)
        if any(w in text for w in ["curl", "mud rahe", "sikud", "peele pad", "pila"]):
            return {
                "spoken_text": (
                    "Kisan bhai, patton ka mudna aur peela padna Leaf Curl Virus ke lakshan hain, jo safed makhi ya thrips ke kaaran failta hai. "
                    "Iske ilaj ke liye: 1) Pehle rog-grast podhon ko ukhad kar nikal dein. "
                    "2) Safed makhi ke niyantran ke liye Imidacloprid (17.8 SL) 1 ml per 3 litre paani me ghol kar chhidkaav karein. "
                    "Ya jaivik me Neem ka tel (1500 PPM) 3 ml per litre paani chhidkein."
                ),
                "step": "CROP_DOCTOR",
                "data": {"disease": "Leaf Curl Virus", "type": "Viral/Vector"}
            }

        # 2. Fruit/Shoot Borer / Sundi (Chana, Tamatar, Makka, Kapas)
        if any(w in text for w in ["sundi", "illii", "illi", "chhed", "borer", "fall armyworm"]):
            return {
                "spoken_text": (
                    "Kisan bhai, fasal me sundi ya illi lagne par fal aur tano me chhed ho jate hain. "
                    "Iske turant rokthaam ke liye: Emamectin Benzoate (5% SG) 4 gram per 10 litre paani, ya "
                    "Chlorantraniliprole (Coragen) 0.4 ml per litre paani me ghol kar shaam ke samay chhidkaav karein. "
                    "Jaivik tareeqe ke liye Pheromone traps lagayein."
                ),
                "step": "CROP_DOCTOR",
                "data": {"disease": "Fruit/Stem Borer", "type": "Insect"}
            }

        # 3. Blight / Fungal Rot / Jhulsa (Aloo, Tamatar, Pyaaz)
        if any(w in text for w in ["jhulsa", "blight", "sad", "galan", "dhabbe", "fungus"]):
            return {
                "spoken_text": (
                    "Kisan bhai, yeh Faphund yaani Jhulsa (Blight) bimari ho sakti hai jisse patton par kaale bhure dhabbe bante hain. "
                    "Iske rokthaam ke liye Mancozeb (75% WP) 2.5 gram per litre paani, ya "
                    "Saaf (Carbendazim + Mancozeb) 2 gram per litre paani me milakar chhidkaav karein. "
                    "Kheton me paani bharne na dein."
                ),
                "step": "CROP_DOCTOR",
                "data": {"disease": "Blight/Fungus", "type": "Fungal"}
            }

        # General Pest & Disease guidance
        return {
            "spoken_text": (
                "Kisan bhai, fasal ki bimari ko sahi pehchanne ke liye kripya fasal ka naam aur patton ya podhe ke mukhya lakshan batayein—jaise "
                "kya patte sukhe hain, keeda dikh raha hai ya jhulsa rog hai? Main turant sahi dawai aur dosage bata dunga."
            ),
            "step": "CROP_DOCTOR",
            "data": {}
        }

    def _handle_fertilizer_nutrition(self, text: str, session: Any) -> Optional[Dict[str, Any]]:
        fert_words = ["urea", "dap", "potash", "khad", "fertilizer", "khat", "npk", "zinc", "sulphur", "poshan", "dosage"]
        if not any(w in text for w in fert_words):
            return None

        if "dap" in text or "d.a.p" in text:
            return {
                "spoken_text": (
                    "Kisan bhai, DAP (Di-Ammonium Phosphate) buwaai ya ropai ke samay jadon ke vikas ke liye diya jata hai. "
                    "Isme 18% Nitrogen aur 46% Phosphorus hota hai. Fasal ke hisaab se 50 kilo prati acre buwaai ke samay daalein, "
                    "aur dhyan rahe khadi fasal me top-dressing ke liye DAP ke bajay Urea aur NPK 19:19:19 ka upyog karein."
                ),
                "step": "AGRONOMY",
                "data": {"nutrient": "DAP"}
            }

        if "urea" in text:
            return {
                "spoken_text": (
                    "Kisan bhai, Urea me 46% Nitrogen hota hai jo paudhe ki vegetative growth badhata hai. "
                    "Urea ko hamesha 2 se 3 kiston me top-dressing ke roop me dein—pehla kist pehli sinchai ke baad aur doosra phool aane se pehle. "
                    "Neem coated urea ka upyog karein taaki nitrogen dheere-dheere paudhe ko mile."
                ),
                "step": "AGRONOMY",
                "data": {"nutrient": "Urea"}
            }

        if any(w in text for w in ["npk", "19:19:19", "spray"]):
            return {
                "spoken_text": (
                    "Kisan bhai, khadi fasal me jald asar ke liye water soluble NPK 19:19:19 ka 1 kilogram per 200 litre paani (5 gram per litre) "
                    "foliar spray karein. Isse paudhe me peela-pan door hota hai aur nayi shakhaayein tezi se nikalte hain."
                ),
                "step": "AGRONOMY",
                "data": {"nutrient": "NPK Foliar"}
            }

        if any(w in text for w in ["zinc", "sulphur"]):
            return {
                "spoken_text": (
                    "Kisan bhai, Zinc Sulphate (21% ya 33%) dhaan, makka aur gehun ke liye behad zaroori hai. "
                    "Yeh khaira rog se bachata hai. Prati acre 10 se 15 kilo Zinc Sulphate aakhri jutai ke samay ya pehli sinchai par dein. "
                    "DAP aur Zinc ko kabhi ek saath mila kar na daalein."
                ),
                "step": "AGRONOMY",
                "data": {"nutrient": "Zinc/Sulphur"}
            }

        return {
            "spoken_text": (
                "Kisan bhai, santulit khad ke liye mitti ki jaanch (Soil Test) sabse zaroori hai. Aamtaur par 4:2:1 anupaat me "
                "Nitrogen, Phosphorus aur Potash dena chahiye. Fasal ka naam batayein toh main uski exact khad ki matra bata sakta hoon."
            ),
            "step": "AGRONOMY",
            "data": {}
        }

    def _handle_government_schemes(self, text: str, session: Any) -> Optional[Dict[str, Any]]:
        scheme_words = ["yojana", "scheme", "pm kisan", "samman nidhi", "kcc", "credit card", "fasal bima", "pmfby", "kusum", "solar pump", "subsidy", "sarkari"]
        if not any(w in text for w in scheme_words):
            return None

        # PM-Kisan Samman Nidhi
        if any(w in text for w in ["pm kisan", "samman nidhi", "2000", "kist"]):
            return {
                "spoken_text": (
                    "Kisan bhai, PM-Kisan Samman Nidhi ke tehat kisanon ko saal me ₹6,000 milte hain—₹2,000 ki teen kiston me. "
                    "Kist praapt karne ke liye 3 cheezein zaroori hain: 1) pmkisan.gov.in par Aadhaar e-KYC poori hona, "
                    "2) Bank khate se Aadhaar aur NPCI direct benefit transfer link hona, aur 3) Land Seeding verified hona. "
                    "Aap apne nazdeeki CSC center ya PM Kisan portal par status check kar sakte hain."
                ),
                "step": "GOV_SCHEME",
                "data": {"scheme": "PM-Kisan"}
            }

        # Kisan Credit Card (KCC)
        if any(w in text for w in ["kcc", "credit card", "loan", "byaj"]):
            return {
                "spoken_text": (
                    "Kisan bhai, Kisan Credit Card (KCC) par kisanon ko sirf 4% annual byaj dar par karz milta hai (7% interest me 3% ki chhoot samay par chukane par). "
                    "Isme ₹1,60,000 tak ka loan bina kisi collateral ya zameen bandhak rakhe milta hai, aur ₹3 lakh tak concessional rate par. "
                    "Aap apne bank branch me bahi-khata, khasra-khatauni aur aadhar card le jaakar aavedan kar sakte hain."
                ),
                "step": "GOV_SCHEME",
                "data": {"scheme": "KCC"}
            }

        # Pradhan Mantri Fasal Bima Yojana (PMFBY)
        if any(w in text for w in ["fasal bima", "pmfby", "bima", "nuksan", "claim"]):
            return {
                "spoken_text": (
                    "Kisan bhai, Pradhan Mantri Fasal Bima Yojana ke tehat Kharif faslon par sirf 2% aur Rabi par 1.5% premium lagta hai. "
                    "Agar bemausam baarish, olavrishti ya sookhe se fasal ka nuksan hota hai, toh 72 ghante ke andar Crop Insurance App par ya "
                    "toll-free number 14447 par intimation darj karwana kanoonan anivarya hai taaki survey team aa kar claim sanction kare."
                ),
                "step": "GOV_SCHEME",
                "data": {"scheme": "PMFBY"}
            }

        # PM Kusum Solar Pump
        if any(w in text for w in ["kusum", "solar", "solar pump", "pump"]):
            return {
                "spoken_text": (
                    "Kisan bhai, PM-Kusum Solar Pump Yojana ke tehat 3HP se 7.5HP tak ke solar water pump lagwane par 60% tak government subsidy milti hai, "
                    "30% bank loan milta hai aur kisan ko sirf 10% kharch karna padta hai. Isse diesel aur bijli ka poora kharcha bach jata hai. "
                    "Aavedan state renewable energy portal par hota hai."
                ),
                "step": "GOV_SCHEME",
                "data": {"scheme": "PM-Kusum"}
            }

        return {
            "spoken_text": (
                "Kisan bhai, sarkari yojanaon me PM-Kisan Samman Nidhi, Kisan Credit Card (4% loan), Fasal Bima Yojana, aur PM Kusum Solar Pump "
                "kisanon ke hit me uplabdh hain. Aap kis yojana ke niyam ya aavedan ke bare me jaanna chahte hain?"
            ),
            "step": "GOV_SCHEME",
            "data": {}
        }

    def _handle_enam_and_legal(self, text: str, session: Any) -> Optional[Dict[str, Any]]:
        enam_triggers = ["enam", "e-nam", "commission", "aadhatiya", "arhatiya", "vyapari", "hamali", "dalali", "tolai", "parchi", "slip", "kanoon", "adhikar"]
        if not any(w in text for w in enam_triggers):
            return None

        if any(w in text for w in ["commission", "dalali", "aadhatiya", "arhatiya", "kaat"]):
            return {
                "spoken_text": (
                    "Kisan bhai dhyan dein: eNAM aur statutory APMC niyam ke mutabiq kisan se ZERO PERCENT (0%) commission lena kanoonan laagu hai! "
                    "Aadhatiya ya vyapari ka 4% se 6% commission khareedaar (buyer) dega, kisan nahi! "
                    "Agar koi aapse illegal commission ya katauti maangta hai, toh turant APMC Mandi Secretary se complaint karein ya computerized eNAM slip maangein."
                ),
                "step": "ENAM_LEGAL",
                "data": {"legal_rule": "0% Commission Protection"}
            }

        if any(w in text for w in ["parchi", "receipt", "tolai", "weighbridge", "vajan"]):
            return {
                "spoken_text": (
                    "Kisan bhai, eNAM portal ke tehat kisan ka haq hai ki usko digital weighbridge se vajan ki computerized parchi mile "
                    "aur uski payment 24 ghante ke andar direct bank khate me electronically jama ho. Kisi tarah ki manmaani katauti kanoonan aparadh hai."
                ),
                "step": "ENAM_LEGAL",
                "data": {"legal_rule": "Weighbridge Receipt Rights"}
            }

        return {
            "spoken_text": (
                "eNAM kanoon kisanon ko middleman loot se bachata hai: 0% farmer commission, electronic weighbridge receipt, aur direct bank payment. "
                "Aapko kisi mandi me kisi aadhatiye ya parchi par koi pareshani aa rahi hai kya?"
            ),
            "step": "ENAM_LEGAL",
            "data": {}
        }

    def _handle_agronomy_and_weather(self, text: str, session: Any) -> Optional[Dict[str, Any]]:
        agri_words = ["mausam", "weather", "baarish", "rain", "sinchai", "irrigation", "buwaai", "sowing", "beej", "seed", "upaj", "acreage"]
        if not any(w in text for w in agri_words):
            return None

        if any(w in text for w in ["sinchai", "paani"]):
            return {
                "spoken_text": (
                    "Kisan bhai, fasal me sinchai uski critical avasthaon par karna sabse laabhkari hota hai—jaise paudhe me phool aane ke samay aur "
                    "daana bharte waqt. Drip ya micro-sprinkler se 40% paani ki bachat hoti hai aur upaj me 25% vriddhi hoti hai."
                ),
                "step": "AGRONOMY",
                "data": {"topic": "Irrigation"}
            }

        if any(w in text for w in ["beej", "buwaai", "sowing"]):
            return {
                "spoken_text": (
                    "Kisan bhai, beej buwaai se pehle beej-upchar (Seed Treatment) zaroor karein. Faphund-rodhi dava jaise Trichoderma 5 gram per kg beej "
                    "ya Carbendazim 2 gram per kg beej se upcharit karne par jamm-pratishat 90% se upar rehta hai aur mitti janit rogon se bachav hota hai."
                ),
                "step": "AGRONOMY",
                "data": {"topic": "Seed Treatment"}
            }

        if any(w in text for w in ["mausam", "baarish", "rain"]):
            return {
                "spoken_text": (
                    f"Kisan bhai, {session.location_name} aur aas-paas ke ilaqe me mausam samanya bana hua hai. "
                    "Agar mandi maal le jaana hai toh tarpaulin se dhal kar rakhein aur nami ko 12% se neeche rakhein taaki acche bhav milein."
                ),
                "step": "WEATHER",
                "data": {"topic": "Weather"}
            }

        return None

    def _handle_chitchat_and_general(self, text: str, session: Any) -> Optional[Dict[str, Any]]:
        # WhatsApp Feature Query
        if any(w in text for w in ["whatsapp", "व्हाट्सएप", "व्हाट्सऐप", "whatsapp ka", "use kya", "use hai", "use kyu", "kya use", "kya kaam"]):
            phone_disp = session.phone_number if session.phone_number else "mobile"
            return {
                "spoken_text": (
                    f"Kisan Bhai ji! Kisan-Vaani ka WhatsApp feature aapke liye bohot madadgar hai. "
                    f"Aap jab bhi kisi fasal ka bhav dekhte hain, hum aapko seedhe aapke WhatsApp number (+91 {phone_disp}) "
                    f"par poora digital hisaab bhej dete hain—jisme sabse uncha mandi rate, gaadi ka diesel kharcha, "
                    f"aur aadhatiya commission zero percent (0%) ki eNAM kanooni receipt shaamil hoti hai! "
                    f"Ise aap mandi me aadhatiye ko dikha kar poora haq le sakte hain."
                ),
                "step": "OPEN_CONVERSATION",
                "data": {"feature": "WhatsApp Advisory"}
            }

        # Greetings in Hindi / Hinglish / English
        if any(w in text for w in ["namaste", "pranam", "ram ram", "kisan vaani", "hello", "hi", "नमस्ते", "प्रणाम", "राम राम", "जय जवान", "जय किसान", "हेलो"]):
            return {
                "spoken_text": (
                    f"Namaste {session.farmer_name} ji! Main Kisan-Vaani hoon—Gnani AI dwara chalit aapka personal kheti advisor. "
                    f"Aap mujhse kisi bhi fasal ka taaza mandi rate, bimari ki dawai, khad-sinchai ya sarkari yojanaon ke bare me pooch sakte hain. "
                    f"Batayein aaj kaunsi fasal ya suvidha par baat karein?"
                ),
                "step": "OPEN_CONVERSATION",
                "data": {}
            }

        # Gratitude
        if any(w in text for w in ["dhanyawad", "shukriya", "thanks", "theek hai", "achha", "धन्यवाद", "शुक्रिया", "ठीक है", "अच्छा"]):
            return {
                "spoken_text": (
                    f"Bahut-bahut dhanyawad {session.farmer_name} ji! Annadata ki seva karna hi hamara sankalp hai. "
                    f"Jab bhi mandi bhav ya kheti me koi zaroorat ho, bas ek aawaz lagayein. Jai Jawan, Jai Kisan!"
                ),
                "step": "FINISHED",
                "data": {}
            }

        # Identity & Capabilities
        if any(w in text for w in ["kaun ho", "kya karte ho", "kya kar sakte ho", "help", "madad", "कौन हो", "तुम कौन", "क्या करते"]):
            return {
                "spoken_text": (
                    f"Main Kisan-Vaani hoon—aapka sovereign voice kheti aur mandi advisor! "
                    f"Main aapko live mandi rates, diesel kharcha katne ke baad net munafa, "
                    f"fasal ki bimari ka ilaj aur eNAM zero percent commission adhikar batata hoon. "
                    f"Aap bol kar kuch bhi pooch sakte hain!"
                ),
                "step": "OPEN_CONVERSATION",
                "data": {}
            }

        return None

    def _generate_open_agri_response(self, text: str, session: Any) -> Dict[str, Any]:
        """Intelligent voice-first Indic generative reasoning for open questions."""
        f_name = session.farmer_name or "Kisan Bhai"
        clean = text.strip()

        # 1. Try scientific Agri-RAG knowledge base first
        rag_res = agri_rag.answer_query(clean, f_name)
        if rag_res:
            return rag_res

        # 2. Crop mentions inside free text
        if any(w in clean for w in ["tamatar", "टमाटर", "tomato"]):
            return {
                "spoken_text": f"{f_name} ji, tamatar ka bhav aaj lagbhag ₹1,550 se ₹1,850 prati quintal chal raha hai. Aapke paas bechne ke liye kitne crates ya quintal tamatar hain?",
                "step": "COMMODITY_ANSWERED",
                "data": {"commodity": "tomato"}
            }
        if any(w in clean for w in ["pyaaz", "kanda", "प्याज", "कांदा", "onion"]):
            return {
                "spoken_text": f"{f_name} ji, pyaaz ka bhav Lasalgaon aur Nashik mandiyon me ₹2,450 se ₹2,750 prati quintal hai. Aapke paas kitne katte maal taiyar hai?",
                "step": "COMMODITY_ANSWERED",
                "data": {"commodity": "onion"}
            }
        if any(w in clean for w in ["gehun", "gehu", "गेहूं", "wheat"]):
            return {
                "spoken_text": f"{f_name} ji, gehun ka taaza mandi bhav ₹2,580 se ₹2,720 prati quintal chal raha hai jo MSP se upar hai. Kitna quintal bechna chahte hain?",
                "step": "COMMODITY_ANSWERED",
                "data": {"commodity": "wheat"}
            }

        # General helpful answer
        return {
            "spoken_text": (
                f"{f_name} ji, kheti aur mandi vyapar me sabse behtar munafa paane ke liye "
                f"aap mujhse kisi bhi fasal ka taaza mandi bhav, bechne ka sahi samay, bimari ki dawai, ya eNAM kanoon pooch sakte hain. "
                f"Aap kaunsi fasal par baat karna chahte hain?"
            ),
            "step": "OPEN_CONVERSATION",
            "data": {"user_query": clean}
        }

agri_engine = AgriIntelligenceEngine()
