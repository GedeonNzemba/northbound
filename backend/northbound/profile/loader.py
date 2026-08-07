"""
Load `profile/master-profile.yaml` and build the evidence index.

This module is the boundary between the YAML file Gedeon and I maintain by hand
and everything downstream. Its job is to make the generation contract in
docs/04 *enforceable* rather than aspirational:

  • Every fact carries a stable `id`.
  • `verify: true` anywhere — on an entry OR on a single bullet — excludes that
    item from generation. Exclusion is the default; nothing unconfirmed reaches
    an employer.
  • Standing instructions from docs/06 that must survive any future edit are
    asserted at load time, not left to a code reviewer noticing.

If the profile violates one of those invariants the loader raises. A malformed
profile must fail loudly at startup, never silently produce a weaker CV.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterator, Literal

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROFILE = REPO_ROOT / "profile" / "master-profile.yaml"

Track = Literal["direct", "transferable"]


class ProfileError(RuntimeError):
    """The profile is malformed or violates a standing instruction."""


# --------------------------------------------------------------------------- #
# Evidence — the unit the generator is allowed to cite
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Evidence:
    """One citable fact. `id` is what a generated bullet must reference."""

    id: str
    text: str
    kind: str                       # experience_professional | experience_general | education | ...
    parent_id: str | None = None    # the role/entry this bullet belongs to
    tags: tuple[str, ...] = ()
    excluded: bool = False
    exclusion_reason: str | None = None

    @property
    def usable(self) -> bool:
        return not self.excluded


@dataclass
class Role:
    """A work entry, professional or general."""

    id: str
    employer: str
    title_as_held: str
    kind: Literal["professional", "general"]
    raw: dict[str, Any]
    bullets: list[Evidence] = field(default_factory=list)
    excluded: bool = False
    exclusion_reason: str | None = None

    # ---- fields the renderer needs, normalised ---------------------------- #
    @property
    def employment_type(self) -> str | None:
        """None is meaningful: docs/06 forbids guessing one (e.g. Cumpsty)."""
        return self.raw.get("employment_type")

    @property
    def canadian_title(self) -> str:
        return self.raw.get("canadian_title_equivalent") or self.title_as_held

    @property
    def noc(self) -> str | None:
        return self.raw.get("noc_2021")

    @property
    def location(self) -> str:
        loc = self.raw.get("location") or {}
        parts = [loc.get("city"), loc.get("region"), loc.get("country")]
        seen: list[str] = []
        for p in parts:
            if p and p not in seen:
                seen.append(p)
        base = ", ".join(seen)
        if loc.get("arrangement"):
            base = f"{base} ({loc['arrangement']})" if base else loc["arrangement"]
        return base

    @property
    def context_clause(self) -> str | None:
        """docs/08 §3.2 — a Canadian reader doesn't know these employers."""
        return self.raw.get("industry")

    @property
    def display_dates(self) -> str:
        """
        docs/08 §1.4 — `Mon YYYY – Mon YYYY`, months spelled out.

        `cv_render_dates` wins where present: it is how the painter and packer
        date conflicts were resolved (docs/06), and day-level precision is
        explicitly forbidden for those entries.
        """
        if override := self.raw.get("cv_render_dates"):
            return str(override)
        start = _fmt_month(self.raw.get("start"))
        end = _fmt_month(self.raw.get("end")) if self.raw.get("end") else "Present"
        return f"{start} – {end}" if start else (end or "")

    @property
    def sort_key(self) -> str:
        return str(self.raw.get("start") or "0000")


MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]


def _fmt_month(value: Any) -> str:
    """
    Render a date at the granularity it is actually known to.

    Deliberately never emits a day. docs/08 §1.4 and the painter resolution in
    docs/06 both require month-level output, and a spurious day is a false
    statement of precision.
    """
    if value is None:
        return ""
    if isinstance(value, date):
        return f"{MONTHS[value.month][:3]} {value.year}"
    s = str(value).strip()
    if m := re.fullmatch(r"(\d{4})-(\d{2})(?:-\d{2})?", s):
        return f"{MONTHS[int(m.group(2))][:3]} {m.group(1)}"
    if re.fullmatch(r"\d{4}", s):
        return s
    return s


# --------------------------------------------------------------------------- #
# The profile
# --------------------------------------------------------------------------- #

@dataclass
class Profile:
    raw: dict[str, Any]
    roles: list[Role]
    evidence: dict[str, Evidence]
    path: Path

    # ---- identity / contact ---------------------------------------------- #
    @property
    def legal_name(self) -> str:
        return self.raw["identity"]["legal_name"]

    @property
    def contact_block(self) -> dict[str, str]:
        """
        docs/08 §1.3 — city + country only, no street address, phone in +CC.

        The absence of a street address here is load-bearing, not an oversight:
        `identity` deliberately holds no address, ID or passport number.
        """
        c = self.raw["contact"]
        res = self.raw["identity"]["residence"]
        return {
            "name": self.legal_name,
            "location": f"{res['city']}, {res['country']}",
            "phone": _fmt_phone(c["phone_e164"]),
            "email": c["email"],
            "linkedin": c.get("linkedin", ""),
            "portfolio": c.get("portfolio", ""),
        }

    # ---- lookups ---------------------------------------------------------- #
    def role(self, role_id: str) -> Role:
        for r in self.roles:
            if r.id == role_id:
                return r
        raise KeyError(role_id)

    def usable_evidence(self) -> dict[str, Evidence]:
        return {k: v for k, v in self.evidence.items() if v.usable}

    def roles_for(self, kind: Literal["professional", "general"]) -> list[Role]:
        return sorted(
            (r for r in self.roles if r.kind == kind and not r.excluded),
            key=lambda r: r.sort_key,
            reverse=True,
        )

    def evidence_by_tag(self, *tags: str) -> list[Evidence]:
        want = set(tags)
        return [e for e in self.evidence.values() if e.usable and want & set(e.tags)]

    def education_entry(self, entry_id: str) -> dict[str, Any] | None:
        """The raw education record, so the audit can check what was rendered."""
        for e in self.raw.get("education", []) or []:
            if e.get("id") == entry_id:
                return e
        return None

    def education_years(self, entry_id: str) -> set[str]:
        """
        Every year this credential could legitimately carry.

        Entries record dates three ways — `completed` as a bare year, `completed`
        as a full date, or a `start`/`end` pair — and a CV may render any of
        them. Collecting all of them keeps the check about *invented* years
        rather than about formatting.
        """
        entry = self.education_entry(entry_id) or {}
        years: set[str] = set()
        for key in ("completed", "start", "end"):
            value = entry.get(key)
            if isinstance(value, date):
                years.add(str(value.year))
            elif value is not None and re.fullmatch(r"\d{4}", str(value).strip()):
                years.add(str(value).strip())
        return years

    # ---- standing instructions (docs/06) ---------------------------------- #
    @property
    def render_referees(self) -> bool:
        return bool((self.raw.get("referees") or {}).get("render_on_cv", False))

    @property
    def coursework_ids(self) -> set[str]:
        """
        IT Academy items. D1: these are curriculum from remote study and must
        never render as held credentials.
        """
        block = (self.raw.get("certifications") or {}).get("coursework_completed") or {}
        return {i["id"] for i in block.get("items", []) if "id" in i}

    @property
    def verified_credential_ids(self) -> set[str]:
        block = (self.raw.get("certifications") or {}).get("verified_credentials") or []
        return {i["id"] for i in block if "id" in i}


def _fmt_phone(e164: str) -> str:
    """+27832532615 -> +27 83 253 2615 (docs/08 §1.3: full international form)."""
    s = e164.strip()
    if s.startswith("+27") and len(s) == 12:
        return f"+27 {s[3:5]} {s[5:8]} {s[8:]}"
    return s


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #

def _walk_entries(raw: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for key in ("experience_professional", "experience_general"):
        for entry in raw.get(key, []) or []:
            yield key, entry


def load_profile(path: Path | str | None = None) -> Profile:
    path = Path(path or DEFAULT_PROFILE)
    if not path.exists():
        raise ProfileError(f"profile not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ProfileError("profile did not parse to a mapping")

    roles: list[Role] = []
    evidence: dict[str, Evidence] = {}

    for key, entry in _walk_entries(raw):
        if "id" not in entry:
            raise ProfileError(f"{key} entry missing `id`: {entry.get('employer')!r}")

        kind = "professional" if key.endswith("professional") else "general"

        # An entry is excluded if flagged directly, or if a nested conflict
        # block still carries verify: true (that is how date disputes are held).
        excluded = bool(entry.get("verify"))
        reason = "entry flagged verify: true" if excluded else None
        conflict = entry.get("conflict") or {}
        if conflict.get("verify"):
            excluded, reason = True, "unresolved conflict"

        role = Role(
            id=entry["id"],
            employer=entry.get("employer", ""),
            title_as_held=entry.get("title_as_held", ""),
            kind=kind,
            raw=entry,
            excluded=excluded,
            exclusion_reason=reason,
        )

        for b in entry.get("highlights", []) or []:
            if "id" not in b or "text" not in b:
                raise ProfileError(f"malformed highlight in {role.id}: {b!r}")
            # A bullet is excluded if IT is flagged, or if its whole role is.
            b_excluded = bool(b.get("verify")) or excluded
            b_reason = (
                "bullet flagged verify: true" if b.get("verify") else reason
            )
            ev = Evidence(
                id=b["id"],
                text=" ".join(str(b["text"]).split()),
                kind=key,
                parent_id=role.id,
                tags=tuple(b.get("tags", []) or []),
                excluded=b_excluded,
                exclusion_reason=b_reason,
            )
            if ev.id in evidence:
                raise ProfileError(f"duplicate evidence id: {ev.id}")
            evidence[ev.id] = ev
            role.bullets.append(ev)

        roles.append(role)

    _index_flat(raw, "education", evidence, "credential")
    _index_flat(raw, "awards", evidence, "name")
    _index_portfolio(raw, evidence)

    profile = Profile(raw=raw, roles=roles, evidence=evidence, path=path)
    _assert_standing_instructions(profile)
    return profile


def _index_flat(raw: dict, key: str, out: dict[str, Evidence], text_field: str) -> None:
    for entry in raw.get(key, []) or []:
        if "id" not in entry:
            continue
        excluded = bool(entry.get("verify"))
        out[entry["id"]] = Evidence(
            id=entry["id"],
            text=str(entry.get(text_field, "")),
            kind=key,
            excluded=excluded,
            exclusion_reason="flagged verify: true" if excluded else None,
        )


def _index_portfolio(raw: dict, out: dict[str, Evidence]) -> None:
    for entry in raw.get("portfolio_links", []) or []:
        if "id" not in entry:
            continue
        out[entry["id"]] = Evidence(
            id=entry["id"],
            text=f"{entry.get('label','')} — {entry.get('url','')}",
            kind="portfolio",
            tags=tuple(entry.get("tags", []) or []),
        )


def _assert_standing_instructions(p: Profile) -> None:
    """
    Fail loudly if a docs/06 standing instruction has been reverted.

    These are the ones a future edit could plausibly undo by accident, where the
    consequence lands on a real employer rather than in a test.
    """
    problems: list[str] = []

    # No referees, ever (docs/06 — removed on Gedeon's instruction).
    refs = p.raw.get("referees") or {}
    if refs.get("render_on_cv"):
        problems.append("referees.render_on_cv is true — referees must never render")
    if refs.get("entries"):
        problems.append("referees.entries is non-empty — referee details must not be stored")

    # IT Academy coursework must never be classified as a certification (D1).
    block = (p.raw.get("certifications") or {}).get("coursework_completed") or {}
    if block.get("render_as") != "coursework_under_education":
        problems.append(
            "certifications.coursework_completed.render_as must be "
            "'coursework_under_education' (D1)"
        )

    # No PII that must never reach a CV or a git repo (docs/02 Rule 6).
    ident = p.raw.get("identity") or {}
    for banned in ("id_number", "passport_number", "street_address", "sin"):
        if banned in ident:
            problems.append(f"identity.{banned} must not be stored in the profile")

    if problems:
        raise ProfileError(
            "profile violates standing instructions:\n  - " + "\n  - ".join(problems)
        )


__all__ = ["Profile", "Role", "Evidence", "load_profile", "ProfileError", "Track"]
