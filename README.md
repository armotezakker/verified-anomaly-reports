# verified-anomaly-reports

Detects anomalies in real water sensor data, drafts plain-language incident
reports with an LLM, and checks those reports against the underlying data
with a faithfulness-checking model (Typesafe / Noul) before they would reach
an operator. Built as a portfolio project aimed at Xylem's stated interest
in applying modern AI tools to data exploration and decision support on
operational water data.

This is phase 1: data acquisition and inspection only. No anomaly detection
or LLM report generation yet.

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

## Date range

2024-09-01 to 2025-08-31 (one year). Chosen to open right at the start of
the Helene flood and close just after the Guadalupe flood, while covering a
full seasonal temperature cycle for the temperature stations.

## Pipeline

```
src/data/fetch_nwis.py    pulls raw JSON per station into data/raw/
src/data/parse_nwis.py    flattens raw JSON into data/processed/readings.parquet
src/analysis/inspect_data.py   prints summary stats, writes reports/figures/*.png
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

## Setup

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`TYPESAFE_API_KEY` must be set in the environment before running the
sanity check or, later, the report verification pipeline. It is never
committed.
