from datetime import date

import pytest

import followup
from bookings import BookingStore
from followup import FollowUpSender, compose_message, whatsapp_link
from tools import PropertyDesk

TODAY = date(2026, 10, 14)


@pytest.fixture
def desk():
    store = BookingStore(":memory:")
    store.seed(TODAY)
    return PropertyDesk("en", today=lambda: TODAY, store=store)


def test_message_lists_liked_homes_then_options(desk):
    desk.search("buy", "Bopal", None, "90 lakh", 3)  # shows Sapna Greens
    desk.details("SH-102")  # strong interest
    text, liked, options = compose_message(desk, "Rohan")
    assert [l["id"] for l in liked] == ["SH-102"]
    assert 2 <= len(options) <= 3 and "SH-102" not in [o["id"] for o in options]
    assert all(o["purpose"] == "buy" for o in options)  # same buy/rent as the search
    assert text.startswith("Hi Rohan") and "Sapna Greens (SH-102)" in text and "₹82 L" in text


def test_message_includes_booked_visit(desk):
    booked, _ = desk.book_visit("SH-109", "Asha", "9876543210", "2026-10-20", "4 pm")
    text, liked, _ = compose_message(desk, "Asha")
    assert liked[0]["id"] == "SH-109"
    assert booked["confirmation_code"] in text and "/month" in text


def test_hindi_message(desk):
    desk.language = "hi"
    desk.search("rent", "Satellite", None, "30000", 2)
    text, liked, _ = compose_message(desk, None)
    assert text.startswith("नमस्ते,") and "मानसी अपार्टमेंट्स" in text and "/महीना" in text


def test_whatsapp_link_is_prefilled():
    link = whatsapp_link("9876543210", "Hi there")
    assert link == "https://wa.me/919876543210?text=Hi%20there"


async def test_preview_channel_needs_no_setup():
    sender = FollowUpSender("preview")
    out = await sender.deliver("9876543210", "hello")
    assert out["channel"] == "preview" and out["status"] == "preview"


async def test_whatsapp_without_token_falls_back_to_preview():
    sender = FollowUpSender("whatsapp", token="", phone_number_id="")
    assert (await sender.deliver("9876543210", "hello"))["status"] == "preview"


async def test_whatsapp_outside_window_reports_failure(monkeypatch):
    async def fake_send(*args):
        return False, "outside WhatsApp's 24-hour window: the recipient must message the business number first"

    monkeypatch.setattr(followup, "send_whatsapp", fake_send)
    sender = FollowUpSender("whatsapp", token="t", phone_number_id="123")
    out = await sender.deliver("9876543210", "hello")
    assert out["status"] == "failed" and "24-hour" in out["detail"]


def test_leads_and_messages_are_stored(desk):
    lead_id = desk.store.save_lead("9876543210", "Rohan", "en", ["SH-102", "SH-103"])
    desk.store.log_message("9876543210", "preview", "preview", "hello")
    assert lead_id == 1
    assert desk.store.leads()[0]["interested"] == '["SH-102", "SH-103"]'
    assert desk.store.messages()[0]["status"] == "preview"
