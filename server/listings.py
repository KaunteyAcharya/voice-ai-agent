"""Fictional property listings for Tatsat Real Estate (Ahmedabad / Gandhinagar).

Every listing, price and description here is made up for the demo. Areas are real
neighbourhoods so the conversation sounds natural.

Prices are stored in rupees: the full sale price for "buy" listings and the
monthly rent for "rent" listings.
"""

from __future__ import annotations

LAKH = 100_000
CRORE = 10_000_000

# Canonical area names plus the spellings people (and Whisper) commonly produce,
# in both Latin and Devanagari script. Used for fuzzy area matching.
AREA_ALIASES: dict[str, list[str]] = {
    "Satellite": ["satellite", "satelite", "sattelite", "सैटेलाइट", "सेटेलाइट"],
    "Bopal": ["bopal", "bopaal", "south bopal", "बोपल", "बोपाल"],
    "Prahlad Nagar": ["prahlad nagar", "prahladnagar", "prahlad", "प्रह्लाद नगर", "प्रहलाद नगर", "प्रह्लादनगर"],
    "SG Highway": ["sg highway", "s g highway", "s.g. highway", "sg road", "एसजी हाईवे", "एस जी हाईवे", "एसजी हाइवे"],
    "Thaltej": ["thaltej", "thaltej road", "थलतेज", "थलतेज़"],
    "Chandkheda": ["chandkheda", "chand kheda", "चांदखेड़ा", "चांदखेडा", "चाँदखेड़ा"],
    "Gandhinagar Sector 21": [
        "gandhinagar", "gandhinagar sector 21", "sector 21", "गांधीनगर", "गाँधीनगर", "सेक्टर 21", "सेक्टर इक्कीस",
    ],
}

AREA_HI: dict[str, str] = {
    "Satellite": "सैटेलाइट",
    "Bopal": "बोपल",
    "Prahlad Nagar": "प्रह्लाद नगर",
    "SG Highway": "एसजी हाईवे",
    "Thaltej": "थलतेज",
    "Chandkheda": "चांदखेड़ा",
    "Gandhinagar Sector 21": "गांधीनगर सेक्टर 21",
}

AMENITY_HI: dict[str, str] = {
    "covered parking": "कवर्ड पार्किंग",
    "parking": "पार्किंग",
    "lift": "लिफ़्ट",
    "gym": "जिम",
    "swimming pool": "स्विमिंग पूल",
    "clubhouse": "क्लबहाउस",
    "24x7 security": "24x7 सिक्योरिटी",
    "power backup": "पावर बैकअप",
    "garden": "गार्डन",
    "private garden": "प्राइवेट गार्डन",
    "kids play area": "किड्स प्ले एरिया",
    "modular kitchen": "मॉड्यूलर किचन",
    "terrace": "टैरेस",
    "near metro": "मेट्रो के पास",
    "pet friendly": "पेट फ्रेंडली",
}

FURNISHING_HI = {
    "unfurnished": "अनफर्निश्ड",
    "semi-furnished": "सेमी-फर्निश्ड",
    "fully furnished": "फुली फर्निश्ड",
}

TYPE_HI = {"apartment": "अपार्टमेंट", "villa": "विला", "bungalow": "बंगला"}

LISTINGS: list[dict] = [
    {
        "id": "SH-101",
        "title": {"en": "Shaligram Heights", "hi": "शालिग्राम हाइट्स"},
        "area": "Satellite",
        "type": "apartment",
        "bhk": 3,
        "purpose": "buy",
        "price": 95 * LAKH,
        "size_sqft": 1650,
        "furnishing": "semi-furnished",
        "amenities": ["covered parking", "lift", "gym", "24x7 security", "power backup"],
        "possession": {"en": "Ready to move", "hi": "रेडी टू मूव"},
        "description": {
            "en": "Corner flat on the 7th floor near Jodhpur Cross Roads, east facing with two balconies.",
            "hi": "जोधपुर चार रास्ता के पास सातवें फ़्लोर पर कॉर्नर फ़्लैट, ईस्ट फ़ेसिंग, दो बालकनी के साथ।",
        },
        "gradient": ["#ff9a76", "#f6416c"],
    },
    {
        "id": "SH-102",
        "title": {"en": "Sapna Greens", "hi": "सपना ग्रीन्स"},
        "area": "Bopal",
        "type": "apartment",
        "bhk": 3,
        "purpose": "buy",
        "price": 82 * LAKH,
        "size_sqft": 1550,
        "furnishing": "unfurnished",
        "amenities": ["covered parking", "lift", "swimming pool", "clubhouse", "kids play area", "24x7 security"],
        "possession": {"en": "Ready to move", "hi": "रेडी टू मूव"},
        "description": {
            "en": "Gated society with a large central garden, five minutes from Bopal crossroads.",
            "hi": "बड़े सेंट्रल गार्डन वाली गेटेड सोसाइटी, बोपल सर्कल से पाँच मिनट दूर।",
        },
        "gradient": ["#43e97b", "#38a169"],
    },
    {
        "id": "SH-103",
        "title": {"en": "Aangan Residency", "hi": "आँगन रेज़िडेंसी"},
        "area": "Bopal",
        "type": "apartment",
        "bhk": 2,
        "purpose": "buy",
        "price": 58 * LAKH,
        "size_sqft": 1150,
        "furnishing": "unfurnished",
        "amenities": ["parking", "lift", "gym", "power backup"],
        "possession": {"en": "Under construction, possession December 2027", "hi": "अंडर कंस्ट्रक्शन, दिसंबर 2027 में पज़ेशन"},
        "description": {
            "en": "New launch with flexible payment plan, close to schools and the BRTS route.",
            "hi": "नया प्रोजेक्ट, आसान पेमेंट प्लान, स्कूल और BRTS रूट के पास।",
        },
        "gradient": ["#4facfe", "#00c6fb"],
    },
    {
        "id": "SH-104",
        "title": {"en": "Riverview Regency", "hi": "रिवरव्यू रीजेंसी"},
        "area": "Prahlad Nagar",
        "type": "apartment",
        "bhk": 4,
        "purpose": "buy",
        "price": 210 * LAKH,
        "size_sqft": 2600,
        "furnishing": "semi-furnished",
        "amenities": ["covered parking", "lift", "swimming pool", "gym", "clubhouse", "24x7 security", "power backup"],
        "possession": {"en": "Ready to move", "hi": "रेडी टू मूव"},
        "description": {
            "en": "Premium high-rise apartment near Prahlad Nagar garden with a private lift lobby.",
            "hi": "प्रह्लाद नगर गार्डन के पास प्रीमियम हाई-राइज़ अपार्टमेंट, प्राइवेट लिफ़्ट लॉबी के साथ।",
        },
        "gradient": ["#a18cd1", "#6b46c1"],
    },
    {
        "id": "SH-105",
        "title": {"en": "Skyline 32", "hi": "स्काईलाइन 32"},
        "area": "SG Highway",
        "type": "apartment",
        "bhk": 3,
        "purpose": "buy",
        "price": 125 * LAKH,
        "size_sqft": 1850,
        "furnishing": "semi-furnished",
        "amenities": ["covered parking", "lift", "gym", "swimming pool", "clubhouse", "near metro"],
        "possession": {"en": "Ready to move", "hi": "रेडी टू मूव"},
        "description": {
            "en": "Thirty-two storey tower off SG Highway with city views and quick access to offices.",
            "hi": "एसजी हाईवे के पास 32 फ़्लोर का टावर, बढ़िया सिटी व्यू, ऑफ़िस भी पास में।",
        },
        "gradient": ["#30cfd0", "#330867"],
    },
    {
        "id": "SH-106",
        "title": {"en": "Banyan Bungalows", "hi": "बनियन बंगलोज़"},
        "area": "Thaltej",
        "type": "bungalow",
        "bhk": 4,
        "purpose": "buy",
        "price": 350 * LAKH,
        "size_sqft": 3800,
        "furnishing": "fully furnished",
        "amenities": ["covered parking", "private garden", "terrace", "24x7 security", "power backup", "modular kitchen"],
        "possession": {"en": "Ready to move", "hi": "रेडी टू मूव"},
        "description": {
            "en": "Independent bungalow with a private garden and terrace in a quiet lane of Thaltej.",
            "hi": "थलतेज की शांत लेन में प्राइवेट गार्डन और टैरेस वाला इंडिपेंडेंट बंगला।",
        },
        "gradient": ["#f6d365", "#fda085"],
    },
    {
        "id": "SH-107",
        "title": {"en": "Shubh Labh Flats", "hi": "शुभ लाभ फ़्लैट्स"},
        "area": "Chandkheda",
        "type": "apartment",
        "bhk": 2,
        "purpose": "buy",
        "price": 42 * LAKH,
        "size_sqft": 1050,
        "furnishing": "unfurnished",
        "amenities": ["parking", "lift", "24x7 security", "near metro"],
        "possession": {"en": "Ready to move", "hi": "रेडी टू मूव"},
        "description": {
            "en": "Affordable two bedroom flat a short walk from the Chandkheda metro station.",
            "hi": "चांदखेड़ा मेट्रो स्टेशन से थोड़ी दूरी पर बजट फ्रेंडली 2 बेडरूम फ़्लैट।",
        },
        "gradient": ["#fbc2eb", "#a6c1ee"],
    },
    {
        "id": "SH-108",
        "title": {"en": "Capital Villas", "hi": "कैपिटल विलाज़"},
        "area": "Gandhinagar Sector 21",
        "type": "villa",
        "bhk": 3,
        "purpose": "buy",
        "price": 110 * LAKH,
        "size_sqft": 2200,
        "furnishing": "semi-furnished",
        "amenities": ["covered parking", "private garden", "clubhouse", "24x7 security", "kids play area"],
        "possession": {"en": "Possession in March 2027", "hi": "मार्च 2027 में पज़ेशन"},
        "description": {
            "en": "Duplex villa in a green, low-traffic sector of Gandhinagar, close to GIFT City road.",
            "hi": "गांधीनगर के ग्रीन और शांत सेक्टर में डुप्लेक्स विला, GIFT सिटी रोड के पास।",
        },
        "gradient": ["#84fab0", "#8fd3f4"],
    },
    {
        "id": "SH-109",
        "title": {"en": "Mansi Apartments", "hi": "मानसी अपार्टमेंट्स"},
        "area": "Satellite",
        "type": "apartment",
        "bhk": 2,
        "purpose": "rent",
        "price": 28_000,
        "size_sqft": 1100,
        "furnishing": "fully furnished",
        "amenities": ["parking", "lift", "24x7 security", "power backup", "modular kitchen"],
        "possession": {"en": "Available from 1 November", "hi": "1 नवंबर से अवेलेबल"},
        "description": {
            "en": "Fully furnished flat near Iscon Mall with AC in both bedrooms.",
            "hi": "इस्कॉन मॉल के पास फुली फर्निश्ड फ़्लैट, दोनों बेडरूम में एसी।",
        },
        "gradient": ["#ffecd2", "#fcb69f"],
    },
    {
        "id": "SH-110",
        "title": {"en": "Garden Court", "hi": "गार्डन कोर्ट"},
        "area": "Prahlad Nagar",
        "type": "apartment",
        "bhk": 3,
        "purpose": "rent",
        "price": 45_000,
        "size_sqft": 1750,
        "furnishing": "semi-furnished",
        "amenities": ["covered parking", "lift", "gym", "swimming pool", "24x7 security", "pet friendly"],
        "possession": {"en": "Available immediately", "hi": "अभी अवेलेबल"},
        "description": {
            "en": "Spacious family flat facing the garden, pets allowed.",
            "hi": "गार्डन फ़ेसिंग बड़ा फ़ैमिली फ़्लैट, पेट्स अलाउड हैं।",
        },
        "gradient": ["#c471f5", "#fa71cd"],
    },
    {
        "id": "SH-111",
        "title": {"en": "Orchid Villa", "hi": "ऑर्किड विला"},
        "area": "Bopal",
        "type": "villa",
        "bhk": 3,
        "purpose": "rent",
        "price": 55_000,
        "size_sqft": 2400,
        "furnishing": "fully furnished",
        "amenities": ["covered parking", "private garden", "clubhouse", "24x7 security", "power backup"],
        "possession": {"en": "Available immediately", "hi": "अभी अवेलेबल"},
        "description": {
            "en": "Furnished villa in a gated community with a private garden and two car parks.",
            "hi": "गेटेड कम्युनिटी में फर्निश्ड विला, प्राइवेट गार्डन और दो कार पार्किंग के साथ।",
        },
        "gradient": ["#667eea", "#764ba2"],
    },
    {
        "id": "SH-112",
        "title": {"en": "Metro Nest", "hi": "मेट्रो नेस्ट"},
        "area": "Chandkheda",
        "type": "apartment",
        "bhk": 1,
        "purpose": "rent",
        "price": 12_000,
        "size_sqft": 600,
        "furnishing": "semi-furnished",
        "amenities": ["parking", "lift", "near metro"],
        "possession": {"en": "Available from 15 November", "hi": "15 नवंबर से अवेलेबल"},
        "description": {
            "en": "Compact one bedroom flat, ideal for working professionals, next to the metro.",
            "hi": "कॉम्पैक्ट 1 बेडरूम फ़्लैट, वर्किंग प्रोफ़ेशनल्स के लिए बढ़िया, मेट्रो के बिल्कुल पास।",
        },
        "gradient": ["#89f7fe", "#66a6ff"],
    },
]

LISTINGS_BY_ID: dict[str, dict] = {listing["id"]: listing for listing in LISTINGS}
