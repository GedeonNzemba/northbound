#!/usr/bin/env python3
"""
Run all three spikes in dependency order and write a combined summary.

  3 (search listings)  →  picks a real posting URL  →  1 (posting detail)
  2 (open data)        →  independent

Used by .github/workflows/spikes.yml so nobody has to run anything by hand,
and equally usable locally:

    python spikes/run_all.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "out"
PY = sys.executable


def run(script: str, *args: str) -> tuple[int, str]:
    cmd = [PY, str(HERE / script), *args]
    print(f"\n$ {' '.join(cmd)}", flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    out = (p.stdout or "") + (p.stderr or "")
    print(out, flush=True)
    return p.returncode, out


def first_posting_url() -> str | None:
    """Pull a live posting URL out of spike 3's report."""
    report = OUT / "search-listing-report.json"
    if not report.exists():
        return None
    try:
        data = json.loads(report.read_text())
    except json.JSONDecodeError:
        return None
    # Prefer the LMIA queue — it is the primary source.
    ordered = sorted(
        data.get("results", []),
        key=lambda r: 0 if "lmia" in (r.get("name") or "") else 1,
    )
    for r in ordered:
        posts = (r.get("Q3_postings") or {}).get("first_10") or []
        if posts:
            return posts[0]["url"]
    return None


def main() -> int:
    OUT.mkdir(exist_ok=True)
    summary: dict = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "runner": "github-actions" if __import__("os").getenv("CI") else "local",
        "steps": {},
    }

    # --- 3: search listings (no browser) --------------------------------
    rc, log = run("03_search_listing.py")
    summary["steps"]["03_search_listing"] = {"exit": rc, "ok": rc == 0}

    # --- 1: posting detail, chained off spike 3 -------------------------
    url = first_posting_url()
    summary["chained_posting_url"] = url
    if url:
        rc1, _ = run("01_fetch_posting.py", "--url", url)
        summary["steps"]["01_fetch_posting"] = {"exit": rc1, "ok": rc1 == 0, "url": url}
    else:
        summary["steps"]["01_fetch_posting"] = {
            "skipped": True,
            "reason": "spike 3 produced no posting URL — either it was blocked, or "
                      "the results are not server-rendered (see its report)",
        }
        print("\n!! no posting URL from spike 3 — skipping spike 1")

    # --- 2: open data (independent) -------------------------------------
    rc2, _ = run("02_inspect_opendata.py")
    summary["steps"]["02_inspect_opendata"] = {"exit": rc2, "ok": rc2 == 0}

    (OUT / "run-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    for name, st in summary["steps"].items():
        mark = "skip" if st.get("skipped") else ("ok" if st.get("ok") else "FAIL")
        print(f"  {mark:>4}  {name}")
    print("=" * 60)

    # Deliberately exit 0 even on spike failure: a blocked or changed page is a
    # RESULT worth committing and reading, not a build error to hide.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
