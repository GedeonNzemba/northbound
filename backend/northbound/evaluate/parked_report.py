"""
Read a batch's failures back.

A run that parks everything is not a disappointment, it is a bug report — but
only if you can read it. Twenty `WHY-PARKED.txt` files scattered across a
directory are data nobody looks at; one frequency table of which rules fired,
how often, and on what, is the thing that says where to aim.

This is the loop that matters right now. The engine's checks are only worth
having if the documents can actually pass them, and the only way to find out
which rule is too strict — or which part of the prompt is too loose — is to
count.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

BLOCK = re.compile(r"^\s*BLOCK\s+(\S+)\s*(?:\[([^\]]*)\])?:\s*(.*)$")
WARN = re.compile(r"^\s*WARN\s+(\S+)\s*(?:\[([^\]]*)\])?:\s*(.*)$")
VERDICT = re.compile(r"^\s*(OVERSTATED|UNSUPPORTED)\s+\[([^\]]*)\]\s*(.*)$")
CLAIM = re.compile(r"^\s*claim\s*:\s*(.*)$")
SOURCE = re.compile(r"^\s*source\s*:\s*(.*)$")
SPAN = re.compile(r"^\s*span\s*:\s*(.*)$")
HEAD = re.compile(r"^\s*PARKED\s+(.*?)\s+\[track\s+(\w+)")


@dataclass
class Finding:
    kind: str            # "audit" | "entailment"
    rule: str            # audit rule name, or the entailment verdict
    where: str = ""
    detail: str = ""
    claim: str = ""
    source: str = ""
    span: str = ""


@dataclass
class ParkedFile:
    path: Path
    posting: str = ""
    track: str = ""
    findings: list[Finding] = field(default_factory=list)


def parse_report(text: str, path: Path) -> ParkedFile:
    out = ParkedFile(path=path)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if m := HEAD.match(line):
            out.posting, out.track = m.group(1), m.group(2)
        elif m := BLOCK.match(line):
            out.findings.append(Finding("audit", m.group(1), m.group(2) or "",
                                        m.group(3)))
        elif m := VERDICT.match(line):
            f = Finding("entailment", m.group(1).lower(), m.group(2) or "",
                        m.group(3))
            # The claim/source/span lines follow immediately.
            for follow in lines[i + 1:i + 4]:
                if c := CLAIM.match(follow):
                    f.claim = c.group(1)
                elif s := SOURCE.match(follow):
                    f.source = s.group(1)
                elif sp := SPAN.match(follow):
                    f.span = sp.group(1)
            out.findings.append(f)
    return out


# Where the reports plausibly are, depending on where the batch was run from and
# what --out was given. Guessing here is cheap; making someone find out by
# running the wrong path twice is not.
SEARCH_ORDER = (
    "out/parked", "../out/parked", "backend/out/parked",
    "out", "../out",
)


def find_parked_dir(hint: Path | str | None = None) -> Path | None:
    """The first directory that actually contains WHY-PARKED files."""
    candidates = [Path(hint)] if hint else []
    candidates += [Path(p) for p in SEARCH_ORDER]
    for c in candidates:
        if c.is_dir() and any(c.glob("*WHY-PARKED.txt")):
            return c
    return None


def read_parked(directory: Path | str) -> list[ParkedFile]:
    directory = Path(directory)
    files = sorted(directory.rglob("*WHY-PARKED.txt"))
    return [parse_report(f.read_text(encoding="utf-8", errors="replace"), f)
            for f in files]


def digest(parked: list[ParkedFile], *, examples: int = 2) -> str:
    """
    A frequency table plus a couple of real examples per rule.

    Short enough to read in one screen and to paste somewhere, which is the
    point — the raw files are too long to look at and too many to compare.
    """
    if not parked:
        return "no WHY-PARKED.txt files found"

    counts: Counter[tuple[str, str]] = Counter()
    by_rule: dict[tuple[str, str], list[Finding]] = {}
    for pf in parked:
        for f in pf.findings:
            key = (f.kind, f.rule)
            counts[key] += 1
            by_rule.setdefault(key, []).append(f)

    total_findings = sum(counts.values())
    lines = [
        f"{len(parked)} parked application(s), {total_findings} finding(s)",
        "",
        "WHICH RULE FIRED, AND HOW OFTEN",
        "-" * 72,
    ]
    for (kind, rule), n in counts.most_common():
        share = 100 * n / total_findings
        lines.append(f"  {n:>3}  ({share:>4.0f}%)  {kind:<11} {rule}")

    lines += ["", "EXAMPLES", "-" * 72]
    for (kind, rule), n in counts.most_common():
        lines.append(f"\n[{kind}] {rule}  ×{n}")
        for f in by_rule[(kind, rule)][:examples]:
            if kind == "audit":
                lines.append(f"    {f.where or '-'}: {f.detail[:150]}")
            else:
                lines.append(f"    cites {f.where}")
                lines.append(f"      claim : {f.claim[:150]}")
                lines.append(f"      source: {f.source[:150]}")
                if f.span:
                    lines.append(f"      span  : {f.span[:150]}")
    return "\n".join(lines)


__all__ = ["read_parked", "find_parked_dir", "parse_report", "digest",
           "ParkedFile", "Finding"]
