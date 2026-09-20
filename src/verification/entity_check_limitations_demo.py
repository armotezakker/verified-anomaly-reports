"""Demonstrate, not just assert, the entity check's own failure modes.

The check passed all 27 real faithful reports with no false positives.
That does not mean it is robust in general, it means the LLM happened to
always use full station names in this run. This script constructs
synthetic report snippets that a report writer could plausibly produce
and shows where the naive substring check would get the wrong answer.
"""

from src.verification.entity_check import check_entity_match

CASES = [
    # These three are genuine false-positive risks: the station reference is
    # actually correct, phrased in a way the registry doesn't recognize.
    ("LIMITATION: nickname not in registry", "11447650", "A reading at the Sac River gauge near Freeport was well above normal."),
    ("LIMITATION: abbreviated river name", "03451500", "The French B. River gauge at Asheville recorded an elevated reading."),
    ("LIMITATION: station referenced only by USGS ID", "01646500", "Site 01646500 recorded a streamflow reading above the normal range."),
    # This one is a correct FAIL, not a limitation: it is an actually wrong
    # station reference (the wrong one of the two Guadalupe gauges), shown
    # here to distinguish a real catch from a false positive above.
    ("CORRECT CATCH: wrong Guadalupe gauge", "08166200", "Streamflow at Guadalupe River at Comfort, TX was elevated."),
    ("for contrast: full correct name", "11447650", "Streamflow at Sacramento River at Freeport was elevated."),
]


def main() -> None:
    for label, site_id, text in CASES:
        result = check_entity_match(text, site_id)
        verdict = "PASS" if result["passed"] else "FAIL"
        print(f"[{verdict}] {label}")
        print(f"    text: {text}")
        print(f"    reason: {result['reason']}")
        print()


if __name__ == "__main__":
    main()
