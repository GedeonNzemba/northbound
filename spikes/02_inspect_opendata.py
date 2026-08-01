#!/usr/bin/env python3
"""
SPIKE 2 — Can the open-data CSV actually support this system?

docs/03-architecture.md builds the discovery layer on the Open Government
dataset "Job Postings Advertised on Canada's National Job Bank Website". Three
claims are made about it that have NEVER been checked against the real file:

  C1  It is refreshed often enough to support "monitor for new jobs".
      → Gedeon's stated requirement is near-real-time. If the newest row is
        30+ days old, this source CANNOT meet it and the plan must change.
        This is the one that decides whether the architecture survives.

  C2  It carries a usable LMIA / foreign-candidate signal.
      → The Stage 1 filter in docs/03 assumes one exists. If it doesn't, the
        whole "only LMIA employers" premise has no basis in this source and has
        to come from the search page or the XML feed instead.

  C3  It carries NOC 2021, wage, location and employer — enough to rank on.

It does NOT carry the apply-to email; that is spike 1's job.

    pip install requests
    python spikes/02_inspect_opendata.py

Writes spikes/out/opendata-report.json + a sample of real rows.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed.  pip install requests")

OUT = Path(__file__).parent / "out"
DATASET_ID = "ea639e28-c0fc-48bf-b5dd-b8899bd43072"
CKAN = "https://open.canada.ca/data/api/3/action/package_show"

# Column names we hope exist. Deliberately generous — we do not know the real
# schema, which is the entire point of running this.
WANT = {
    "date":     ["date", "posted", "created", "effective", "start"],
    "lmia":     ["lmia", "tfw", "foreign", "temporary_foreign", "immigration"],
    "noc":      ["noc"],
    "employer": ["employer", "business", "company", "operating_name"],
    "wage":     ["wage", "salary", "pay"],
    "location": ["province", "city", "location", "region", "cma"],
    "contact":  ["email", "contact", "apply", "how_to"],
}


def classify(headers: list[str]) -> dict[str, list[str]]:
    low = {h: h.lower() for h in headers}
    return {
        concept: sorted(h for h, l in low.items() if any(k in l for k in keys))
        for concept, keys in WANT.items()
    }


def main() -> int:
    OUT.mkdir(exist_ok=True)
    report: dict = {
        "spike": "02_inspect_opendata",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": DATASET_ID,
    }

    print(f"→ package_show {DATASET_ID}")
    r = requests.get(CKAN, params={"id": DATASET_ID}, timeout=60)
    r.raise_for_status()
    pkg = r.json()["result"]

    report["title"] = pkg.get("title")
    report["licence"] = pkg.get("license_title")
    report["metadata_modified"] = pkg.get("metadata_modified")

    resources = [
        {
            "name": x.get("name"),
            "format": x.get("format"),
            "url": x.get("url"),
            "last_modified": x.get("last_modified") or x.get("created"),
            "size": x.get("size"),
        }
        for x in pkg.get("resources", [])
    ]
    resources.sort(key=lambda x: (x["last_modified"] or ""), reverse=True)
    report["resource_count"] = len(resources)
    report["resources_newest_first"] = resources[:12]

    print(f"  {len(resources)} resources; newest: {resources[0]['name'] if resources else '—'}")

    csvs = [x for x in resources if (x["format"] or "").upper() == "CSV" and x["url"]]
    if not csvs:
        report["fatal"] = "no CSV resource found"
        (OUT / "opendata-report.json").write_text(json.dumps(report, indent=2))
        return 2

    newest = csvs[0]
    print(f"→ GET {newest['url']}")
    # Stream a slice — these files can be large and we only need the shape.
    resp = requests.get(newest["url"], timeout=180, stream=True)
    resp.raise_for_status()
    chunk = b""
    for part in resp.iter_content(1 << 20):
        chunk += part
        if len(chunk) > 8 << 20:  # 8 MB is plenty for schema + sample
            break
    resp.close()

    text = chunk.decode("utf-8-sig", errors="replace")
    text = text[: text.rfind("\n")]  # drop the truncated final row
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        report["fatal"] = "CSV parsed to zero rows"
        (OUT / "opendata-report.json").write_text(json.dumps(report, indent=2))
        return 3

    headers = list(rows[0].keys())
    report["sampled_resource"] = newest
    report["row_sample_size"] = len(rows)
    report["headers"] = headers
    report["header_classification"] = classify(headers)

    # ---- C1: freshness -----------------------------------------------------
    date_cols = report["header_classification"]["date"]
    freshness = {}
    for col in date_cols:
        vals = sorted(v for v in (r.get(col) or "" for r in rows) if v.strip())
        if vals:
            freshness[col] = {"min": vals[0], "max": vals[-1]}
    report["C1_freshness"] = {
        "date_columns": date_cols,
        "observed_ranges": freshness,
        "verdict_note": "Compare the max date to today. A gap of weeks means this "
                        "source CANNOT satisfy the near-real-time monitoring "
                        "requirement and docs/03 must be revised.",
    }

    # ---- C2: LMIA / foreign-candidate signal -------------------------------
    lmia_cols = report["header_classification"]["lmia"]
    report["C2_lmia_signal"] = {
        "candidate_columns": lmia_cols,
        "value_distribution": {
            c: Counter((r.get(c) or "").strip() for r in rows).most_common(8)
            for c in lmia_cols
        },
        "verdict_note": "Empty list here means the Stage 1 'LMIA employers only' "
                        "filter has no basis in this source.",
    }

    # ---- C3: ranking fields ------------------------------------------------
    report["C3_ranking_fields"] = {
        c: report["header_classification"][c] for c in ("noc", "employer", "wage", "location")
    }
    report["C3_contact_fields_present"] = report["header_classification"]["contact"]

    # Fill rates tell you which columns are real vs mostly-null.
    report["fill_rate"] = {
        h: round(sum(1 for r in rows if (r.get(h) or "").strip()) / len(rows), 3)
        for h in headers
    }

    (OUT / "opendata-sample.json").write_text(
        json.dumps(rows[:25], indent=2), encoding="utf-8"
    )
    (OUT / "opendata-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n--- verdicts to read ---")
    print(f"C1 freshness : {freshness or 'NO DATE COLUMN FOUND'}")
    print(f"C2 lmia      : {lmia_cols or 'NO LMIA COLUMN FOUND'}")
    print(f"C3 noc/wage  : {report['C3_ranking_fields']}")
    print(f"\n✔ wrote {OUT/'opendata-report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
