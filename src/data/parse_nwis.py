"""Parse raw NWIS JSON payloads into one tidy table.

Reads every data/raw/*.json file written by fetch_nwis.py and writes a
single long-format table to data/processed/readings.parquet with columns:
site_id, site_name, param_code, param_name, datetime, value, qualifiers.
"""

import html
import json
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"


def parse_file(path: Path) -> list[dict]:
    payload = json.loads(path.read_text())
    rows = []
    for series in payload["value"]["timeSeries"]:
        site_id = series["sourceInfo"]["siteCode"][0]["value"]
        site_name = series["sourceInfo"]["siteName"]
        param_code = series["variable"]["variableCode"][0]["value"]
        param_name = html.unescape(series["variable"]["variableName"])
        for value_block in series["values"]:
            methods = value_block.get("method") or [{}]
            method_id = methods[0].get("methodID")
            method_desc = methods[0].get("methodDescription", "")
            for point in value_block["value"]:
                rows.append(
                    {
                        "site_id": site_id,
                        "site_name": site_name,
                        "param_code": param_code,
                        "param_name": param_name,
                        "method_id": method_id,
                        "method_desc": method_desc,
                        "datetime": point["dateTime"],
                        "value": point["value"],
                        "qualifiers": ",".join(point.get("qualifiers", [])),
                    }
                )
    return rows


def main() -> None:
    all_rows = []
    for path in sorted(RAW_DIR.glob("*.json")):
        all_rows.extend(parse_file(path))

    df = pd.DataFrame(all_rows)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df.sort_values(["site_id", "param_code", "method_id", "datetime"]).reset_index(drop=True)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "readings.parquet"
    df.to_parquet(out_path, index=False)
    print(f"wrote {out_path} with {len(df)} rows")


if __name__ == "__main__":
    main()
