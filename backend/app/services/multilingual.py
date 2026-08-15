"""
app/services/multilingual.py — Cross-Lingual Translation & Detection Layer (Feature 8).

Detects non-English queries (e.g. German "US Inflationsrate Mai 2024", Spanish "Tasa de inflación de EE. UU.")
and translates them into English for unified vector & graph retrieval.
"""
from __future__ import annotations

import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)

# Common non-English financial keywords and phrases
_MULTILINGUAL_DICTIONARY = {
    # German
    "inflationsrate": "inflation rate",
    "leitzins": "fed interest rate",
    "bruttoinlandsprodukt": "gdp growth",
    "mai": "may",
    "us-inflation": "us inflation",
    # Spanish
    "tasa de inflación": "inflation rate",
    "tasa de interés": "fed interest rate",
    "crecimiento del pib": "gdp growth",
    "mayo": "may",
    "ee. uu.": "us",
    # French
    "taux d'inflation": "inflation rate",
    "taux d'intérêt": "fed interest rate",
    "croissance du pib": "gdp growth",
    "mai": "may",
    "états-unis": "us",
}


def detect_and_translate_query(query: str) -> Tuple[str, str]:
    """
    Detects non-English queries and translates financial terms to English.
    Returns: (translated_query, detected_language_code)
    """
    query_clean = query.strip()
    query_low = query_clean.lower()

    detected_lang = "en"
    translated = query_clean

    # Detect German
    if any(k in query_low for k in ["inflationsrate", "leitzins", "bruttoinlandsprodukt", "mai"]):
        detected_lang = "de"
    # Detect Spanish
    elif any(k in query_low for k in ["tasa de", "interés", "crecimiento del pib", "mayo", "ee. uu."]):
        detected_lang = "es"
    # Detect French
    elif any(k in query_low for k in ["taux d'", "croissance du pib", "états-unis"]):
        detected_lang = "fr"

    if detected_lang != "en":
        for k, v in _MULTILINGUAL_DICTIONARY.items():
            if k in query_low:
                translated = re.sub(re.escape(k), v, translated, flags=re.IGNORECASE)

        logger.info("Cross-Lingual Layer: Detected lang='%s'. Translated '%s' -> '%s'", detected_lang, query_clean, translated)

    return translated, detected_lang
