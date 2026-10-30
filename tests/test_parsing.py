from datetime import date, time

import pytest

from listings import CRORE, LAKH
from parsing import (
    format_amount_display,
    format_amount_spoken,
    format_time_spoken,
    normalize_phone,
    parse_amount,
    parse_visit_date,
    parse_visit_time,
)

WED = date(2026, 10, 14)  # a Wednesday


@pytest.mark.parametrize(
    "value,purpose,expected",
    [
        ("90 lakh", "buy", 90 * LAKH),
        ("90L", "buy", 90 * LAKH),
        ("1.2 crore", "buy", 120 * LAKH),
        ("1 crore 20 lakh", "buy", 120 * LAKH),
        ("1 crore 20", "buy", 120 * LAKH),
        ("₹75,00,000", "buy", 75 * LAKH),
        ("सवा करोड़", "buy", 125 * LAKH),
        ("डेढ़ करोड़", "buy", 150 * LAKH),
        ("90 लाख", "buy", 90 * LAKH),
        ("९० लाख", "buy", 90 * LAKH),
        (90, "buy", 90 * LAKH),
        (9_000_000, "buy", 9_000_000),
        ("30000", "rent", 30_000),
        ("30k", "rent", 30_000),
        ("30 हज़ार", "rent", 30_000),
        (25, "rent", 25_000),
        ("", "buy", None),
        (None, "buy", None),
        ("no idea", "buy", None),
    ],
)
def test_parse_amount(value, purpose, expected):
    assert parse_amount(value, purpose) == expected


def test_format_amount_spoken():
    assert format_amount_spoken(82 * LAKH, "en") == "82 lakh rupees"
    assert format_amount_spoken(125 * LAKH, "en") == "1 crore 25 lakh rupees"
    assert format_amount_spoken(2 * CRORE, "hi") == "2 करोड़ रुपये"
    assert format_amount_spoken(28_000, "hi") == "28 हज़ार रुपये"
    assert format_amount_spoken(60_748, "en") == "60 thousand 748 rupees"


def test_format_amount_display():
    assert format_amount_display(95 * LAKH) == "₹95 L"
    assert format_amount_display(125 * LAKH) == "₹1.25 Cr"
    assert format_amount_display(28_000, "rent") == "₹28,000/mo"
    assert format_amount_display(1_234_567) == "₹12.35 L"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2026-10-20", date(2026, 10, 20)),
        ("tomorrow", date(2026, 10, 15)),
        ("kal", date(2026, 10, 15)),
        ("कल शाम", date(2026, 10, 15)),
        ("aavtikale", date(2026, 10, 15)),
        ("parso", date(2026, 10, 16)),
        ("परसों", date(2026, 10, 16)),
        ("today", WED),
        ("Saturday", date(2026, 10, 17)),
        ("shanivar", date(2026, 10, 17)),
        ("शनिवार", date(2026, 10, 17)),
        ("Wednesday", date(2026, 10, 21)),
        ("20 October", date(2026, 10, 20)),
        ("20 अक्टूबर", date(2026, 10, 20)),
        ("5 January", date(2027, 1, 5)),
        ("20/10", date(2026, 10, 20)),
        ("next week sometime", None),
    ],
)
def test_parse_visit_date(text, expected):
    assert parse_visit_date(text, today=WED) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("11 am", time(11, 0)),
        ("4:30 pm", time(16, 30)),
        ("16:00", time(16, 0)),
        ("4 baje", time(16, 0)),
        ("शाम 5 बजे", time(17, 0)),
        ("subah 11 baje", time(11, 0)),
        ("dopahar 2", time(14, 0)),
        ("noon", time(12, 0)),
        ("12 pm", time(12, 0)),
        ("whenever", None),
    ],
)
def test_parse_visit_time(text, expected):
    assert parse_visit_time(text) == expected


def test_format_time_spoken():
    assert format_time_spoken(time(16, 30), "en") == "4:30 PM"
    assert format_time_spoken(time(11, 0), "hi") == "सुबह 11 बजे"
    assert format_time_spoken(time(17, 0), "hi") == "शाम 5 बजे"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("98765 43210", "9876543210"),
        ("+91 98765-43210", "9876543210"),
        ("09876543210", "9876543210"),
        ("९८७६५४३२१०", "9876543210"),
        ("12345", None),
        ("1234567890", None),  # Indian mobiles start with 6-9
    ],
)
def test_normalize_phone(value, expected):
    assert normalize_phone(value) == expected
