"""Deterministic station entity-match check.

Not an LLM call. Plain substring matching against a small registry of the
six known stations, run before and independent of the Noul faithfulness
score. Built specifically because phase 3 found Noul misses a station
name swap when the rest of the report is numerically consistent
(r24_corrupt, "Sacramento R" changed to "American R", scored 0.90 by
Noul). A deterministic check is a better fit for this failure mode than
another probabilistic one: whether a specific known string is present in
the text is not a judgment call.

Each station has a primary token (the river or creek name) and, only
where two stations share a river name, a disambiguating token (the
place name). The check fails a report if the true station's primary
token is missing, or if a disambiguator is required and missing.

This is deliberately naive and its known failure modes are documented in
the README rather than assumed away: it will not catch a swap to another
station that happens to share the same primary token with no other
identifying change, and it will falsely fail a report that refers to its
station only by a nickname or abbreviation not in the registry.
"""

STATION_REGISTRY = {
    "03451500": {"primary": "french broad", "disambiguator": None},
    "08166200": {"primary": "guadalupe", "disambiguator": "kerrville"},
    "08167000": {"primary": "guadalupe", "disambiguator": "comfort"},
    "01646500": {"primary": "potomac", "disambiguator": None},
    "11447650": {"primary": "sacramento", "disambiguator": "freeport"},
    "04234000": {"primary": "fall creek", "disambiguator": None},
}


def check_entity_match(report_text: str, true_site_id: str) -> dict:
    text = report_text.lower()
    entry = STATION_REGISTRY[true_site_id]

    if entry["primary"] not in text:
        return {
            "passed": False,
            "reason": f"primary station token '{entry['primary']}' not found in report text",
        }

    if entry["disambiguator"] and entry["disambiguator"] not in text:
        return {
            "passed": False,
            "reason": f"disambiguating token '{entry['disambiguator']}' not found in report text (river name shared by multiple stations)",
        }

    return {"passed": True, "reason": "station tokens present"}
