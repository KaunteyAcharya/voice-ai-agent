"""Follow-up messages: the homes a caller liked plus a few good alternatives.

Two delivery channels (MESSAGE_CHANNEL in .env):

* ``preview`` (default, free, no setup): the message is saved to the database,
  shown in the UI, and comes with a WhatsApp click-to-chat link pre-filled with
  the text, so an agent can send it in one tap from their own WhatsApp.
* ``whatsapp``: sent automatically through Meta's WhatsApp Cloud API. Meta's test
  number is free and can message up to 5 numbers you verify in the Meta
  developer dashboard. Free-form text is only delivered inside WhatsApp's 24-hour
  customer-service window (the recipient must have messaged the business number
  recently); outside it Meta requires a pre-approved template, so the message is
  kept as a preview instead.

Every message is logged in the ``messages`` table, and the caller's number and
interests in ``leads``, whatever the channel.
"""

from __future__ import annotations

from datetime import date, time
from urllib.parse import quote

import aiohttp
from loguru import logger

from listings import AREA_HI, LISTINGS_BY_ID, TYPE_HI
from parsing import format_amount_display, format_date_spoken, format_time_spoken

WHATSAPP_URL = "https://graph.facebook.com/{version}/{phone_id}/messages"
OUTSIDE_WINDOW_ERROR = 131047  # Meta: "re-engagement message" (24-hour window closed)

_TEXT = {
    "en": {
        "hello": "Hi {name}, thanks for calling Tatsat Real Estate!",
        "hello_noname": "Hi, thanks for calling Tatsat Real Estate!",
        "liked": "Homes you were interested in:",
        "options": "A few more good options for you:",
        "visit": "Your site visit: {property}, {when} (code {code})",
        "outro": "Reply here or call us anytime to book a visit. - Aditi, Tatsat Real Estate",
        "rent": "/month",
    },
    "hi": {
        "hello": "नमस्ते {name}, तत्सत रियल एस्टेट को कॉल करने के लिए थैंक यू!",
        "hello_noname": "नमस्ते, तत्सत रियल एस्टेट को कॉल करने के लिए थैंक यू!",
        "liked": "जिन घरों में आपकी दिलचस्पी थी:",
        "options": "आपके लिए कुछ और अच्छे ऑप्शन:",
        "visit": "आपकी साइट विज़िट: {property}, {when} (कोड {code})",
        "outro": "विज़िट बुक करने के लिए यहाँ रिप्लाई करें या कभी भी कॉल करें। - अदिति, तत्सत रियल एस्टेट",
        "rent": "/महीना",
    },
}


def _line(listing: dict, lang: str) -> str:
    hi = lang == "hi"
    area = AREA_HI[listing["area"]] if hi else listing["area"]
    kind = TYPE_HI[listing["type"]] if hi else listing["type"]
    price = format_amount_display(listing["price"], listing["purpose"]).replace("/mo", _TEXT[lang]["rent"])
    return f"• {listing['title'][lang]} ({listing['id']}) - {listing['bhk']} BHK {kind}, {area} - {price} - {listing['possession'][lang]}"


def compose_message(desk, name: str | None) -> tuple[str, list[dict], list[dict]]:
    """Build the follow-up text. Returns (text, liked listings, option listings)."""
    lang = desk.language
    t = _TEXT[lang]
    liked, options = desk.followup_picks()
    lines = [t["hello"].format(name=name) if name else t["hello_noname"], ""]
    if liked:
        lines += [t["liked"], *(_line(l, lang) for l in liked), ""]
    if options:
        lines += [t["options"], *(_line(l, lang) for l in options[:3]), ""]
    for code in desk.booked_codes:
        booking = desk.store.get(code)
        if booking and booking["status"] == "confirmed":
            when = f"{format_date_spoken(date.fromisoformat(booking['date']), lang)}, {format_time_spoken(time.fromisoformat(booking['time']), lang)}"
            lines += [t["visit"].format(property=LISTINGS_BY_ID[booking["property_id"]]["title"][lang], when=when, code=code), ""]
    lines.append(t["outro"])
    return "\n".join(lines), liked, options


def whatsapp_link(phone: str, text: str) -> str:
    """Click-to-chat link that opens WhatsApp with the message ready to send."""
    return f"https://wa.me/91{phone}?text={quote(text)}"


async def send_whatsapp(token: str, phone_number_id: str, version: str, phone: str, text: str) -> tuple[bool, str]:
    """Send a text message via the WhatsApp Cloud API. Returns (sent, detail)."""
    url = WHATSAPP_URL.format(version=version, phone_id=phone_number_id)
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": f"+91{phone}",
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post(url, json=payload, headers={"Authorization": f"Bearer {token}"}) as resp:
                data = await resp.json(content_type=None)
    except Exception as e:
        return False, f"network error: {e}"
    if resp.status < 300 and data.get("messages"):
        return True, f"message id {data['messages'][0].get('id')}"
    error = (data or {}).get("error", {})
    if error.get("code") == OUTSIDE_WINDOW_ERROR:
        return False, "outside WhatsApp's 24-hour window: the recipient must message the business number first"
    return False, f"WhatsApp error {error.get('code')}: {error.get('message', resp.status)}"


class FollowUpSender:
    """Delivers follow-up messages on the configured channel."""

    def __init__(self, channel: str, token: str = "", phone_number_id: str = "", version: str = "v26.0"):
        self.whatsapp_ready = channel == "whatsapp" and bool(token and phone_number_id)
        if channel == "whatsapp" and not self.whatsapp_ready:
            logger.warning("MESSAGE_CHANNEL=whatsapp but WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID are missing; using preview")
        self.channel = "whatsapp" if self.whatsapp_ready else "preview"
        self._token, self._phone_id, self._version = token, phone_number_id, version

    async def deliver(self, phone: str, text: str) -> dict:
        if self.whatsapp_ready:
            sent, detail = await send_whatsapp(self._token, self._phone_id, self._version, phone, text)
            if sent:
                logger.info(f"📨 WhatsApp follow-up sent to +91 {phone} ({detail})")
                return {"channel": "whatsapp", "status": "sent", "detail": detail}
            logger.warning(f"📨 WhatsApp follow-up not sent to +91 {phone}: {detail}")
            return {"channel": "whatsapp", "status": "failed", "detail": detail}
        logger.info(f"📨 Follow-up for +91 {phone} saved as a preview (MESSAGE_CHANNEL=preview)")
        return {"channel": "preview", "status": "preview", "detail": "saved; send it with the WhatsApp link"}
