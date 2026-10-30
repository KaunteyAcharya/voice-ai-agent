"""Parsing and formatting helpers for money, dates, times and phone numbers.

The LLM passes tool arguments the way the caller said them ("90 lakh", "kal",
"शाम 5 बजे"), so the tools normalise everything here instead of trusting the
model to convert units. Everything is pure Python and unit tested.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time, timedelta, timezone

from listings import CRORE, LAKH

# India Standard Time. A fixed offset avoids needing the tzdata package on Windows.
IST = timezone(timedelta(hours=5, minutes=30), name="IST")

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def now_ist() -> datetime:
    return datetime.now(IST)


def today_ist() -> date:
    return now_ist().date()


def fold(text: str) -> str:
    """Normalise Unicode and drop the Devanagari nukta so "करोड़" and "करोड" compare equal."""
    return unicodedata.normalize("NFC", str(text)).replace("़", "")


def _clean(text: str) -> str:
    return " ".join(fold(text).translate(_DEVANAGARI_DIGITS).lower().replace(",", "").split())


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------

_UNIT_PATTERNS = [
    (CRORE, r"crores?|cr\b|करोड़|करोड"),
    (LAKH, r"lakhs?|lacs?|lac\b|l\b|लाख"),
    (1000, r"thousands?|k\b|हज़ार|हजार"),
]
_WORD_NUMBERS = {
    "sava": 1.25, "सवा": 1.25,
    "dedh": 1.5, "डेढ": 1.5,
    "dhai": 2.5, "adhai": 2.5, "ढाई": 2.5,
}


def parse_amount(value: object, purpose: str | None = None) -> int | None:
    """Turn "90 lakh", "1.2 crore", "1 crore 20 lakh", "25k", 9000000 into rupees.

    A bare small number is read in the unit people use for that purpose:
    lakh for buying (``90`` -> 90 lakh) and thousand for renting (``25`` -> 25,000).
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return _apply_default_unit(float(value), purpose)

    text = _clean(str(value))
    for word, number in _WORD_NUMBERS.items():
        text = re.sub(rf"(?<!\w){re.escape(word)}(?!\w)", str(number), text)
    text = re.sub(r"₹|rs\.?|rupees?|रुपये|रुपए|inr", " ", text)

    total = 0.0
    found_unit = False
    for multiplier, unit_pattern in _UNIT_PATTERNS:
        for match in re.finditer(rf"(\d+(?:\.\d+)?)\s*(?:{unit_pattern})", text):
            total += float(match.group(1)) * multiplier
            found_unit = True
        text = re.sub(rf"(\d+(?:\.\d+)?)\s*(?:{unit_pattern})", " ", text)

    if found_unit:
        # Pick up a trailing plain number, e.g. "1 crore 20" -> treat "20" as lakh.
        rest = re.findall(r"\d+(?:\.\d+)?", text)
        if rest and total >= CRORE:
            total += float(rest[0]) * LAKH
        return int(round(total))

    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    if not numbers:
        return None
    return _apply_default_unit(float(numbers[0]), purpose)


def _apply_default_unit(number: float, purpose: str | None) -> int:
    if number < 1000:
        if purpose == "rent":
            return int(round(number * 1000))
        if purpose == "buy" or purpose is None:
            return int(round(number * LAKH))
    return int(round(number))


def format_amount_spoken(rupees: int, lang: str) -> str:
    """Speech-friendly Indian amount: "1 crore 25 lakh rupees" / "1 करोड़ 25 लाख रुपये"."""
    words = {
        "en": ("crore", "lakh", "thousand", "rupees"),
        "hi": ("करोड़", "लाख", "हज़ार", "रुपये"),
    }[lang]
    crore_w, lakh_w, thousand_w, rupees_w = words
    rupees = int(round(rupees))
    parts: list[str] = []
    crores, rest = divmod(rupees, CRORE)
    if crores:
        parts.append(f"{crores} {crore_w}")
    lakhs, rest = divmod(rest, LAKH)
    if lakhs:
        parts.append(f"{lakhs} {lakh_w}")
    thousands, rest = divmod(rest, 1000)
    # Big amounts are rounded to the nearest thousand when spoken.
    if crores or lakhs:
        if rest >= 500:
            thousands += 1
        rest = 0
    if thousands:
        parts.append(f"{thousands} {thousand_w}")
    if rest:
        parts.append(str(rest))
    if not parts:
        parts.append("0")
    return " ".join(parts) + f" {rupees_w}"


def format_amount_display(rupees: int, purpose: str | None = None) -> str:
    """Compact amount for UI cards: ₹95 L, ₹1.25 Cr, ₹28,000/mo."""
    if purpose == "rent":
        return f"₹{_indian_grouping(rupees)}/mo"
    if rupees >= CRORE:
        return f"₹{rupees / CRORE:.2f}".rstrip("0").rstrip(".") + " Cr"
    if rupees >= LAKH:
        return f"₹{rupees / LAKH:.2f}".rstrip("0").rstrip(".") + " L"
    return f"₹{_indian_grouping(rupees)}"


def _indian_grouping(n: int) -> str:
    s = str(int(round(n)))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups + [tail])


# ---------------------------------------------------------------------------
# Dates and times
# ---------------------------------------------------------------------------

_WEEKDAYS = [
    ("monday", "mon", "somvar", "somwar", "सोमवार"),
    ("tuesday", "tue", "mangalvar", "mangalwar", "मंगलवार"),
    ("wednesday", "wed", "budhvar", "budhwar", "बुधवार"),
    ("thursday", "thu", "guruvar", "guruwar", "brihaspativar", "गुरुवार", "बृहस्पतिवार", "वीरवार"),
    ("friday", "fri", "shukravar", "shukrawar", "शुक्रवार"),
    ("saturday", "sat", "shanivar", "shaniwar", "शनिवार"),
    ("sunday", "sun", "ravivar", "raviwar", "itvaar", "रविवार", "इतवार"),
]
_MONTHS = [
    ("january", "jan", "जनवरी"),
    ("february", "feb", "फ़रवरी", "फरवरी"),
    ("march", "mar", "मार्च"),
    ("april", "apr", "अप्रैल"),
    ("may", "मई"),
    ("june", "jun", "जून"),
    ("july", "jul", "जुलाई"),
    ("august", "aug", "अगस्त"),
    ("september", "sep", "sept", "सितंबर", "सितम्बर"),
    ("october", "oct", "अक्टूबर", "अक्तूबर"),
    ("november", "nov", "नवंबर", "नवम्बर"),
    ("december", "dec", "दिसंबर", "दिसम्बर"),
]
_RELATIVE_DAYS = [
    (2, ("day after tomorrow", "parso", "parson", "परसों", "परसो")),
    (1, ("tomorrow", "kal", "कल", "aavtikale", "aavti kale", "આવતીકાલે")),
    (0, ("today", "aaj", "आज", "tonight")),
]

WEEKDAY_NAMES = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "hi": ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"],
}
MONTH_NAMES = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"],
    "hi": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त",
           "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
}


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text) is not None


def parse_visit_date(value: object, today: date | None = None) -> date | None:
    """Understand "2026-10-18", "18/10", "18 October", "kal", "परसों", "Saturday", "next shanivar"."""
    if value is None:
        return None
    today = today or today_ist()
    text = _clean(str(value))
    if not text:
        return None

    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = re.search(r"\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\b", text)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else None
        if year is not None and year < 100:
            year += 2000
        return _resolve_day_month(day, month, year, today)

    for month_index, names in enumerate(_MONTHS, start=1):
        for name in names:
            if _has_word(text, name):
                m = re.search(r"\b(\d{1,2})\b", text)
                if m:
                    return _resolve_day_month(int(m.group(1)), month_index, None, today)

    for offset, words in _RELATIVE_DAYS:
        if any(_has_word(text, w) for w in words):
            return today + timedelta(days=offset)

    for weekday, names in enumerate(_WEEKDAYS):
        if any(_has_word(text, n) for n in names):
            days_ahead = (weekday - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            if any(_has_word(text, w) for w in ("next", "agle", "agla", "अगले", "अगला")) and days_ahead < 7:
                # "next Saturday" said on a Wednesday is ambiguous; most people mean
                # the coming one, so only skip ahead when it's within two days.
                if days_ahead <= 2:
                    days_ahead += 7
            return today + timedelta(days=days_ahead)

    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _resolve_day_month(day: int, month: int, year: int | None, today: date) -> date | None:
    if year is not None:
        return _safe_date(year, month, day)
    candidate = _safe_date(today.year, month, day)
    if candidate is not None and candidate < today:
        candidate = _safe_date(today.year + 1, month, day)
    return candidate


_MORNING = ("am", "a.m", "a.m.", "morning", "subah", "सुबह")
_AFTERNOON = ("pm", "p.m", "p.m.", "afternoon", "evening", "dopahar", "dopehar", "shaam", "sham",
              "दोपहर", "शाम", "raat", "रात", "night")


def parse_visit_time(value: object) -> time | None:
    """Understand "11 am", "4:30 pm", "16:00", "शाम 5 बजे", "subah 11 baje", "noon"."""
    if value is None:
        return None
    text = _clean(str(value))
    if not text:
        return None
    if _has_word(text, "noon") or _has_word(text, "midday"):
        return time(12, 0)

    m = re.search(r"(\d{1,2})(?:[:.](\d{2}))?", text)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    if hour > 23 or minute > 59:
        return None

    is_pm = any(w in text for w in _AFTERNOON)
    is_am = any(_has_word(text, w) for w in _MORNING) or "सुबह" in text
    if hour <= 12:
        if is_pm and hour < 12:
            hour += 12
        elif is_am and hour == 12:
            hour = 0
        elif not is_am and not is_pm and 1 <= hour <= 7:
            # Site visits happen during the day: "4 baje" means 4 PM.
            hour += 12
    return time(hour, minute)


def format_date_spoken(d: date, lang: str) -> str:
    return f"{WEEKDAY_NAMES[lang][d.weekday()]}, {d.day} {MONTH_NAMES[lang][d.month - 1]}"


def format_time_spoken(t: time, lang: str) -> str:
    hour12 = t.hour % 12 or 12
    clock = f"{hour12}" if t.minute == 0 else f"{hour12}:{t.minute:02d}"
    if lang == "hi":
        if t.hour < 12:
            period = "सुबह"
        elif t.hour < 16:
            period = "दोपहर"
        elif t.hour < 20:
            period = "शाम"
        else:
            period = "रात"
        return f"{period} {clock} बजे"
    return f"{clock} {'AM' if t.hour < 12 else 'PM'}"


# ---------------------------------------------------------------------------
# Phone numbers
# ---------------------------------------------------------------------------


def normalize_phone(value: object) -> str | None:
    """Return a 10-digit Indian mobile number, or None if it isn't one."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value).translate(_DEVANAGARI_DIGITS))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return digits
    return None


def format_phone_display(phone: str) -> str:
    return f"+91 {phone[:5]} {phone[5:]}"
