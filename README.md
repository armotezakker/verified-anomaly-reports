# verified-anomaly-reports

Detects anomalies in real water sensor data, drafts plain-language incident
reports with an LLM, and checks those reports against the underlying data
with a faithfulness-checking model (Typesafe / Noul) before they would reach
an operator. Built as a portfolio project aimed at Xylem's stated interest
in applying modern AI tools to data exploration and decision support on
operational water data.

Phase 1 pulled and inspected the raw data. Phase 2 adds a deliberately
simple anomaly detector. Phase 3 generates and verifies a curated sample
of incident reports, including a deliberate test of whether the
faithfulness checker actually catches injected errors. Phase 4 closes the
one gap phase 3 found with a deterministic check and evaluates the
combined system. This is the project's central result: semantic
verification (Noul) and a deterministic check catch different failure
modes, and a trustworthy report pipeline needs both.

## Data source

USGS National Water Information System (NWIS), instantaneous values
service (`waterservices.usgs.gov/nwis/iv`). Public, no API key required.

## Stations

Six real USGS gauges, chosen to mix streamflow and temperature, a large
regulated river with a small flashy creek, and two known real flood events
with calm baseline periods:

| Site ID | Name | Parameters | Why |
|---|---|---|---|
| 03451500 | French Broad River at Asheville, NC | streamflow, temperature | Hurricane Helene flood, Sept 27 2024 |
| 08166200 | Guadalupe River near Hunt, TX | streamflow | Texas Hill Country flash flood, July 4 2025 |
| 08167000 | Guadalupe River at Comfort, TX | streamflow | Same flood, downstream gauge, corroborates propagation |
| 01646500 | Potomac River near Washington, DC (Little Falls) | streamflow, temperature | Mid-Atlantic baseline, several moderate flood peaks through the year |
| 11447650 | Sacramento River at Freeport, CA | streamflow, temperature | Large regulated West coast river, tidal influence near the Delta |
| 04234000 | Fall Creek near Ithaca, NY | streamflow | Small flashy Northeast creek, contrast to the large rivers above |

Parameter codes: `00060` streamflow (cubic feet per second), `00010` water
temperature (degrees Celsius).

### Guadalupe River flood: framing rule

The July 4, 2025 Guadalupe River flood (both the Hunt and Comfort gauges)
was a real, fatal event. This is a deliberate, stated choice, not an
oversight: every report, figure, and piece of documentation in this
project that touches that station stays strictly technical (flow rate,
gauge height, rate of rise, timing) and never narrates the event
dramatically or references the human toll. This rule applies to the
report-generation prompt templates from phase 3 onward as well.

## Date range

2024-09-01 to 2025-08-31 (one year). Chosen to open right at the start of
the Helene flood and close just after the Guadalupe flood, while covering a
full seasonal temperature cycle for the temperature stations.

## Pipeline

```
src/data/fetch_nwis.py    pulls raw JSON per station into data/raw/
src/data/parse_nwis.py    flattens raw JSON into data/processed/readings.parquet
src/analysis/inspect_data.py   prints summary stats, writes reports/figures/*.png
src/detection/rolling_iqr.py   the rolling time-based IQR anomaly detector
src/analysis/run_detection.py  runs the detector on all series, writes data/processed/anomalies.csv and anomaly_context.json
src/analysis/flag_rate_sanity_check.py   zooms into representative weeks to check the flag rate by eye
src/analysis/sample_for_reports.py   picks the curated sample of anomalies for phase 3
src/generation/prompts.py   the report-generation prompt template and the corruption instructions
src/generation/run_generation.py   generates faithful reports, then deliberately corrupts a third of them
src/verification/run_faithfulness_eval.py   runs every report through Noul, reports the evaluation honestly
src/verification/plot_faithfulness_distribution.py   the Noul-alone separation figure
src/verification/entity_check.py   the deterministic station entity-match check
src/verification/entity_check_limitations_demo.py   demonstrates the entity check's own false-positive risks
src/verification/run_combined_eval.py   entity check + Noul combined, full confusion matrix
src/verification/plot_combined_distribution.py   the combined-system separation figure
scripts/typesafe_sanity_check.py   one Noul call to confirm the faithfulness checker works
```

Run with the repo's own venv:

```
.venv/bin/python src/data/fetch_nwis.py
.venv/bin/python src/data/parse_nwis.py
.venv/bin/python src/analysis/inspect_data.py
TYPESAFE_API_KEY=... .venv/bin/python scripts/typesafe_sanity_check.py
```

## Inspection findings

382,516 readings across 6 stations, 9 station-parameter series.

Sampling is not a clean uniform 15 minutes everywhere. Four series mix
5-minute and 15-minute intervals within the same year (Guadalupe, Potomac),
most likely a mid-year telemetry cadence change at those gauges rather than
event-triggered sampling. Fall Creek has the most real gaps, 179 gaps over
one hour totaling about 560 hours, consistent with a small Northeast creek
gauge affected by winter icing.

Sacramento water temperature carries two concurrent sensors under the same
parameter code ("Right Bank Pump Stand" and "BGC Project, East Fender").
They track each other closely (see the plot), so this looks like a real
redundant sensor pair rather than a data error, but any pipeline built on
top of this data needs an explicit policy for handling it rather than
silently summing both.

Sacramento streamflow also has 5 negative readings (down to -305 cfs) on
2024-11-14, consistent with tidal or pumping-driven reverse flow near the
Delta rather than a sensor fault, visible as the daily oscillation pattern
in the plot.

Confirmed genuine anomalous events from the pulled data itself:

- French Broad River at Asheville: streamflow jumps from a baseline around
  1,600 cfs to a peak of 113,000 cfs on 2024-09-27, Hurricane Helene.
- Guadalupe River near Hunt: baseline near 2 cfs, peak of 298,000 cfs on
  2025-07-04, the Texas Hill Country flash flood.
- Guadalupe River at Comfort: same event, downstream, peak of 177,000 cfs
  a few hours later on 2025-07-04.
- Potomac River: a peak of 156,000 cfs on 2025-05-16, well above the
  several smaller seasonal flood peaks earlier in the year.
- Fall Creek: three distinct spring/early-summer spikes above 1,300 cfs
  against a baseline usually under 100 cfs.

Full numeric summary: `data/processed/station_summary.csv` (not committed,
regenerate with the pipeline above). Plots: `reports/figures/<site_id>.png`.

## Faithfulness checker sanity check

`scripts/typesafe_sanity_check.py` sends one Noul question built from the
Guadalupe near Hunt flood peak found above, asking whether a one-sentence
generated answer is faithful to the retrieved context. Confirmed working
from this repo's own venv, `TYPESAFE_API_KEY` read from the environment
only, never written to a file in this repo.

## Phase 2: anomaly detection

Deliberately simple, not the focus of this project. A rolling, time-based
IQR (interquartile range) fence per station-parameter series: for each
point, compute the median and IQR of the trailing 14 days of prior points
only, and flag the point if it falls outside `median +/- 3 * IQR`. Full
reasoning in `src/detection/rolling_iqr.py`. In short: IQR over a rolling
z-score because streamflow is heavily right-skewed and a flood inside the
window would inflate a rolling mean/standard deviation enough to start
masking itself; a time-based window rather than a fixed row count so the
mixed 5-minute/15-minute sampling does not change how much history the
detector is actually looking at.

Data quality issues from phase 1, resolved before detection:

- Sacramento water temperature's two concurrent sensors are averaged by
  timestamp before detection (both sensors agree at 99.0% of timestamps,
  34,703 of 35,040; the other 337 fall back to whichever one reported).
  This produces one series instead of two competing or double-counted
  ones.
- Mixed 5-minute/15-minute sampling is handled by the time-based rolling
  window itself (see above), not by resampling or interpolating the raw
  values.

Run with:

```
.venv/bin/python -m src.analysis.run_detection
```

### Results

| Site | Parameter | Readings scored | Anomalies flagged | % flagged |
|---|---|---|---|---|
| 03451500 French Broad | streamflow | 34,211 | 2,923 | 8.5% |
| 03451500 French Broad | temperature | 34,289 | 278 | 0.8% |
| 08166200 Guadalupe (Hunt) | streamflow | 42,038 | 2,535 | 6.0% |
| 08167000 Guadalupe (Comfort) | streamflow | 41,947 | 2,298 | 5.5% |
| 01646500 Potomac | streamflow | 46,291 | 2,326 | 5.0% |
| 01646500 Potomac | temperature | 47,578 | 581 | 1.2% |
| 11447650 Sacramento | streamflow | 34,812 | 783 | 2.2% |
| 11447650 Sacramento | temperature | 34,840 | 206 | 0.6% |
| 04234000 Fall Creek | streamflow | 29,804 | 2,300 | 7.7% |

Total: 14,230 flagged of 345,810 scored, 4.11% overall.

The flagged fractions are not tuned down. A 14-day trailing IQR fence
flags every meaningful rise above recent baseline, not only the five
marquee events below, so most stations show flagged points scattered
across many smaller storms and thaws through the year in addition to the
big ones. Confirmed against the overlay plots in
`reports/figures/<site_id>_<param_code>_anomalies.png`.

### Zero floor fix on the streamflow lower bound

The IQR fence's lower bound is now clipped to never go below zero for
streamflow series (parameter `00060`), since streamflow cannot physically
be negative in the ordinary case. Not applied to temperature, since water
near freezing can legitimately read a hair below zero on some sensors.

Re-ran detection with the fix: 14,225 anomalies before, 14,230 after,
exactly 5 added, all 5 at Sacramento streamflow. Those 5 are precisely the
negative readings documented in phase 1 (the 2024-11-14 tidal backflow
event, down to -305 cfs), which the unfloored fence had not been flagging
because the local trailing IQR at that station was wide enough to push
the unfloored lower bound below -305. No other series changed at all,
because their lower bounds never actually reached zero in the unfloored
version. The fix is monotonic by construction: it can only raise a lower
bound, so it can only add flags, never remove one. Worth noting as an
honest wrinkle, not a contradiction: streamflow being negative there is a
real, physically explainable tidal effect, not a sensor fault, but it is
still rare enough (5 readings out of a year) that flagging it for an
operator's attention is the right behavior, physically-grounded floor or
not.

### Flag rate sanity check

3.7 to 4.1 percent overall, with several series at 5 to 8.5 percent,
looked high enough to check by eye before trusting it for phase 3.
`src/analysis/flag_rate_sanity_check.py` computes flags per week outside
the known event windows for French Broad streamflow (8.5%) and Fall Creek
streamflow (7.7%), the two highest-rate series among the ones without a
marquee flood dominating the whole year.

The result was not overreaction. 31 of 50 non-event weeks at French Broad
and 28 of 51 at Fall Creek have zero flags at all; flags arrive in bursts
across the remaining 19 and 23 weeks respectively, not scattered evenly
day to day. Plotted a representative burst week for each
(`reports/figures/sanity_check_03451500_00060.png` and
`sanity_check_04234000_00060.png`): in both, the flagged points sit
exactly on visually obvious rises above the shaded normal-range band, rain
events that clearly leave baseline, and stop being flagged as soon as the
value drops back inside the band. The high aggregate percentage comes
from the fact that this year of real river data contains many genuine
storm events beyond the five marquee ones, each one flagged for its full
multi-hour or multi-day duration at sub-daily resolution, not from the
detector reacting to ordinary noise.

Verdict: no retuning. `k = 3` and the 14-day window stay as originally
chosen. Tightening them further would mean suppressing real, visually
confirmed departures from baseline to make the summary number look
smaller, which is the wrong trade for a project whose next phase is about
whether reports stay honest to the data, not about hiding how much
real variability six rivers actually have over a year.

### Known real events: caught or missed

All five known real events from phase 1 were caught, each with multiple
flagged points within 6 hours of the documented peak:

- Hurricane Helene, French Broad River streamflow: caught, 49 flagged
  points near the 2024-09-27 peak.
- TX Hill Country flood, Guadalupe near Hunt: caught, 39 flagged points
  near the 2025-07-04 peak.
- TX Hill Country flood, Guadalupe at Comfort: caught, 32 flagged points
  near the 2025-07-04 peak.
- Potomac River peak flow: caught, 49 flagged points near the 2025-05-16
  peak.
- Fall Creek spring spike: caught, 49 flagged points near the 2025-03-06
  peak.

No known event was missed in this run. That is a genuine result of the
run, not a target that was tuned toward; thresholds were picked once from
first principles (`k = 3`, a 14-day window) and left alone. If a future
change to the station set or date range produces a miss, that should be
reported the same way, not adjusted away.

### Known limitations, stated plainly

- The detector works at the level of individual readings, not events. A
  multi-hour flood produces dozens of flagged points rather than one. The
  packaged anomaly context (below) is at the same per-reading granularity;
  grouping consecutive flagged points into a single incident is phase 3's
  job, not solved here.
- A trailing window that includes a past flood will have an inflated
  baseline for the following two weeks, which can under-flag a second,
  smaller event soon after a big one. Not observed in this year of data
  for these six stations, but a known structural limitation of any
  trailing-window approach.
- Fixed: the IQR fence's lower bound is now floored at zero for
  streamflow (see above). This was a real gap, not by design, and cheap
  to fix, so it was fixed rather than left as a caveat.

Anomaly log: `data/processed/anomalies.csv` (not committed). Packaged
context for phase 3: `data/processed/anomaly_context.json` (not
committed), one record per flagged reading with exactly: site id, site
name, latitude, longitude, parameter code and name, timestamp, the
anomalous value, and the baseline (median, low, high) it was compared
against. Nothing else, so it can serve as the ground truth the
faithfulness checker verifies generated reports against.

## Phase 3: generate and verify a curated sample of reports

Not all 14,230 flagged readings get a report. `src/analysis/sample_for_reports.py`
selects a deliberate sample of 27: the 5 known real major events (Helene,
both Guadalupe gauges, the Potomac peak, the Fall Creek spike) as core
"should clearly matter" cases, plus 22 more stratified across all 9
station-parameter series and 3 severity tiers (borderline, moderate,
severe, computed as distance from the nearest baseline bound relative to
the width of the normal range), so the sample isn't just the five biggest
spikes. Fixed random seed for reproducibility. Saved to
`data/processed/report_sample.json` (not committed).

### Report generation

`src/generation/prompts.py` holds the actual prompt template, not just a
description of one. The system prompt is a hard constraint: use only the
given context (station, location, parameter, timestamp, value, baseline),
never invent a cause or a historical comparison, never speculate as fact,
keep it to 3 to 5 sentences, and for any station with "Guadalupe" in the
name, stay strictly technical, flow rate, timing, rate of change, and
never reference human impact under any circumstance. This is written
directly into the system prompt sent to the model, not left as a comment
for a human reader.

`src/generation/run_generation.py` generates one report per sampled
anomaly with `claude-haiku-4-5-20251001` (`ANTHROPIC_API_KEY` from the
environment only). Spot-checked all 7 reports touching Helene or the
Guadalupe gauges: none dramatize the event or reference casualties, all
stay to flow rate, baseline comparison, and timing, for example "Streamflow
at Guadalupe River at Kerrville measured 298,000 ft³/s at 11:45 UTC on
July 4, 2025. This value is anomalous relative to the 14-day baseline
normal range of 0.0 to 21.65 ft³/s... No information regarding the cause
of this anomaly is available in the sensor data."

### Deliberate corruption

For 9 of the 27 reports (a third), a second Anthropic call rewrites the
faithful report with exactly one labeled error, chosen from: wrong
station name, wrong parameter, a fabricated cause, a fabricated
historical comparison, or a value that no longer matches the data.
Distribution: 2 wrong_station, 2 wrong_parameter, 1 wrong_value, 2
fabricated_cause, 2 fabricated_comparison. Both versions of each
corrupted report are kept, faithful and corrupted, always checked against
the same true underlying context. All 36 reports (27 faithful + 9
corrupted) saved to `data/processed/reports.json` (not committed).

Example, `fabricated_cause` on the Sacramento streamflow report r27: the
faithful version ends "The measured flow is approximately 1.53 times the
upper bound of the normal range. No information on rate of change or
cause is available in the sensor data provided." The corrupted version
inserts "The anomaly is attributed to the scheduled release of water from
Folsom Dam on 2024-11-25 at 12:30 UTC to manage reservoir levels ahead of
the forecasted atmospheric river event", specific, plausible, and entirely
invented.

### Faithfulness evaluation

`src/verification/run_faithfulness_eval.py` runs all 36 reports through
Noul, checking the report text against the same packaged context it was
generated from (the true one, even for corrupted reports). Results in
`data/processed/faithfulness_eval.csv` (not committed).

| Group | n | mean P(faithful) | std | min | max |
|---|---|---|---|---|---|
| Faithful | 27 | 0.847 | 0.138 | 0.46 | 0.96 |
| Corrupted (all) | 9 | 0.160 | 0.285 | 0.01 | 0.90 |

By error type (corrupted only), mean P(faithful):

| Error type | n | mean | min | max |
|---|---|---|---|---|
| wrong_parameter | 2 | 0.010 | 0.01 | 0.01 |
| wrong_value | 1 | 0.020 | 0.02 | 0.02 |
| fabricated_cause | 2 | 0.065 | 0.06 | 0.07 |
| fabricated_comparison | 2 | 0.075 | 0.07 | 0.08 |
| wrong_station | 2 | 0.560 | 0.22 | 0.90 |

At the natural threshold of 0.5: 26 of 27 faithful reports correctly
scored faithful, 1 false positive (r22, a genuinely faithful Sacramento
temperature report, scored 0.46, just under the line). 8 of 9 corrupted
reports correctly scored unfaithful, 1 false negative (r24_corrupt,
scored 0.90): a `wrong_station` swap of "Sacramento R at Freeport CA" to
"American R at Freeport CA", a plausible real nearby river name, missed
completely.

Honest read: the checker separates the two groups well overall (0.847 vs
0.160 mean, most corrupted reports scored under 0.1) and catches numeric
and content fabrications reliably, wrong parameter, wrong value,
fabricated cause, and fabricated comparison all scored at or under 0.08
in every instance. `wrong_station` is clearly the hardest error type: one
instance was caught (0.22) and one was missed outright (0.90), because
the substituted name was locally plausible and every number and timestamp
in the report still matched the true data. That is a real, useful limit
on what this faithfulness checker catches on its own, an entity-identity
swap where everything else checks out is a weaker signal for it than a
fact that actively contradicts the numbers, and it is reported here
rather than tuned away by relabeling the threshold.

Distribution figure: `reports/figures/faithfulness_distribution.png`,
individual P(faithful) scores for faithful reports and each error type,
threshold line at 0.5. `wrong_station` is the only category that visibly
straddles the threshold.

## Phase 4: closing the wrong_station gap with a deterministic check

Phase 3 found one real weak spot: Noul missed a `wrong_station`
corruption outright, scoring 0.90 for a report that said "American R at
Freeport CA" instead of "Sacramento R at Freeport CA", because every
number and timestamp still matched and the substituted name was locally
plausible. Whether a specific station name appears in a specific piece of
text is not a judgment call, it is exactly the kind of check deterministic
code does perfectly and a semantic model has no particular advantage at.
So the fix is not a better prompt or a different threshold, it's a second,
independent check of a different kind.

### The check

`src/verification/entity_check.py`. A small registry of the six stations,
each with a primary token (the river or creek name) and, only for the two
Guadalupe gauges that share a river name, a disambiguating place name
("kerrville" or "comfort"). The check fails a report if the true
station's primary token is missing from the text, or if the
disambiguator is required and missing. Plain substring matching, no LLM
call, runs before and independent of the Noul score.

### Confirming it closes the gap

Both `wrong_station` cases from phase 3, re-checked directly:

```
report_id    p_faithful  noul_flags_untrustworthy  entity_check_passed  combined_flags_untrustworthy
r24_corrupt        0.90                     False                 False                          True
r13_corrupt        0.22                      True                 False                          True
```

r24_corrupt is the one Noul missed outright (0.90, would have passed
alone); the entity check catches it on its own, `sacramento` is not in
"American R at Freeport CA". r13_corrupt is the one Noul had already
caught (0.22); the entity check independently catches it too, `french
broad` is not in "French Creek River at Asheville, NC". Both are now
caught by a signal Noul isn't involved in.

### Does the entity check introduce new false positives

Checked directly against all 27 faithful reports: zero. The entity check
passes every one, including the Potomac reports that vary their phrasing
("Little Falls", "(Little Falls)", "Little Falls Pump Station") and the
two Guadalupe gauges correctly disambiguated by their place names. That
is a true statement about this specific 27-report sample, not a claim
that the check is robust in general, so it was stress-tested separately
with `src/verification/entity_check_limitations_demo.py` on synthetic
text the real sample never produced:

```
[FAIL] LIMITATION: nickname not in registry
    text: A reading at the Sac River gauge near Freeport was well above normal.
[FAIL] LIMITATION: abbreviated river name
    text: The French B. River gauge at Asheville recorded an elevated reading.
[FAIL] LIMITATION: station referenced only by USGS ID
    text: Site 01646500 recorded a streamflow reading above the normal range.
[FAIL] CORRECT CATCH: wrong Guadalupe gauge
    text: Streamflow at Guadalupe River at Comfort, TX was elevated.
[PASS] for contrast: full correct name
    text: Streamflow at Sacramento River at Freeport was elevated.
```

The first three are genuine false-positive risks: a correct station
reference, phrased in a way the registry doesn't recognize (a nickname,
an abbreviation, an ID-only reference), gets wrongly flagged. The fourth
is not a limitation, it's the check correctly catching an actually wrong
station reference (the wrong one of the two Guadalupe gauges), included
to show the difference between a real catch and a false positive. This
naive string match works here because the generation prompt template
consistently produces full station names. It would need a larger alias
registry (or a fallback to matching on latitude/longitude or the USGS
site ID, both of which are also in the packaged context) before being
trusted on report text from a different generator with looser phrasing.

### Combined system confusion matrix

| | Noul alone | Combined (entity check + Noul) |
|---|---|---|
| False positives (faithful flagged untrustworthy) | 1 (r22, 0.46) | 1 (r22, 0.46, unchanged) |
| False negatives (corrupted scored trustworthy) | 1 (r24_corrupt, wrong_station) | 0 |

By error type, corrupted reports caught (combined system):

| Error type | caught / total |
|---|---|
| wrong_station | 2 / 2 |
| wrong_parameter | 2 / 2 |
| wrong_value | 1 / 1 |
| fabricated_cause | 2 / 2 |
| fabricated_comparison | 2 / 2 |

All 9 corrupted reports are now caught. The one remaining false positive
(r22) is unrelated to station identity, a genuinely faithful Sacramento
temperature report Noul itself scored under 0.5, and the entity check has
no way to help with that, it isn't a station-identity problem. Closing it
would need either a Noul threshold below 0.46 (trading away some ability
to catch weak corruptions) or a separate look at why Noul scored a
faithful report that low, not something this phase changes.

Figure: `reports/figures/combined_distribution.png`, same layout as the
phase 3 figure but plotting the effective trust score (Noul's P(faithful)
forced to 0 whenever the entity check fails, marked with an X). Both
wrong_station points sit at 0, fully separated from the faithful cluster,
where one had been sitting at 0.90 under Noul alone. The original
Noul-only figure (`faithfulness_distribution.png`) is left in place as
the before picture.

### The general principle

Semantic and deterministic checks catch different failure modes. Noul
reliably catches fabricated content, a cause, a comparison, a number that
drifted, because those require understanding whether a claim is actually
supported by the context. It is measurably weaker at catching a swapped
proper noun when everything else stays numerically consistent, because
that is a narrow factual lookup, not a judgment call, and a model trained
to weigh overall coherence can let a locally plausible substitution
through. A deterministic check is the reverse: excellent at an exact
factual lookup, useless at judging whether a fabricated cause is
plausible or whether a number is even in the right range. Neither check
subsumes the other. A trustworthy AI-generated report pipeline needs
both, not a better version of just one.

## Setup

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`TYPESAFE_API_KEY` must be set in the environment before running the
sanity check or the faithfulness evaluation. `ANTHROPIC_API_KEY` must be
set before running report generation. Neither is ever committed.
