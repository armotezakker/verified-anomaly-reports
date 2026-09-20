"""The report-generation prompt template and the deliberate-corruption
instructions used to build the faithfulness-checker test set.

The system prompt below is the actual template: it is a hard constraint on
what the model may use and say, not a docstring note. It applies to every
report this project generates, and the Guadalupe framing rule is written
directly into it rather than left as an assumption the model has to infer.
"""

REPORT_SYSTEM_PROMPT = """You are an automated system that writes short, plain-language incident summaries for water utility operators from sensor anomaly data. Follow these rules exactly. They are hard constraints, not suggestions.

1. Use ONLY the data given in the message below. Do not invent, assume, or infer a cause for the anomaly. Do not state a comparison to any historical event, another station, or a typical seasonal value unless that comparison is explicitly present in the data given to you.
2. Do not speculate. If the cause of the anomaly is not in the data, say only that the reading is anomalous relative to the stated baseline. Never phrase a guess as if it were a known fact.
3. Keep the report to 3 to 5 sentences.
4. Report factual sensor information only: what was measured, when, the value, and how it compares to the stated normal range. Do not add urgency and do not editorialize.
5. Hard requirement for any station on the Guadalupe River (site name containing "Guadalupe"): stay strictly technical. Report only flow rate, gauge behavior, timing, and rate of change relative to baseline. Do not dramatize the event in any way and do not reference human impact, casualties, injury, or any human toll under any circumstance, even if you can infer it from the station or date. This rule overrides any instinct toward narrative or emotional framing and applies with particular strictness here because this specific event was real and fatal.

Output only the incident summary text, nothing else."""


def format_context(record: dict) -> str:
    return (
        f"Station: {record['site_name']} ({record['site_id']})\n"
        f"Location: {record['latitude']}, {record['longitude']}\n"
        f"Parameter: {record['param_name']} ({record['param_code']})\n"
        f"Timestamp (UTC): {record['timestamp']}\n"
        f"Reading: {record['value']}\n"
        f"Normal range (trailing 14-day baseline): {record['baseline_low']} to {record['baseline_high']}, "
        f"median {record['baseline_median']}\n"
    )


# Each corrupted report gets exactly one of these injected. The instruction
# is given to the model as a rewrite task over an already-faithful report,
# so everything else about the report's tone and structure stays the same.
CORRUPTION_INSTRUCTIONS = {
    "wrong_station": (
        "Rewrite the report below, changing only the station or river name it mentions to a "
        "different, plausible-sounding but incorrect name. Keep every other fact, number, and "
        "the overall structure the same. Output only the rewritten report, nothing else."
    ),
    "wrong_parameter": (
        "Rewrite the report below so it describes the wrong parameter: if it reports streamflow, "
        "rewrite it to instead report water temperature with a plausible fabricated value and unit "
        "(or the reverse if it reports temperature). Keep the station, timestamp, and overall "
        "structure the same. Output only the rewritten report, nothing else."
    ),
    "fabricated_cause": (
        "Rewrite the report below, adding one specific, plausible-sounding cause for the anomaly "
        "that is not present anywhere in the original (for example, a specific storm, a dam "
        "release, or an equipment fault), stated as if it were a known fact. Keep everything else "
        "the same. Output only the rewritten report, nothing else."
    ),
    "fabricated_comparison": (
        "Rewrite the report below, adding one specific, plausible-sounding comparison to a "
        "historical event or typical seasonal value that is not present anywhere in the original "
        "(for example, 'the highest reading since 2015' or 'well above the typical spring "
        "average'), stated as if it were a known fact. Keep everything else the same. Output only "
        "the rewritten report, nothing else."
    ),
    "wrong_value": (
        "Rewrite the report below, changing the specific numeric reading it states to a different "
        "plausible number for this parameter, without changing the severity language around it, so "
        "the number in the text no longer matches the true value. Keep everything else the same. "
        "Output only the rewritten report, nothing else."
    ),
}
