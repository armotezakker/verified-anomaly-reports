"""Pull instantaneous values from the USGS NWIS waterservices API.

Fetches one JSON payload per (station, parameter) pair and writes it
unmodified to data/raw/. No API key is required; this is a public service.
"""

import json
import time
from pathlib import Path

import requests

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

BASE_URL = "https://waterservices.usgs.gov/nwis/iv/"

START_DT = "2024-09-01"
END_DT = "2025-08-31"

# Station id -> (name, parameter codes to pull)
# 00060 = discharge, cubic feet per second
# 00010 = water temperature, degrees Celsius
STATIONS = {
    "03451500": ("French Broad River at Asheville, NC", ["00060", "00010"]),
    "08166200": ("Guadalupe River near Hunt, TX", ["00060"]),
    "08167000": ("Guadalupe River at Comfort, TX", ["00060"]),
    "01646500": ("Potomac River near Washington, DC (Little Falls)", ["00060", "00010"]),
    "11447650": ("Sacramento River at Freeport, CA", ["00060", "00010"]),
    "04234000": ("Fall Creek near Ithaca, NY", ["00060"]),
}


def fetch_station(site_id: str, param_codes: list[str]) -> dict:
    params = {
        "sites": site_id,
        "parameterCd": ",".join(param_codes),
        "startDT": START_DT,
        "endDT": END_DT,
        "format": "json",
    }
    resp = requests.get(BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for site_id, (name, codes) in STATIONS.items():
        out_path = RAW_DIR / f"{site_id}.json"
        print(f"fetching {site_id} ({name}) params={codes} ...")
        payload = fetch_station(site_id, codes)
        out_path.write_text(json.dumps(payload))
        n_series = len(payload["value"]["timeSeries"])
        print(f"  wrote {out_path.name}, {n_series} series")
        time.sleep(1)


if __name__ == "__main__":
    main()
