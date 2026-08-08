"""
Tests for reading a batch's failures back.

The first paid run parked 8 of 8. That is not a disappointment, it is a bug
report — the checks are only worth having if documents can pass them, and the
only way to find out which rule is too strict is to count which ones fired.
This is the thing that turns twenty scattered files into that count.
"""

from __future__ import annotations

import pytest

from northbound.evaluate.parked_report import digest, parse_report, read_parked

AUDIT = """PARKED  Mucci Farms — greenhouse labourer  [track transferable, 2 attempt(s)]
  reason: 2 blocking audit finding(s) after 2 attempt(s) — held for human review
  BLOCKED
    BLOCK skills.unheld_credential [cv]: claims 'first aid', nowhere in the profile
    BLOCK specificity.thin [letter.bridge]: letter.bridge has 1 concrete particular(s)
  usage: 12 call(s)  prompt 90,000 (40,000 cached = 44%)  output 5,000  ≈ $0.30
"""

ENTAIL = """PARKED  Ridge Farms — general labourer - farm  [track transferable, 2 attempt(s)]
  reason: 1 claim(s) not supported by cited evidence after 2 attempt(s)
  PASS — no findings
  entailment: 1 unsupported claim(s)
  OVERSTATED [gen.cumpsty.h1] cv.experience[gen.cumpsty]
        claim : Led a team of electricians on estate construction sites.
        source: Assisted qualified electricians on residential estate sites.
        span  : 'Led a team' — the source says assisted, not led
"""


def test_audit_findings_are_read_with_their_rule_and_place(tmp_path):
    f = parse_report(AUDIT, tmp_path / "x.txt")
    assert f.track == "transferable"
    assert "Mucci Farms" in f.posting
    rules = [(x.kind, x.rule, x.where) for x in f.findings]
    assert ("audit", "skills.unheld_credential", "cv") in rules
    assert ("audit", "specificity.thin", "letter.bridge") in rules


def test_an_entailment_failure_keeps_claim_source_and_span(tmp_path):
    """
    The span is the whole point — it says which words went beyond the source,
    which is what makes a fix targeted instead of a blind rewrite.
    """
    f = parse_report(ENTAIL, tmp_path / "y.txt")
    (finding,) = f.findings
    assert finding.kind == "entailment" and finding.rule == "overstated"
    assert finding.where == "gen.cumpsty.h1"
    assert "Led a team" in finding.claim
    assert "Assisted qualified" in finding.source
    assert "Led a team" in finding.span


def test_the_usage_line_is_not_mistaken_for_a_finding(tmp_path):
    f = parse_report(AUDIT, tmp_path / "x.txt")
    assert len(f.findings) == 2, [x.rule for x in f.findings]


def test_the_digest_counts_rules_across_files(tmp_path):
    (tmp_path / "a-WHY-PARKED.txt").write_text(AUDIT, encoding="utf-8")
    (tmp_path / "b-WHY-PARKED.txt").write_text(ENTAIL, encoding="utf-8")
    (tmp_path / "c-WHY-PARKED.txt").write_text(AUDIT, encoding="utf-8")

    out = digest(read_parked(tmp_path))
    assert "3 parked application(s)" in out
    assert "skills.unheld_credential" in out
    assert "  2  " in out, "the repeated rule must show a count of 2"
    assert "overstated" in out


def test_the_most_common_rule_is_listed_first(tmp_path):
    """The point is knowing where to aim, so ordering carries the answer."""
    (tmp_path / "a-WHY-PARKED.txt").write_text(AUDIT, encoding="utf-8")
    (tmp_path / "b-WHY-PARKED.txt").write_text(AUDIT, encoding="utf-8")
    (tmp_path / "c-WHY-PARKED.txt").write_text(ENTAIL, encoding="utf-8")

    body = digest(read_parked(tmp_path))
    table = body[body.index("HOW OFTEN"):body.index("EXAMPLES")]
    counted = [l for l in table.splitlines() if l.startswith("  ") and "(" in l]
    assert counted, table
    assert "skills.unheld_credential" in counted[0], counted[0]
    assert counted[0].split()[0] == "2", counted[0]


def test_an_empty_directory_says_so(tmp_path):
    assert "no WHY-PARKED" in digest(read_parked(tmp_path))


def test_a_malformed_file_does_not_crash_the_digest(tmp_path):
    (tmp_path / "junk-WHY-PARKED.txt").write_text("not a report at all\n",
                                                  encoding="utf-8")
    (tmp_path / "ok-WHY-PARKED.txt").write_text(AUDIT, encoding="utf-8")
    out = digest(read_parked(tmp_path))
    assert "skills.unheld_credential" in out
