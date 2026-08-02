#!/usr/bin/env python3
"""
SPIKE 5 — Where do the jobs Gedeon can actually do live?

Spike 4 censused the LMIA-approved queue (fskl=101020) and found 112 postings
containing ZERO technology roles: 28/40 agriculture, plus physicians,
caregivers, butchers and a hunting guide.

That breaks the assumption underneath docs/01 and docs/03 — that the LMIA queue
is where a front-end developer applies. It is not. So before another line of
architecture is written, measure the real market:

  A  How many tech jobs are open to international candidates (fglo=1)?
  B  How many tech jobs are in the LMIA-approved facet? (expected: ~0)
  C  How big is the general-work market Gedeon is honestly qualified for?

The answer decides whether this system targets software roles, agricultural and
general work, or both — and that is a strategy question, not an engineering one.

    python spikes/05_market_probe.py
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("missing deps.  pip install requests beautifulsoup4 lxml")

OUT = Path(__file__).parent / "out"
SEARCH = "https://www.jobbank.gc.ca/jobsearch/jobsearch"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 "
      "(Northbound job-application assistant; gedeon@gedeonchrist.com)")

COUNT_RE = re.compile(r"([\d,]+)\s+(?:jobs?|results?|postings?)", re.I)
TITLE_RE = re.compile(r"/jobsearch/jobposting/\d+")

# Facets under test. None = no facet (whole board, for context).
FACETS = {
    "international (fglo=1)": {"fglo": "1"},
    "lmia_approved (fskl=101020)": {"fskl": "101020"},
    "no_facet (whole board)": {},
}

# What Gedeon can honestly apply for, per profile/master-profile.yaml.
QUERIES = {
    # --- his actual profession ---
    "tech: web developer": "web developer",
    "tech: front end developer": "front end developer",
    "tech: software developer": "software developer",
    "tech: programmer": "programmer",
    "tech: javascript": "javascript",
    # --- documented general work ---
    "gen: general labourer": "general labourer",
    "gen: painter": "painter",
    "gen: security guard": "security guard",
    "gen: retail sales": "retail sales associate",
    "gen: warehouse": "warehouse",
    "gen: construction labourer": "construction labourer",
    "gen: farm worker": "farm worker",
    # --- baseline ---
    "": "",
}


def probe(session: requests.Session, facet: dict, q: str) -> dict:
    params = {"searchstring": q, "sort": "M", **facet}
    url = f"{SEARCH}?{urlencode(params)}"
    r = session.get(url, timeout=45)
    if r.status_code != 200:
        return {"http": r.status_code, "count": None, "url": url}
    soup = BeautifulSoup(r.text, "lxml")
    text = soup.get_text(" ", strip=True)
    m = COUNT_RE.search(text)
    n_links = len({a["href"] for a in soup.find_all("a", href=True)
                   if TITLE_RE.search(a["href"])})
    titles = [a.get_text(" ", strip=True)[:70]
              for a in soup.find_all("a", href=True) if TITLE_RE.search(a["href"])][:5]
    return {
        "http": 200,
        "count": int(m.group(1).replace(",", "")) if m else None,
        "on_page": n_links,
        "sample_titles": titles,
        "url": url,
    }


def main() -> int:
    OUT.mkdir(exist_ok=True)
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-CA,en;q=0.9"})

    report = {"spike": "05_market_probe",
              "run_at": datetime.now(timezone.utc).isoformat(),
              "matrix": {}}

    for fname, facet in FACETS.items():
        report["matrix"][fname] = {}
        print(f"\n{'='*66}\n{fname}\n{'='*66}")
        for label, q in QUERIES.items():
            res = probe(s, facet, q)
            report["matrix"][fname][label or "(all jobs)"] = res
            c = res.get("count")
            print(f"  {(label or '(all jobs)'):<32} {c if c is not None else '?':>8}")
            time.sleep(random.uniform(1.5, 3.0))

    # --- the headline numbers -------------------------------------------
    intl = report["matrix"]["international (fglo=1)"]
    lmia = report["matrix"]["lmia_approved (fskl=101020)"]
    tech_intl = sum(v["count"] or 0 for k, v in intl.items() if k.startswith("tech:"))
    tech_lmia = sum(v["count"] or 0 for k, v in lmia.items() if k.startswith("tech:"))
    gen_intl = sum(v["count"] or 0 for k, v in intl.items() if k.startswith("gen:"))
    gen_lmia = sum(v["count"] or 0 for k, v in lmia.items() if k.startswith("gen:"))

    report["headline"] = {
        "tech_open_to_international": tech_intl,
        "tech_in_lmia_facet": tech_lmia,
        "general_open_to_international": gen_intl,
        "general_in_lmia_facet": gen_lmia,
        "reading": (
            "If tech_in_lmia_facet is ~0 while tech_open_to_international is "
            "meaningful, then the LMIA facet is the wrong queue for Gedeon's "
            "profession and the international facet is the real target — with the "
            "caveat that those employers have not necessarily obtained an LMIA. "
            "If BOTH tech numbers are near zero, the honest conclusion is that "
            "Job Bank is not where Canadian front-end roles are advertised, and "
            "the sourcing strategy needs to change, not the scraper."
        ),
    }

    (OUT / "market-probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n" + "=" * 66)
    for k, v in report["headline"].items():
        if k != "reading":
            print(f"  {k:<34} {v}")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
