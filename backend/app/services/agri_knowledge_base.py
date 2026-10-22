"""
Agricultural Knowledge Base (AKB) for Kisan-Vaani.
Curated from official ICAR, KVK, and State Agricultural University Package of Practices (POP).
Provides factual knowledge chunks for semantic RAG retrieval.
"""

from typing import List, Dict, Any

AGRI_KNOWLEDGE_DOCUMENTS: List[Dict[str, Any]] = [
    # ==========================================
    # CROP DISEASES & PEST MANAGEMENT (ICAR/POP)
    # ==========================================
    {
        "id": "doc_tomato_leaf_curl",
        "category": "disease_pest",
        "crop": "tomato",
        "topic": "Leaf Curl Virus (पर्ण कुंचन रोग)",
        "keywords": ["leaf curl", "tamatar", "mud rahe", "pila", "peele patte", "safed makhi", "whitefly", "पर्ण कुंचन", "पत्ते मुड़ना"],
        "content": (
            "टमाटर में पत्तों का ऊपर या नीचे की ओर मुड़ना और पीला पड़ना लीफ कर्ल वायरस (Leaf Curl Virus) के लक्षण हैं। "
            "यह वायरस सफेद मक्खी (Whitefly) द्वारा फैलता है। "
            "रोकथाम और उपचार: 1) सबसे पहले रोगग्रस्त पौधों को उखाड़कर खेत से दूर नष्ट करें। "
            "2) सफेद मक्खी के नियंत्रण के लिए इमिडाक्लोप्रिड (Imidacloprid 17.8 SL) 1 मिलीलीटर प्रति 3 लीटर पानी में, "
            "या एसिटामिप्रिड (Acetamiprid 20 SP) 1 ग्राम प्रति 3 लीटर पानी में घोलकर छिड़काव करें। "
            "3) जैविक उपचार: नीम का तेल (1500 PPM) 3 से 4 मिलीलीटर प्रति लीटर पानी में मिलाकर 10 दिन के अंतराल पर छिड़कें।"
        )
    },
    {
        "id": "doc_tomato_fruit_borer",
        "category": "disease_pest",
        "crop": "tomato",
        "topic": "Tomato Fruit Borer / Sundi (फल छेदक इल्ली)",
        "keywords": ["fruit borer", "tamatar borer", "chhed", "sundi", "illi", "tamatar me keeda", "फल छेदक", "इल्ली", "सुंडी"],
        "content": (
            "टमाटर का फल छेदक कीट (Helicoverpa armigera) फलों में छेद करके गूदा खा जाता है जिससे फल सड़ जाते हैं। "
            "नियंत्रण: 1) कोराजन (Chlorantraniliprole 18.5 SC) 60 मिलीलीटर प्रति 200 लीटर पानी (0.3 ml/L) में, "
            "या एमामेक्टिन बेंजोएट (Emamectin Benzoate 5 SG) 4 ग्राम प्रति 10 लीटर पानी में मिलाकर शाम के समय छिड़काव करें। "
            "2) जैविक नियंत्रण: खेत में प्रति एकड़ 4 से 5 फेरोमोन ट्रैप (Pheromone Traps) लगाएं।"
        )
    },
    {
        "id": "doc_potato_early_late_blight",
        "category": "disease_pest",
        "crop": "potato",
        "topic": "Potato Early & Late Blight (आलू का झुलसा रोग)",
        "keywords": ["blight", "aloo jhulsa", "pacheti jhulsa", "ageti jhulsa", "black spots", "faphund", "झुलसा", "आलू"],
        "content": (
            "आलू में पछेती झुलसा (Late Blight) फफूंद से होता है, जिसमें पत्तियों पर भूरे-काले पानीदार धब्बे बनते हैं और पौधे सड़ने लगते हैं। "
            "उपचार: 1) लक्षण दिखते ही मैंकोजेब (Mancozeb 75 WP) 2.5 ग्राम प्रति लीटर पानी, या "
            "2) गंभीर अवस्था में साइमोक्सानिल + मैंकोजेब (Curzate M8) 2.5 ग्राम प्रति लीटर, या रिडोमिल गोल्ड (Metalaxyl + Mancozeb) 2 ग्राम प्रति लीटर पानी में छिड़कें। "
            "खेत में जलभराव न होने दें।"
        )
    },
    {
        "id": "doc_onion_thrips_purple_blotch",
        "category": "disease_pest",
        "crop": "onion",
        "topic": "Onion Thrips & Purple Blotch (प्याज में थ्रिप्स और बैंगनी धब्बा रोग)",
        "keywords": ["onion thrips", "pyaaz thrips", "baingani dhabba", "purple blotch", "chandi jaise dhabbe", "प्याज थ्रिप्स"],
        "content": (
            "प्याज में थ्रिप्स पत्तियों का रस चूसते हैं जिससे पत्तियों पर चांदी जैसे सफेद धब्बे बनते हैं, और पत्तियां मुड़ने लगती हैं। "
            "बैंगनी धब्बा रोग में पत्तियों पर बैंगनी रंग के चकत्ते बनते हैं। "
            "उपचार: 1) थ्रिप्स के लिए फिप्रोनिल (Fipronil 5 SC) 2 मिलीलीटर प्रति लीटर पानी में, "
            "2) बैंगनी धब्बे के लिए प्रोपिकोनाजोल (Tilt 25 EC) 1 मिलीलीटर प्रति लीटर पानी में मिलाकर छिड़काव करें। "
            "घोल में स्टीकर (Sticker/Spreader) 0.5 मिली प्रति लीटर जरूर मिलाएं क्योंकि प्याज की पत्तियां चिकनी होती हैं।"
        )
    },
    {
        "id": "doc_wheat_yellow_rust_termite",
        "category": "disease_pest",
        "crop": "wheat",
        "topic": "Wheat Yellow Rust & Termite (गेहूं का पीला रतुआ और दीमक)",
        "keywords": ["wheat rust", "gehun pila ratua", "yellow rust", "deemak", "termite", "गेहूं रतुआ", "दीमक"],
        "content": (
            "गेहूं में पीला रतुआ (Yellow Rust) में पत्तियों पर हल्दी जैसा पीला पाउडर चिपक जाता है। "
            "उपचार: प्रोपिकोनाजोल (Tilt 25 EC) 1 मिलीलीटर प्रति लीटर पानी (200 मिली प्रति एकड़ 200 लीटर पानी में) का छिड़काव तुरंत करें। "
            "दीमक के नियंत्रण के लिए क्लोरपायरीफॉस (Chlorpyrifos 20 EC) 1 से 1.5 लीटर प्रति एकड़ सिंचाई के पानी के साथ चलाएं।"
        )
    },
    {
        "id": "doc_mustard_aphid_white_rust",
        "category": "disease_pest",
        "crop": "mustard",
        "topic": "Mustard Aphid & White Rust (सरसों का माहू/चेपा और सफेद रतुआ)",
        "keywords": ["mustard aphid", "sarson mahu", "chepa", "white rust", "sarso keede", "सरसों माहू", "चेपा"],
        "content": (
            "सरसों में माहू (Aphid/Chepa) जनवरी-फरवरी में फूलों और फलियों का रस चूसकर भारी नुकसान करता है। "
            "उपचार: डायमेथोएट (Rogor 30 EC) 1.5 मिलीलीटर प्रति लीटर पानी, या "
            "इमिडाक्लोप्रिड 17.8 SL 1 मिलीलीटर प्रति 3 लीटर पानी में घोलकर छिड़कें। "
            "सफेद रतुआ (White Rust) के लिए मैन्कोजेब 2 ग्राम प्रति लीटर पानी में छिड़कें।"
        )
    },
    {
        "id": "doc_cotton_pink_bollworm",
        "category": "disease_pest",
        "crop": "cotton",
        "topic": "Cotton Pink Bollworm (कपास की गुलाबी सुंडी)",
        "keywords": ["pink bollworm", "kapas gulabi sundi", "cotton pest", "टिंडा छेदक", "गुलाबी सुंडी"],
        "content": (
            "कपास की गुलाबी सुंडी (Pink Bollworm) फूलों को अंदर से बंद कर देती है (Rosette flower) और टिंडों में छेद कर देती है। "
            "उपचार: 1) फूल आने के समय प्रोफेनोफॉस (Profenofos 50 EC) 2 मिलीलीटर प्रति लीटर पानी में, "
            "या स्पाइनोसैड (Spinosad 45 SC) 0.5 मिलीलीटर प्रति लीटर पानी में छिड़कें। "
            "2) फेरोमोन ट्रैप 5 से 8 प्रति एकड़ निगरानी के लिए लगाएं।"
        )
    },
    {
        "id": "doc_paddy_bph_stem_borer",
        "category": "disease_pest",
        "crop": "paddy",
        "topic": "Paddy Brown Plant Hopper (BPH) & Stem Borer (धान का भूरा फुदका और तना छेदक)",
        "keywords": ["paddy bph", "dhan bhura phudka", "tana chhedak", "stem borer", "dhan keede", "भूरा फुदका", "तना छेदक"],
        "content": (
            "धान में भूरा फुदका (BPH) पौधों के आधार से रस चूसता है जिससे पूरा खेत जलने जैसा (Hopper burn) दिखता है। "
            "तना छेदक में गोभ सूख जाती है (Dead heart) और बालियां सफेद निकलती हैं (White earhead)। "
            "उपचार: BPH के लिए पाइमेट्रोजिन (Pymetrozine 50 WG) 120 ग्राम प्रति एकड़, या ट्राईफ्लूमेजॉपिरिम (Trifluclomezopyrim 10 SC) 94 मिली प्रति एकड़ छिड़कें। "
            "तना छेदक के लिए कारटैप हाइड्रोक्लोराइड (Cartap 4G) 7 से 8 किलो प्रति एकड़ मिट्टी में डालें।"
        )
    },

    # ==========================================
    # CROP NUTRITION & FERTILIZER SCHEDULES
    # ==========================================
    {
        "id": "doc_fertilizer_urea_topdressing",
        "category": "fertilizer",
        "crop": "all",
        "topic": "Urea Top-Dressing & Nitrogen Management (यूरिया का सही प्रयोग)",
        "keywords": ["urea", "nitrogen", "top dressing", "peela pan", "peelapan", "यूरिया", "खाद", "नाइट्रोजन", "पीलापन", "पीले पत्ते"],
        "content": (
            "यूरिया में 46% नाइट्रोजन होता है जो पौधों की वनस्पति बढ़वार (वानस्पतिक वृद्धि) के लिए आवश्यक है। "
            "नियम: 1) यूरिया को कभी भी खेत में खड़ा पानी भरा होने पर या तेज धूप में न डालें। "
            "2) इसे 2 से 3 विभाजित खुराकों (Splits) में दें: पहली सिंचाई के बाद और कल्ले निकलते समय। "
            "3) प्रति एकड़ 30 से 45 किलो यूरिया एक बार में पर्याप्त है। नीम लेपित यूरिया का प्रयोग करें जिससे नाइट्रोजन धीरे-धीरे मिले।"
        )
    },
    {
        "id": "doc_fertilizer_dap_vs_npk",
        "category": "fertilizer",
        "crop": "all",
        "topic": "DAP vs NPK Basal Application (डीएपी और एनपीके बुवाई खाद)",
        "keywords": ["dap", "npk 12:32:16", "basal dose", "phosphorus", "डीएपी", "फास्फोरस", "बुवाई"],
        "content": (
            "डीएपी (18% N, 46% P) जड़ों के विकास और कल्ले फूटने के लिए बुवाई या रोपाई के समय ही खेत में 4-5 सेमी गहरा डाला जाता है। "
            "खड़ी फसल में ऊपर से डीएपी फेंकने से फास्फोरस पौधों को नहीं मिलता। "
            "विकल्प: डीएपी के स्थान पर NPK (12:32:16) 75 किलो प्रति एकड़ देना अधिक उत्तम है क्योंकि इसमें पोटाश भी होता है जो फसल को रोग और सूखे से बचाता है।"
        )
    },
    {
        "id": "doc_fertilizer_foliar_spray",
        "category": "fertilizer",
        "crop": "all",
        "topic": "Water Soluble Foliar Sprays (19:19:19, 0:52:34, 0:0:50)",
        "keywords": ["19:19:19", "0:52:34", "0:0:50", "foliar spray", "chhidkaw", "स्प्रे", "घुलनशील खाद"],
        "content": (
            "घुलनशील खादों का स्प्रे सीधे पत्तियों द्वारा तुरंत अवशोषित होता है: "
            "1) वानस्पतिक बढ़वार के समय: NPK 19:19:19 5 ग्राम प्रति लीटर (1 किलो प्रति एकड़ 200 लीटर पानी में)। "
            "2) फूल आने से ठीक पहले: NPK 0:52:34 (मोनो पोटैशियम फास्फेट) 5 ग्राम प्रति लीटर। इससे फूल झड़ने से रुकते हैं। "
            "3) फल या दाना भरते समय: पोटैशियम सल्फेट (0:0:50) 5 ग्राम प्रति लीटर। इससे दाना मोटा, चमकदार और वजनदार बनता है।"
        )
    },
    {
        "id": "doc_zinc_sulphur_deficiency",
        "category": "fertilizer",
        "crop": "all",
        "topic": "Zinc & Sulphur Micronutrients (धान का खैरा रोग, जिंक और सल्फर का महत्व)",
        "keywords": ["zinc", "sulphur", "khaira rog", "peele patte", "peelapan", "dhan me peelapan", "जिंक", "सल्फर", "खैरा रोग", "पीलापन", "पीले पत्ते"],
        "content": (
            "धान में जिंक की कमी से 'खैरा रोग' होता है जिसमें निचली पत्तियों पर कत्थई/भूरे रंग के धब्बे बनते हैं। "
            "उपचार: जिंक सल्फेट (21%) 5 किलो प्रति एकड़ बुवाई के समय मिट्टी में डालें, या "
            "चिलेटेड जिंक (Chelated Zinc EDTA 12%) 1 ग्राम प्रति लीटर पानी में घोलकर स्प्रे करें। "
            "तिलहन फसलों (सरसों, सोयाबीन, मूंगफली) में तेल की मात्रा बढ़ाने के लिए बेंटोनाइट सल्फर 10 किलो प्रति एकड़ अवश्य डालें।"
        )
    },

    # ==========================================
    # GOVERNMENT SCHEMES & ENAM ADVISORY
    # ==========================================
    {
        "id": "doc_enam_zero_commission",
        "category": "scheme_law",
        "crop": "all",
        "topic": "eNAM 0% Commission Legal Farmer Rights (ई-नाम शून्य प्रतिशत कमीशन कानून)",
        "keywords": ["enam", "commission", "aadhatiya", "cut", "dalali", "हक", "कमीशन", "ई-नाम", "दलाली"],
        "content": (
            "राष्ट्रीय कृषि बाजार (eNAM) और केंद्रीय कृषि विपणन नियमों के अनुसार: "
            "मंडी में व्यापारी (आढ़तिया) किसान की उपज पर किसी भी प्रकार का कमीशन या दलाली (Commission) नहीं काट सकता। "
            "मंडी कमीशन शून्य प्रतिशत (0%) है और आढ़त का भुगतान खरीदार (व्यापारी) को करना होता है, किसान को नहीं। "
            "यदि कोई आढ़तिया किसान के बिल से कमीशन काटता है, तो किसान सीधे मंडी सचिव (APMC Secretary) या ई-नाम पोर्टल पर शिकायत दर्ज करा सकता है।"
        )
    },
    {
        "id": "doc_pm_kisan_pmfby",
        "category": "scheme_law",
        "crop": "all",
        "topic": "PM-Kisan & PMFBY Crop Insurance (पीएम किसान और फसल बीमा योजना)",
        "keywords": ["pm kisan", "pmfby", "fasal bima", "kcc", "muavza", "पीएम किसान", "फसल बीमा", "मुआवजा"],
        "content": (
            "1) पीएम किसान सम्मान निधि: पात्र किसानों को प्रतिवर्ष ₹6,000 की राशि 3 समान किस्तों (₹2,000 प्रत्येक) में डीबीटी के माध्यम से बैंक खाते में दी जाती है। ई-केवाईसी (e-KYC) अनिवार्य है। "
            "2) प्रधानमंत्री फसल बीमा योजना (PMFBY): प्राकृतिक आपदा, बेमौसम बारिश, पाला या कीट प्रकोप से फसल नुकसान होने पर 72 घंटे के भीतर टोल-फ्री नंबर 14447 या PMFBY ऐप पर सूचना देना अनिवार्य है। "
            "प्रीमियम दर: खरीफ फसलों के लिए 2%, रबी फसलों के लिए 1.5%, और बागवानी फसलों के लिए 5% है।"
        )
    },
    {
        "id": "doc_kisan_credit_card_kcc",
        "category": "scheme_law",
        "crop": "all",
        "topic": "Kisan Credit Card (KCC) Low Interest Loans (किसान क्रेडिट कार्ड 4% ब्याज ऋण)",
        "keywords": ["kcc", "loan", "byaj", "karz", "credit card", "केसीसी", "ऋण", "ब्याज"],
        "content": (
            "किसान क्रेडिट कार्ड (KCC) योजना के तहत किसानों को खेती और पशुपालन के लिए ₹3 लाख तक का अल्पकालिक ऋण मात्र 4% वार्षिक प्रभावी ब्याज दर पर मिलता है (सामान्य ब्याज 7% होता है, जिसमें समय पर भुगतान करने पर सरकार द्वारा 3% ब्याज छूट/सबवेंशन मिलती है)। "
            "इसके लिए किसी बिचौलिए की जरूरत नहीं है, सीधे अपने नजदीकी बैंक शाखा में जमीन की खतौनी और आधार कार्ड देकर आवेदन करें।"
        )
    }
]
