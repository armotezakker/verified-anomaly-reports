# verified-anomaly-reports

Detects anomalies in real water sensor data, drafts plain-language incident
reports with an LLM, and checks those reports against the underlying data
with a faithfulness-checking model (Typesafe / Noul) before they would reach
an operator. Built as a portfolio project aimed at Xylem's stated interest
in applying modern AI tools to data exploration and decision support on
operational water data.

Phase 1 pulled and inspected the raw data. Phase 2 adds a deliberately
simple anomaly detector. LLM report generation and faithfulness
verification are not built yet.

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
| 11447650 Sacramento | streamflow | 34,812 | 778 | 2.2% |
| 11447650 Sacramento | temperature | 34,840 | 206 | 0.6% |
| 04234000 Fall Creek | streamflow | 29,804 | 2,300 | 7.7% |

The flagged fractions are not tuned down. A 14-day trailing IQR fence
flags every meaningful rise above recent baseline, not only the five
marquee events below, so most stations show flagged points scattered
across many smaller storms and thaws through the year in addition to the
big ones. Confirmed against the overlay plots in
`reports/figures/<site_id>_<param_code>_anomalies.png`.

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
- The IQR fence has no physical floor. For a low-variance baseline period
  it can compute a lower bound below zero for a quantity that cannot
  physically be negative (visible in the Fall Creek plot). This never
  produced a bad flag in this run because no readings were actually
  negative there, but it is a real gap in the model, not by design.

Anomaly log: `data/processed/anomalies.csv` (not committed). Packaged
context for phase 3: `data/processed/anomaly_context.json` (not
committed), one record per flagged reading with exactly: site id, site
name, latitude, longitude, parameter code and name, timestamp, the
anomalous value, and the baseline (median, low, high) it was compared
against. Nothing else, so it can serve as the ground truth the
faithfulness checker verifies generated reports against.

## Setup

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`TYPESAFE_API_KEY` must be set in the environment before running the
sanity check or, later, the report verification pipeline. It is never
committed.
