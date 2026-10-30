"""Aditi's tools: property search, details, EMI, site-visit booking and language switching.

``PropertyDesk`` holds the business logic and is plain Python (unit tested in
``tests/``). ``build_tool_functions`` wraps it as Pipecat "direct functions":
the function signature and docstring become the tool schema the LLM sees, and
each call also pushes an RTVI server message so the browser can draw cards.
"""

from __future__ import annotations

import difflib
import math
import os
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time, timedelta
from pathlib import Path

from loguru import logger
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame
from pipecat.services.llm_service import FunctionCallParams

from bookings import BookingStore
from listings import (
    AMENITY_HI,
    AREA_ALIASES,
    AREA_HI,
    FURNISHING_HI,
    LISTINGS,
    LISTINGS_BY_ID,
    TYPE_HI,
)
from parsing import (
    IST,
    fold,
    format_amount_display,
    format_amount_spoken,
    format_date_spoken,
    format_phone_display,
    format_time_spoken,
    normalize_phone,
    parse_amount,
    parse_visit_date,
    parse_visit_time,
    today_ist,
)

SUPPORTED_LANGUAGES = ("en", "hi")
VISIT_OPEN = time(10, 0)
VISIT_CLOSE = time(18, 0)
MAX_RESULTS = 3

_default_store: BookingStore | None = None


def default_store() -> BookingStore:
    """The process-wide booking store: SQLite at BOOKINGS_DB (default data/tatsat.db)."""
    global _default_store
    if _default_store is None:
        path = os.getenv("BOOKINGS_DB") or str(Path(__file__).resolve().parent.parent / "data" / "tatsat.db")
        _default_store = BookingStore(path)
        _default_store.seed(today_ist())
    return _default_store


def normalize_code(value: object) -> str | None:
    """Turn "SH-2890", "sh 2890", "S H 2 8 9 0" or "2890" into "SH-2890"."""
    text = fold(str(value or "")).translate(str.maketrans("०१२३४५६७८९", "0123456789"))
    digits = "".join(ch for ch in text if ch in "0123456789")
    return f"SH-{digits[-4:]}" if len(digits) >= 4 else None


def normalize_purpose(value: object) -> str | None:
    text = fold(str(value or "")).lower()
    if any(w in text for w in ("rent", "lease", "kiray", "किराय", "भाड़", "भाड", "bhada")):
        return "rent"
    if any(w in text for w in ("buy", "purchase", "sale", "kharid", "खरीद", "ख़रीद", "own")):
        return "buy"
    return None


def match_area(value: object) -> str | None:
    """Map whatever the caller said to one of our canonical area names."""
    text = fold(str(value or "")).lower().strip()
    if not text:
        return None
    for canonical, aliases in AREA_ALIASES.items():
        for alias in aliases:
            alias = fold(alias).lower()
            if alias == text or alias in text or (len(text) >= 4 and text in alias):
                return canonical
    all_aliases = {fold(a).lower(): c for c, aliases in AREA_ALIASES.items() for a in aliases}
    close = difflib.get_close_matches(text, list(all_aliases), n=1, cutoff=0.72)
    return all_aliases[close[0]] if close else None


def normalize_property_id(value: object) -> str | None:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if digits:
        pid = f"SH-{digits[-3:]}"
        if pid in LISTINGS_BY_ID:
            return pid
    # The model sometimes passes the title instead of the id.
    text = fold(str(value or "")).lower()
    for listing in LISTINGS:
        if any(fold(t).lower() in text or text in fold(t).lower() for t in listing["title"].values() if text):
            return listing["id"]
    return None


def calculate_emi_amount(principal: float, annual_rate: float, years: float) -> float:
    months = int(round(years * 12))
    if months <= 0:
        raise ValueError("tenure must be positive")
    monthly_rate = annual_rate / 12 / 100
    if monthly_rate == 0:
        return principal / months
    factor = math.pow(1 + monthly_rate, months)
    return principal * monthly_rate * factor / (factor - 1)


class PropertyDesk:
    """Stateful helper for one call: knows the current language and today's date."""

    def __init__(
        self,
        language: str = "en",
        today: Callable[[], date] = today_ist,
        store: BookingStore | None = None,
    ):
        self.language = language if language in SUPPORTED_LANGUAGES else "en"
        self._today = today
        self.store = store or default_store()
        # What the caller showed interest in, for the follow-up message:
        # property id -> 1 (shown in a search), 2 (asked for details), 3 (booked a visit).
        self.interest: dict[str, int] = {}
        self.last_query: dict | None = None
        self.booked_codes: list[str] = []

    def note_interest(self, pid: str, level: int) -> None:
        self.interest[pid] = max(self.interest.get(pid, 0), level)

    # -- formatting ---------------------------------------------------------

    def _summary(self, listing: dict) -> dict:
        lang = self.language
        hi = lang == "hi"
        return {
            "id": listing["id"],
            "title": listing["title"][lang],
            "area": AREA_HI[listing["area"]] if hi else listing["area"],
            "type": TYPE_HI[listing["type"]] if hi else listing["type"],
            "bhk": listing["bhk"],
            "purpose": listing["purpose"],
            "price_spoken": format_amount_spoken(listing["price"], lang)
            + ((" महीना" if hi else " per month") if listing["purpose"] == "rent" else ""),
            "size_sqft": listing["size_sqft"],
            "furnishing": FURNISHING_HI[listing["furnishing"]] if hi else listing["furnishing"],
            "possession": listing["possession"][lang],
        }

    def _card(self, listing: dict) -> dict:
        lang = self.language
        hi = lang == "hi"
        return {
            "id": listing["id"],
            "title": listing["title"][lang],
            "area": AREA_HI[listing["area"]] if hi else listing["area"],
            "type": TYPE_HI[listing["type"]] if hi else listing["type"].title(),
            "bhk": listing["bhk"],
            "purpose": listing["purpose"],
            "price": format_amount_display(listing["price"], listing["purpose"]),
            "size_sqft": listing["size_sqft"],
            "furnishing": FURNISHING_HI[listing["furnishing"]] if hi else listing["furnishing"],
            "possession": listing["possession"][lang],
            "amenities": [AMENITY_HI.get(a, a) if hi else a for a in listing["amenities"]][:4],
            "gradient": listing["gradient"],
        }

    # -- tools --------------------------------------------------------------

    def search(
        self,
        purpose: str,
        area: str | None = None,
        min_budget: object = None,
        max_budget: object = None,
        bhk: int | None = None,
    ) -> tuple[dict, dict]:
        """Return (result for the LLM, payload for the UI)."""
        norm_purpose = normalize_purpose(purpose) or "buy"
        area_name = match_area(area) if area else None
        unknown_area = bool(area) and area_name is None
        lo = parse_amount(min_budget, norm_purpose)
        hi = parse_amount(max_budget, norm_purpose)
        if lo is not None and hi is not None and lo > hi:
            lo, hi = hi, lo
        try:
            bhk = int(bhk) if bhk not in (None, "") else None
        except (TypeError, ValueError):
            bhk = None

        pool = [listing for listing in LISTINGS if listing["purpose"] == norm_purpose]

        def fits(listing: dict) -> bool:
            if area_name and listing["area"] != area_name:
                return False
            if bhk and listing["bhk"] != bhk:
                return False
            if hi is not None and listing["price"] > hi:
                return False
            if lo is not None and listing["price"] < lo:
                return False
            return True

        exact = sorted((l for l in pool if fits(l)), key=lambda l: l["price"])
        if exact:
            chosen = exact[:MAX_RESULTS]
            is_exact = True
        else:
            chosen = sorted(pool, key=lambda l: self._distance(l, area_name, bhk, lo, hi))[:MAX_RESULTS]
            is_exact = False

        items = []
        for listing in chosen:
            item = self._summary(listing)
            if not is_exact:
                item["differs_by"] = self._differences(listing, area_name, bhk, lo, hi)
            items.append(item)

        result: dict = {
            "exact_match": is_exact,
            "total_exact_matches": len(exact),
            "results": items,
        }
        if unknown_area:
            result["note"] = f"Tatsat Real Estate has no listings in '{area}'. Offer these instead."
        elif not is_exact:
            result["note"] = "Nothing matches every requirement. These are the closest options; say how they differ."
        result["speak_guidance"] = "Mention at most 2 or 3 of these briefly, then ask which one interests the caller."

        query_bits = []
        if area_name or area:
            query_bits.append(area_name or str(area))
        if bhk:
            query_bits.append(f"{bhk} BHK")
        if hi is not None:
            query_bits.append(f"≤ {format_amount_display(hi, norm_purpose)}")
        if lo is not None:
            query_bits.append(f"≥ {format_amount_display(lo, norm_purpose)}")
        ui = {
            "type": "properties",
            "purpose": norm_purpose,
            "exact": is_exact,
            "query": " · ".join(query_bits) or ("rent" if norm_purpose == "rent" else "buy"),
            "items": [self._card(l) for l in chosen],
        }
        self.last_query = {"purpose": norm_purpose, "area": area_name, "bhk": bhk, "lo": lo, "hi": hi}
        for listing in chosen:
            self.note_interest(listing["id"], 1)
        return result, ui

    @staticmethod
    def _distance(listing, area_name, bhk, lo, hi) -> float:
        score = 0.0
        if area_name and listing["area"] != area_name:
            score += 3
        if bhk:
            score += 2 * abs(listing["bhk"] - bhk)
        if hi is not None and listing["price"] > hi:
            score += 10 * (listing["price"] / hi - 1)
        if lo is not None and listing["price"] < lo:
            score += 5 * (1 - listing["price"] / lo)
        return score

    def _differences(self, listing, area_name, bhk, lo, hi) -> list[str]:
        lang = self.language
        out = []
        if area_name and listing["area"] != area_name:
            out.append(f"in {listing['area']} instead of {area_name}")
        if bhk and listing["bhk"] != bhk:
            out.append(f"{listing['bhk']} BHK instead of {bhk} BHK")
        if hi is not None and listing["price"] > hi:
            over = listing["price"] - hi
            out.append(f"{format_amount_spoken(over, lang)} over budget")
        if lo is not None and listing["price"] < lo:
            out.append("below the minimum budget")
        return out

    def details(self, property_id: str) -> tuple[dict, dict | None]:
        pid = normalize_property_id(property_id)
        if not pid:
            return {"error": f"No property with id '{property_id}'. Use an id from search results."}, None
        listing = LISTINGS_BY_ID[pid]
        lang = self.language
        result = self._summary(listing)
        result["amenities"] = [AMENITY_HI.get(a, a) if lang == "hi" else a for a in listing["amenities"]]
        result["description"] = listing["description"][lang]
        result["speak_guidance"] = "Answer what the caller asked in one or two short sentences, mentioning at most three highlights."
        self.note_interest(pid, 2)
        return result, {"type": "property_detail", "item": self._card(listing)}

    def emi(self, loan_amount: object, interest_rate: float = 8.5, tenure_years: float = 20) -> tuple[dict, dict]:
        principal = parse_amount(loan_amount, "buy")
        if not principal or principal <= 0:
            return {"error": "Please give the loan amount, for example '60 lakh'."}, None
        try:
            rate = float(interest_rate) if interest_rate not in (None, "") else 8.5
            years = float(tenure_years) if tenure_years not in (None, "") else 20.0
        except (TypeError, ValueError):
            rate, years = 8.5, 20.0
        if not 0 <= rate <= 30 or not 1 <= years <= 40:
            return {"error": "Interest rate must be 0-30% and tenure 1-40 years."}, None

        emi = calculate_emi_amount(principal, rate, years)
        total = emi * years * 12
        lang = self.language
        result = {
            "loan_amount_spoken": format_amount_spoken(principal, lang),
            "interest_rate_percent": rate,
            "tenure_years": years,
            "monthly_emi_rupees": int(round(emi)),
            "monthly_emi_spoken": format_amount_spoken(round(emi), lang),
            "total_interest_spoken": format_amount_spoken(round(total - principal), lang),
            "note": "Approximate figure; actual EMI depends on the bank.",
        }
        ui = {
            "type": "emi",
            "loan": format_amount_display(principal),
            "rate": rate,
            "years": years,
            "emi": format_amount_display(round(emi), "rent").removesuffix("/mo"),
            "emi_value": int(round(emi)),
            "total_interest": format_amount_display(round(total - principal)),
            "total_payment": format_amount_display(round(total)),
        }
        return result, ui

    def followup_picks(self, max_liked: int = 3, max_options: int = 3) -> tuple[list[dict], list[dict]]:
        """(homes the caller was interested in, other good options) for the follow-up message.

        Interested = homes they booked or asked about; if none, the top homes they were shown.
        Options = the closest other matches to their last search (same buy/rent).
        """
        ranked = sorted(self.interest.items(), key=lambda kv: -kv[1])
        strong = [pid for pid, level in ranked if level >= 2]
        liked_ids = (strong or [pid for pid, _ in ranked])[:max_liked]
        liked = [LISTINGS_BY_ID[pid] for pid in liked_ids]

        q = self.last_query or {}
        purpose = q.get("purpose") or (liked[0]["purpose"] if liked else None)
        pool = [l for l in LISTINGS if l["id"] not in liked_ids and (purpose is None or l["purpose"] == purpose)]
        pool.sort(key=lambda l: self._distance(l, q.get("area"), q.get("bhk"), q.get("lo"), q.get("hi")))
        return liked, pool[:max_options]

    def _parse_slot(self, visit_date: object, visit_time: object) -> tuple[date, time] | dict:
        """Validate a requested visit slot; returns (date, time) or an error result for the LLM."""
        today = self._today()
        day = parse_visit_date(visit_date, today)
        if day is None:
            return {"error": f"Couldn't understand the date '{visit_date}'. Ask again, e.g. 'tomorrow' or '20 October'."}
        if day < today:
            return {"error": "That date is in the past. Ask for a future date."}
        if day > today + timedelta(days=60):
            return {"error": "Visits can be booked up to 60 days ahead. Ask for an earlier date."}
        slot = parse_visit_time(visit_time)
        if slot is None:
            return {"error": f"Couldn't understand the time '{visit_time}'. Ask again, e.g. '11 AM' or '4 PM'."}
        if not VISIT_OPEN <= slot <= VISIT_CLOSE:
            return {"error": "Site visits run from 10 AM to 6 PM. Ask for a time in that window."}
        if day == today and slot <= datetime.now(IST).time():
            return {"error": "That time has already passed today. Offer a later slot or another day."}
        return day, slot

    def _slot_taken(self, pid: str, day: date, slot: time) -> tuple[dict, dict]:
        lang = self.language
        alternatives = self._alternatives(pid, day, slot, self._today())
        result = {
            "done": False,
            "reason": "slot_taken",
            "requested": f"{format_date_spoken(day, lang)}, {format_time_spoken(slot, lang)}",
            "available_alternatives": alternatives,
            "speak_guidance": "Apologise briefly that this slot is taken and offer one or two of the alternatives.",
        }
        ui = {
            "type": "slot_taken",
            "property_id": pid,
            "requested": f"{day.isoformat()} {slot.strftime('%H:%M')}",
            "alternatives": alternatives,
        }
        return result, ui

    def _booking_card(self, booking: dict, status: str = "confirmed") -> dict:
        lang = self.language
        listing = LISTINGS_BY_ID[booking["property_id"]]
        day = date.fromisoformat(booking["date"])
        slot = time.fromisoformat(booking["time"])
        return {
            "type": "booking",
            "status": status,
            "code": booking["code"],
            "property_id": booking["property_id"],
            "property": listing["title"][lang],
            "area": AREA_HI[listing["area"]] if lang == "hi" else listing["area"],
            "name": booking["name"],
            "phone": format_phone_display(booking["phone"]),
            "date": format_date_spoken(day, lang),
            "time": format_time_spoken(slot, lang),
        }

    def _booking_spoken(self, booking: dict) -> dict:
        lang = self.language
        listing = LISTINGS_BY_ID[booking["property_id"]]
        day = date.fromisoformat(booking["date"])
        slot = time.fromisoformat(booking["time"])
        return {
            "confirmation_code": booking["code"],
            "confirmation_code_spoken": " ".join(booking["code"].replace("-", "")),
            "property": listing["title"][lang],
            "when": f"{format_date_spoken(day, lang)}, {format_time_spoken(slot, lang)}",
            "name": booking["name"],
        }

    def book_visit(self, property_id: str, name: str, phone: str, visit_date: str, visit_time: str) -> tuple[dict, dict | None]:
        pid = normalize_property_id(property_id)
        if not pid:
            return {"error": f"Unknown property '{property_id}'. Confirm which property the caller wants to see."}, None
        if not str(name or "").strip():
            return {"error": "Missing the caller's name. Ask for it."}, None
        phone_norm = normalize_phone(phone)
        if not phone_norm:
            return {"error": "That phone number isn't a valid 10-digit Indian mobile number. Ask the caller to repeat it."}, None
        parsed = self._parse_slot(visit_date, visit_time)
        if isinstance(parsed, dict):
            return parsed, None
        day, slot = parsed

        booking = self.store.create(pid, str(name).strip(), phone_norm, day.isoformat(), slot.strftime("%H:%M"))
        if booking is None:
            return self._slot_taken(pid, day, slot)
        logger.info(f"Booked site visit {booking['code']} for {pid} on {booking['date']} {booking['time']}")
        self.note_interest(pid, 3)
        self.booked_codes.append(booking["code"])
        result = {"done": True, "booked": True, **self._booking_spoken(booking), "phone_last_digits": phone_norm[-4:]}
        return result, self._booking_card(booking)

    def _caller_booking(self, phone: object, code: object) -> dict | tuple[dict, None]:
        """Find the booking a caller means, by phone and optionally confirmation code."""
        phone_norm = normalize_phone(phone)
        if not phone_norm:
            return {"error": "Ask for the 10-digit mobile number the visit was booked with."}, None
        visits = self.store.find_by_phone(phone_norm, self._today().isoformat())
        if not visits:
            return {"error": "No upcoming site visits are booked with that number. Ask the caller to check the number."}, None
        wanted = normalize_code(code) if code else None
        if wanted:
            match = [v for v in visits if v["code"] == wanted]
            if not match:
                return {"error": f"No visit with code {wanted} for that number. Use find_my_visits to list them."}, None
            return match[0]
        if len(visits) > 1:
            return {"error": "This number has several visits. Ask which one (by property or confirmation code)."}, None
        return visits[0]

    def find_visits(self, phone: str) -> tuple[dict, dict | None]:
        phone_norm = normalize_phone(phone)
        if not phone_norm:
            return {"error": "Ask for the 10-digit mobile number the visit was booked with."}, None
        visits = self.store.find_by_phone(phone_norm, self._today().isoformat())
        result = {"count": len(visits), "visits": [self._booking_spoken(v) for v in visits]}
        if not visits:
            result["note"] = "No upcoming visits for this number."
        return result, {"type": "visits", "items": [self._booking_card(v) for v in visits]}

    def reschedule_visit(self, phone: str, code: str | None, visit_date: str, visit_time: str) -> tuple[dict, dict | None]:
        found = self._caller_booking(phone, code)
        if isinstance(found, tuple):
            return found
        parsed = self._parse_slot(visit_date, visit_time)
        if isinstance(parsed, dict):
            return parsed, None
        day, slot = parsed
        updated = self.store.reschedule(found["code"], day.isoformat(), slot.strftime("%H:%M"))
        if updated is None:
            return self._slot_taken(found["property_id"], day, slot)
        logger.info(f"Rescheduled {found['code']} to {updated['date']} {updated['time']}")
        result = {
            "done": True,
            "rescheduled": True,
            **self._booking_spoken(updated),
            "speak_guidance": "Confirm the visit is now at the new time and repeat the confirmation code. Don't ask for anything else.",
        }
        return result, self._booking_card(updated, "rescheduled")

    def cancel_visit(self, phone: str, code: str | None) -> tuple[dict, dict | None]:
        found = self._caller_booking(phone, code)
        if isinstance(found, tuple):
            return found
        cancelled = self.store.cancel(found["code"])
        logger.info(f"Cancelled {found['code']}")
        result = {
            "done": True,
            "cancelled": True,
            **self._booking_spoken(cancelled),
            "speak_guidance": "Confirm the visit is cancelled, then ask if there is anything else.",
        }
        return result, self._booking_card(cancelled, "cancelled")

    def _alternatives(self, pid: str, day: date, slot: time, today: date) -> list[str]:
        lang = self.language
        now = datetime.now(IST)
        options: list[tuple[date, time]] = []
        for delta_hours in (1, -1, 2, -2, 3, -3):
            hour = slot.hour + delta_hours
            if not VISIT_OPEN.hour <= hour <= VISIT_CLOSE.hour:
                continue
            candidate = time(hour, slot.minute if hour < VISIT_CLOSE.hour else 0)
            if day == today and candidate <= now.time():
                continue
            if not self.store.is_taken(pid, day.isoformat(), candidate.strftime("%H:%M")):
                options.append((day, candidate))
            if len(options) >= 2:
                break
        next_day = day + timedelta(days=1)
        if not self.store.is_taken(pid, next_day.isoformat(), slot.strftime("%H:%M")):
            options.append((next_day, slot))
        return [f"{format_date_spoken(d, lang)}, {format_time_spoken(t, lang)}" for d, t in options[:3]]




async def _send_ui(params: FunctionCallParams, payload: dict | None) -> None:
    if payload is not None:
        await params.llm.push_frame(RTVIServerMessageFrame(data=payload))


async def _log_tool(params: FunctionCallParams, name: str, summary: str, ok: bool = True) -> None:
    logger.info(f"🔧 {name} → {summary}")
    await _send_ui(params, {"type": "tool", "name": name, "summary": summary, "ok": ok})


def build_tool_functions(
    desk: PropertyDesk,
    switch_language: Callable[[str, object], Awaitable[bool]],
    hang_up: Callable[[], Awaitable[None]] | None = None,
    sender=None,
) -> list[Callable]:
    """Create the direct functions handed to ``LLMContext(tools=...)``."""

    async def search_properties(
        params: FunctionCallParams,
        purpose: str,
        area: str | None = None,
        min_budget: str | None = None,
        max_budget: str | None = None,
        bhk: int | None = None,
    ):
        """Search Tatsat Real Estate listings. Call this as soon as you know whether the caller wants to buy or rent and at least one more preference.

        Args:
            purpose: "buy" or "rent".
            area: Neighbourhood the caller asked for, e.g. "Bopal", "Satellite", "Prahlad Nagar", "SG Highway", "Thaltej", "Chandkheda", "Gandhinagar".
            min_budget: Minimum budget exactly as the caller said it, e.g. "50 lakh" or "20000".
            max_budget: Maximum budget exactly as the caller said it, e.g. "90 lakh", "1.2 crore", or "30000" per month for rent.
            bhk: Number of bedrooms (BHK), e.g. 2 or 3.
        """
        try:
            result, ui = desk.search(purpose, area, min_budget, max_budget, bhk)
            await _send_ui(params, ui)
            kind = "matches" if result["exact_match"] else "closest alternatives"
            await _log_tool(params, "search_properties", f"{ui['query']} → {len(ui['items'])} {kind}")
        except Exception as e:  # never let a tool crash the call
            logger.exception("search_properties failed")
            result = {"error": f"Search failed: {e}"}
            await _log_tool(params, "search_properties", "error", ok=False)
        await params.result_callback(result)

    async def get_property_details(params: FunctionCallParams, property_id: str):
        """Get full details (amenities, description, possession) of one property.

        Args:
            property_id: The property id from search results, e.g. "SH-102".
        """
        result, ui = desk.details(property_id)
        await _send_ui(params, ui)
        await _log_tool(params, "get_property_details", ui["item"]["title"] if ui else f"{property_id} not found", ok=ui is not None)
        await params.result_callback(result)

    async def calculate_emi(
        params: FunctionCallParams,
        loan_amount: str,
        interest_rate: float = 8.5,
        tenure_years: float = 20,
    ):
        """Calculate the approximate monthly EMI for a home loan.

        Args:
            loan_amount: Loan amount as the caller said it, e.g. "70 lakh" or "1.1 crore".
            interest_rate: Annual interest rate in percent. Defaults to 8.5.
            tenure_years: Loan tenure in years. Defaults to 20.
        """
        result, ui = desk.emi(loan_amount, interest_rate, tenure_years)
        await _send_ui(params, ui)
        if ui:
            await _log_tool(params, "calculate_emi", f"{ui['loan']} @ {ui['rate']}% × {ui['years']:g}y → {ui['emi']}/mo")
        else:
            await _log_tool(params, "calculate_emi", "invalid input", ok=False)
        await params.result_callback(result)

    async def schedule_site_visit(
        params: FunctionCallParams,
        property_id: str,
        name: str,
        phone: str,
        date: str,
        time: str,
    ):
        """Book a site visit. Only call after the caller has confirmed their name, phone number, date and time.

        Args:
            property_id: The property id, e.g. "SH-102".
            name: Caller's name.
            phone: Caller's 10-digit mobile number, digits only.
            date: Visit date as YYYY-MM-DD if you can work it out, otherwise as said, e.g. "tomorrow", "kal", "Saturday".
            time: Visit time, e.g. "11 AM" or "4:30 PM". Visits run 10 AM to 6 PM.
        """
        try:
            result, ui = desk.book_visit(property_id, name, phone, date, time)
        except Exception as e:
            logger.exception("schedule_site_visit failed")
            result, ui = {"error": f"Booking failed: {e}"}, None
        await _send_ui(params, ui)
        if ui and ui["type"] == "booking":
            summary = f"{ui['property']}, {ui['date']} {ui['time']} → {ui['code']}"
        elif ui:
            summary = f"{property_id} {date} {time} → slot taken"
        else:
            summary = result.get("error", "failed")
        await _log_tool(params, "schedule_site_visit", summary, ok=bool(ui))
        await params.result_callback(result)

    async def set_language(params: FunctionCallParams, language: str):
        """Switch the conversation language when the caller asks, e.g. "Hindi mein baat karo" or "speak in English".

        Args:
            language: "english" or "hindi".
        """
        target = "hi" if "hi" in language.lower() or "हिं" in language else "en"
        changed = await switch_language(target, params.llm)
        await _log_tool(params, "set_language", "Hindi" if target == "hi" else "English")
        await params.result_callback(
            {
                "language": "hindi" if target == "hi" else "english",
                "changed": changed,
                "instruction": "Reply in Hindi (Devanagari script) from now on."
                if target == "hi"
                else "Reply in English from now on.",
            }
        )

    async def find_my_visits(params: FunctionCallParams, phone: str):
        """Look up the caller's upcoming site visits by the mobile number they booked with.

        Args:
            phone: The caller's 10-digit mobile number, digits only.
        """
        result, ui = desk.find_visits(phone)
        await _send_ui(params, ui)
        summary = f"{result.get('count', 0)} upcoming" if ui else result.get("error", "failed")
        await _log_tool(params, "find_my_visits", summary, ok=bool(ui))
        await params.result_callback(result)

    async def reschedule_site_visit(
        params: FunctionCallParams,
        phone: str,
        new_date: str,
        new_time: str,
        confirmation_code: str | None = None,
    ):
        """Move an existing site visit to a new date and time. Confirm the new slot with the caller first.

        Args:
            phone: The mobile number the visit was booked with, digits only.
            new_date: New date as YYYY-MM-DD if you can work it out, otherwise as said, e.g. "Saturday".
            new_time: New time, e.g. "5 PM". Visits run 10 AM to 6 PM.
            confirmation_code: The visit's code, e.g. "SH-2890". Needed only if the number has several visits.
        """
        try:
            result, ui = desk.reschedule_visit(phone, confirmation_code, new_date, new_time)
        except Exception as e:
            logger.exception("reschedule_site_visit failed")
            result, ui = {"error": f"Rescheduling failed: {e}"}, None
        await _send_ui(params, ui)
        if ui and ui["type"] == "booking":
            summary = f"{ui['code']} → {ui['date']} {ui['time']}"
        elif ui:
            summary = f"{new_date} {new_time} → slot taken"
        else:
            summary = result.get("error", "failed")
        await _log_tool(params, "reschedule_site_visit", summary, ok=bool(ui))
        await params.result_callback(result)

    async def cancel_site_visit(params: FunctionCallParams, phone: str, confirmation_code: str | None = None):
        """Cancel an existing site visit. Only call after the caller has clearly confirmed they want to cancel.

        Args:
            phone: The mobile number the visit was booked with, digits only.
            confirmation_code: The visit's code, e.g. "SH-2890". Needed only if the number has several visits.
        """
        result, ui = desk.cancel_visit(phone, confirmation_code)
        await _send_ui(params, ui)
        await _log_tool(params, "cancel_site_visit", ui["code"] + " cancelled" if ui else result.get("error", "failed"), ok=bool(ui))
        await params.result_callback(result)

    async def send_follow_up(params: FunctionCallParams, phone: str, name: str | None = None):
        """Save the caller's number for follow-up and send them a WhatsApp message with the homes they liked plus a few good options. Call once the caller has agreed and given their number.

        Args:
            phone: The caller's 10-digit mobile number, digits only.
            name: The caller's name, if they gave it.
        """
        from followup import compose_message, whatsapp_link

        phone_norm = normalize_phone(phone)
        if not phone_norm:
            await params.result_callback({"error": "That isn't a valid 10-digit Indian mobile number. Ask the caller to repeat it."})
            return
        name = str(name).strip() if name else None
        text, liked, options = compose_message(desk, name)
        desk.store.save_lead(phone_norm, name, desk.language, [l["id"] for l in liked + options])
        outcome = await sender.deliver(phone_norm, text) if sender else {"channel": "preview", "status": "preview", "detail": ""}
        desk.store.log_message(phone_norm, outcome["channel"], outcome["status"], text, outcome.get("detail"))

        lang = desk.language
        await _send_ui(params, {
            "type": "followup",
            "phone": format_phone_display(phone_norm),
            "name": name or "",
            "channel": outcome["channel"],
            "status": outcome["status"],
            "detail": outcome.get("detail", ""),
            "text": text,
            "link": whatsapp_link(phone_norm, text),
            "liked": [l["title"][lang] for l in liked],
            "options": [l["title"][lang] for l in options],
        })
        await _log_tool(params, "send_follow_up", f"+91 {phone_norm[:5]}… → {outcome['status']} ({len(liked)} liked, {len(options)} options)")
        sent = outcome["status"] == "sent"
        await params.result_callback({
            "saved": True,
            "sent_on_whatsapp": sent,
            "homes_included": [l["title"][lang] for l in liked + options],
            "speak_guidance": "Tell the caller you've sent the details to their WhatsApp."
            if sent
            else "Tell the caller our team will WhatsApp them these details shortly.",
        })

    async def end_call(params: FunctionCallParams):
        """End the call when the caller says goodbye or has nothing else to ask. The system says goodbye for you."""
        from pipecat.frames.frames import FunctionCallResultProperties

        await _log_tool(params, "end_call", "caller is done")
        await params.result_callback({"ending": True}, properties=FunctionCallResultProperties(run_llm=False))
        if hang_up:
            await hang_up()

    tools = [
        search_properties,
        get_property_details,
        calculate_emi,
        schedule_site_visit,
        find_my_visits,
        reschedule_site_visit,
        cancel_site_visit,
        send_follow_up,
        set_language,
    ]
    if hang_up:
        tools.append(end_call)
    return tools
