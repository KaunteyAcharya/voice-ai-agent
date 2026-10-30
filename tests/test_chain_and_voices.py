from dataclasses import replace

import pytest

import voices
from config import load_config
from llm_chain import ChainLink, parse_chain
from prompts import FILLERS, GREETING, fixed_phrases


@pytest.fixture
def cfg():
    return replace(
        load_config(),
        llm_provider="gemini",
        gemini_llm_model="gemini-3.1-flash-lite",
        google_api_key="g",
        groq_api_key="q",
        sarvam_api_key="",
        llm_fallback_chain=("groq:openai/gpt-oss-120b", "groq:qwen/qwen3.8-27b", "sarvam:sarvam-105b", "nonsense"),
    )


def test_chain_starts_with_primary_and_skips_unkeyed_backups(cfg):
    chain = parse_chain(cfg)
    assert chain[0] == ChainLink("gemini", "gemini-3.1-flash-lite")
    assert [link.label for link in chain[1:]] == ["groq:openai/gpt-oss-120b", "groq:qwen/qwen3.8-27b"]


def test_chain_without_groq_key_is_just_the_primary(cfg):
    assert len(parse_chain(replace(cfg, groq_api_key=""))) == 1


def test_chain_does_not_repeat_the_primary(cfg):
    chain = parse_chain(replace(cfg, llm_provider="groq", llm_fallback_chain=("groq:openai/gpt-oss-120b",)))
    assert [link.label for link in chain] == ["groq:openai/gpt-oss-120b"]


def test_lang_key():
    assert voices.lang_key("hi-IN") == "hi"
    assert voices.lang_key("en-IN") == "en"
    assert voices.lang_key(None) == "en"


def test_sentence_split_for_prewarm():
    assert voices._sentences(GREETING["en"]) == [
        "Hi, I'm Aditi from Tatsat Real Estate.",
        "Are you looking to buy or rent a home?",
    ]
    assert len(voices._sentences(GREETING["hi"])) == 2  # split on the Devanagari danda
    assert voices._sentences("Just a second.") == []


def test_audio_cache_is_bounded():
    voices._audio_cache.clear()
    for i in range(voices._MAX_CACHED + 5):
        voices._cache_put("v", f"line {i}", b"\x00\x01")
    assert len(voices._audio_cache) == voices._MAX_CACHED
    assert voices._cache_get("v", "line 0") is None
    assert voices._cache_get("v", f"line {voices._MAX_CACHED + 4}") == b"\x00\x01"
    voices._audio_cache.clear()


def test_fixed_phrases_cover_both_languages():
    for lang in ("en", "hi"):
        phrases = fixed_phrases(lang)
        assert GREETING[lang] in phrases and set(FILLERS[lang]) <= set(phrases)


def test_speech_rate_helpers():
    assert voices.edge_rate(1.0) == "+0%"
    assert voices.edge_rate(1.25) == "+25%"
    assert voices.edge_rate(0.9) == "-10%"
    assert voices.clamp_rate(5) == 2.0 and voices.clamp_rate("fast") == 1.0
    # Different speeds must not share cached audio.
    assert voices.edge_cache_voice("hi-IN-SwaraNeural", 1.0) != voices.edge_cache_voice("hi-IN-SwaraNeural", 1.25)


def test_speech_cleanup_fixes_gender_and_lists():
    from bot import clean_for_speech

    assert clean_for_speech("मैं बुक कर सकता हूँ।") == "मैं बुक कर सकती हूँ।"
    assert clean_for_speech("मैं चेक कर रहा हूँ और बताऊँगा।") == "मैं चेक कर रही हूँ और बताऊँगी।"
    assert clean_for_speech("आप देख सकते हैं।") == "आप देख सकते हैं।"  # second person untouched
    assert clean_for_speech("- Sapna Greens\n- Mansi Apartments") == "Sapna Greens\nMansi Apartments"
    assert clean_for_speech("**Sapna Greens** is 82 lakh. [call ends]").strip() == "Sapna Greens is 82 lakh."


def test_idle_warning_mentions_the_wait():
    from prompts import IDLE_GOODBYE, idle_prompt

    assert "10 more seconds" in idle_prompt("en", 10)
    assert "10 सेकंड" in idle_prompt("hi", 10)
    for lang in ("en", "hi"):
        assert idle_prompt(lang, 10) in fixed_phrases(lang, 10) and IDLE_GOODBYE[lang] in fixed_phrases(lang, 10)


def test_hindi_listing_text_is_everyday_hindi():
    from listings import AMENITY_HI, LISTINGS

    text = " ".join(l["possession"]["hi"] + l["description"]["hi"] for l in LISTINGS) + " ".join(AMENITY_HI.values())
    for formal in ("निर्माणाधीन", "उपलब्ध", "नौकरीपेशा", "अनुमति", "एअदिति"):
        assert formal not in text
