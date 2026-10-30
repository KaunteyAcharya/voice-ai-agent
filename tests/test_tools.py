from datetime import date, timedelta

import pytest

import bookings
from bookings import BookingStore
from listings import LISTINGS
from tools import (
    PropertyDesk,
    calculate_emi_amount,
    match_area,
    normalize_code,
    normalize_property_id,
    normalize_purpose,
)

TODAY = date(2026, 10, 14)  # Wednesday


@pytest.fixture
def store():
    s = BookingStore(":memory:")
    s.seed(TODAY)
    return s


@pytest.fixture
def desk(store):
    def make(lang="en"):
        return PropertyDesk(lang, today=lambda: TODAY, store=store)

    return make


def test_listings_are_complete():
    assert len(LISTINGS) == 12
    for listing in LISTINGS:
        for lang in ("en", "hi"):
            assert listing["title"][lang] and listing["description"][lang] and listing["possession"][lang]
        assert listing["purpose"] in ("buy", "rent")
        assert listing["type"] in ("apartment", "villa", "bungalow")


@pytest.mark.parametrize(
    "said,area",
    [("Bopal", "Bopal"), ("south bopal", "Bopal"), ("बोपल", "Bopal"), ("satelite", "Satellite"),
     ("prahladnagar", "Prahlad Nagar"), ("SG Road", "SG Highway"), ("गांधीनगर", "Gandhinagar Sector 21"),
     ("Vastrapur", None)],
)
def test_match_area(said, area):
    assert match_area(said) == area


def test_normalizers():
    assert normalize_purpose("kiraye pe") == "rent"
    assert normalize_purpose("खरीदना") == "buy"
    assert normalize_property_id("sh 102") == "SH-102"
    assert normalize_property_id("102") == "SH-102"
    assert normalize_property_id("Sapna Greens") == "SH-102"
    assert normalize_property_id("SH-999") is None


def test_search_exact_match(desk):
    result, ui = desk().search("buy", "Bopal", None, "90 lakh", 3)
    assert result["exact_match"] is True
    assert [r["id"] for r in result["results"]] == ["SH-102"]
    assert ui["type"] == "properties" and ui["items"][0]["price"] == "₹82 L"


def test_search_returns_closest_when_nothing_matches(desk):
    result, ui = desk().search("buy", "Bopal", None, "50 lakh", 3)
    assert result["exact_match"] is False
    assert 1 <= len(result["results"]) <= 3
    assert all("differs_by" in r for r in result["results"])
    assert ui["exact"] is False


def test_search_unknown_area_offers_alternatives(desk):
    result, _ = desk().search("rent", "Vastrapur")
    assert "no listings" in result["note"]
    assert result["results"]


def test_search_hindi_uses_devanagari(desk):
    result, _ = desk("hi").search("rent", "सैटेलाइट", max_budget="30 हज़ार")
    first = result["results"][0]
    assert first["id"] == "SH-109"
    assert first["area"] == "सैटेलाइट"
    assert "रुपये" in first["price_spoken"]


def test_emi_math(desk):
    # Standard reducing-balance formula: 50 lakh @ 8.5% for 20 years ≈ ₹43,391.
    assert round(calculate_emi_amount(5_000_000, 8.5, 20)) == 43391
    assert round(calculate_emi_amount(1_200_000, 0, 1)) == 100_000
    result, ui = desk().emi("70 lakh")
    assert result["monthly_emi_rupees"] == 60748
    assert ui["emi"] == "₹60,748"


def test_emi_rejects_bad_input(desk):
    result, ui = desk().emi("lots")
    assert "error" in result and ui is None


def test_booking_happy_path_and_slot_taken(desk):
    d = desk()
    result, ui = d.book_visit("SH-102", "Kaunteya", "98765 43210", "kal", "12 pm")
    assert result["booked"] is True
    assert result["confirmation_code"].startswith("SH-") and len(result["confirmation_code"]) == 7
    assert ui["type"] == "booking"

    # Seeded: SH-102 is already booked tomorrow at 11 AM.
    result, ui = d.book_visit("SH-102", "Asha", "9876543210", "tomorrow", "11 am")
    assert result["done"] is False and result["reason"] == "slot_taken"
    alternatives = result["available_alternatives"]
    assert alternatives and not any("12 PM" in a for a in alternatives)  # 12 PM was just booked
    assert ui["type"] == "slot_taken"


def test_booking_validation(desk):
    d = desk()
    assert "error" in d.book_visit("SH-102", "Asha", "12345", "kal", "11 am")[0]
    assert "error" in d.book_visit("SH-102", "", "9876543210", "kal", "11 am")[0]
    assert "error" in d.book_visit("SH-102", "Asha", "9876543210", "kal", "9 pm")[0]
    assert "error" in d.book_visit("SH-102", "Asha", "9876543210", "2026-10-01", "11 am")[0]
    assert "error" in d.book_visit("SH-999", "Asha", "9876543210", "kal", "11 am")[0]


def test_seeded_saturday_slot(store):
    saturday = TODAY + timedelta(days=3)
    assert store.is_taken("SH-102", saturday.isoformat(), "11:00")


def test_codes_are_unique(monkeypatch, store):
    codes = iter([1111, 1111, 2222])
    monkeypatch.setattr(bookings.random, "randint", lambda a, b: next(codes))
    first = store.create("SH-101", "A", "9876543210", "2026-10-20", "11:00")
    second = store.create("SH-101", "B", "9876543211", "2026-10-20", "12:00")
    assert first["code"] == "SH-1111" and second["code"] == "SH-2222"


def test_normalize_code():
    assert normalize_code("SH-2890") == "SH-2890"
    assert normalize_code("s h 2 8 9 0") == "SH-2890"
    assert normalize_code("एसएच २८९०") == "SH-2890"
    assert normalize_code("12") is None


def test_find_reschedule_and_cancel(desk, store):
    d = desk()
    booked, _ = d.book_visit("SH-109", "Asha", "9876543210", "2026-10-20", "4 pm")
    code = booked["confirmation_code"]

    found, ui = d.find_visits("98765 43210")
    assert found["count"] == 1 and ui["items"][0]["code"] == code

    # Another number sees nothing.
    assert d.find_visits("9000000000")[0]["count"] == 0

    moved, ui = d.reschedule_visit("9876543210", None, "2026-10-21", "5 pm")
    assert moved["rescheduled"] and ui["status"] == "rescheduled" and moved["confirmation_code"] == code
    assert store.get(code)["date"] == "2026-10-21" and store.get(code)["time"] == "17:00"
    assert not store.is_taken("SH-109", "2026-10-20", "16:00")  # old slot freed

    cancelled, ui = d.cancel_visit("9876543210", code)
    assert cancelled["cancelled"] and ui["status"] == "cancelled"
    assert d.find_visits("9876543210")[0]["count"] == 0
    assert not store.is_taken("SH-109", "2026-10-21", "17:00")  # slot free again


def test_reschedule_into_taken_slot_offers_alternatives(desk):
    d = desk()
    d.book_visit("SH-102", "Asha", "9876543210", "2026-10-16", "1 pm")
    result, ui = d.reschedule_visit("9876543210", None, "2026-10-15", "11 am")  # seeded: taken
    assert result["reason"] == "slot_taken" and ui["type"] == "slot_taken"


def test_manage_visit_errors(desk):
    d = desk()
    assert "error" in d.find_visits("123")[0]
    assert "error" in d.cancel_visit("9876543210", None)[0]  # nothing booked
    d.book_visit("SH-109", "Asha", "9876543210", "2026-10-20", "4 pm")
    d.book_visit("SH-111", "Asha", "9876543210", "2026-10-22", "4 pm")
    assert "several" in d.cancel_visit("9876543210", None)[0]["error"]
    assert "error" in d.cancel_visit("9876543210", "SH-0001")[0]


def test_bookings_survive_a_new_store(tmp_path):
    path = tmp_path / "t.db"
    first = BookingStore(path)
    first.seed(TODAY)
    booking = first.create("SH-109", "Asha", "9876543210", "2026-10-20", "11:00")
    second = BookingStore(path)
    second.seed(TODAY)  # re-seeding must not wipe real bookings
    assert second.get(booking["code"])["name"] == "Asha"
