"""
Should we apply at all? — `config/sources.yaml` → `exclusions_only`.

D6 is emphatic that occupation is **not** a filter on the LMIA queue: sponsorship
is the rare thing, role fit is the variable, so farm, greenhouse, labouring,
caregiving and butchery are all in scope and the answer is "all of them". This
module is not a re-litigation of that. It implements the short list of
exclusions the same policy carves out — postings that cannot convert no matter
how good the document is.

The distinction that matters: a role Gedeon has never done is in scope, because
that is what Track B and an honest bridge sentence are for. A role he is legally
barred from holding is not, because no document fixes a missing licence. Two
family physicians and a physiotherapist came back in the first harvest, which is
what made this worth building rather than leaving as a line in a YAML comment.

`PROFILE-GAPS.md` item 8 states the requirement for the driver's-licence case
outright: "the system must filter those postings out rather than apply and waste
the slot."

Not implemented here, because neither is decidable from the posting alone:
closing date (the scraper does not yet capture one) and the
already-applied-within-cooldown rule (needs application history).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..profile import Profile


@dataclass(frozen=True)
class Exclusion:
    rule: str
    reason: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.reason}"


# NOC 2021 major groups whose occupations are provincially regulated — practice
# requires registration with a college or association, and no amount of relevant
# experience substitutes.
#
# The boundary in the trades is deliberate and worth stating, because it is one
# digit wide. **72xx** is certified trades (electricians, plumbers, welders,
# machinists) — a ticket he does not hold. **73xx** is general trades, and 73112
# is painter, which is one of his own roles. Excluding 73 would throw away work
# he has actually done; excluding 72 throws away work he cannot legally do.
REGULATED_NOC_PREFIXES = (
    "311",   # physicians, dentists, veterinarians, optometrists
    "312",   # pharmacists, dietitians, therapists, psychologists
    "313",   # registered nurses and registered psychiatric nurses
    "314",   # therapy and assessment professionals
    "321",   # medical technologists and technicians, paramedics
    "411",   # lawyers and Quebec notaries
    "412",   # post-secondary and school teachers
    "213",   # professional engineers (P.Eng)
    "72",    # certified trades — see the note above about 72 vs 73
)

REGULATED_TITLES = re.compile(
    r"\b(physician|surgeon|dentist|veterinarian|pharmacist|physiotherapist|"
    r"occupational therapist|psychologist|optometrist|chiropractor|midwife|"
    r"registered nurse|licensed practical nurse|nurse practitioner|paramedic|"
    r"lawyer|notary|teacher|professor|"
    r"professional engineer|p\.eng|"
    r"journeyperson|red seal|certified electrician|licensed electrician|"
    r"licensed plumber|certified welder)\b", re.I)

# Each alternative ends on a complete word. An earlier version wrapped the whole
# alternation in \b(...)\b with a branch ending in "lic", which can never match —
# the \b falls between "lic" and the "e" of "licence". Both spellings, because
# Canadian postings use either.
DRIVING_REQUIRED = re.compile(
    r"driver'?s?\s+licen[cs]e"
    r"|driving\s+licen[cs]e"
    r"|\bclass\s+[1-5]\s+licen[cs]e"
    r"|valid\s+licen[cs]e\s+to\s+drive"
    r"|must\s+be\s+able\s+to\s+drive"
    r"|own\s+vehicle\s+required"
    r"|own\s+transportation\s+required", re.I)

# Only the exclusive forms. "Are you legally able to work in Canada?" is a
# screening QUESTION that appears on a large share of these postings and is not
# a bar — answering it is exactly what the cover letter does. A posting that
# restricts itself to people who already hold status is a different thing.
ALREADY_AUTHORISED_ONLY = re.compile(
    r"\b(citizens?\s+and\s+permanent\s+residents?\s+only|"
    r"only\s+(?:canadian\s+)?citizens?\s+(?:or|and)\s+permanent\s+residents?|"
    r"must\s+already\s+(?:hold|have)\s+a\s+(?:valid\s+)?work\s+permit|"
    r"no\s+(?:visa\s+)?sponsorship\s+(?:is\s+)?(?:available|offered|provided)|"
    r"we\s+(?:are\s+)?(?:un(?:able|willing)|not\s+able)\s+to\s+sponsor)\b", re.I)


def screen_posting(posting, profile: Profile) -> Exclusion | None:
    """
    Return why this posting cannot convert, or None if it is worth applying to.

    Deliberately narrow. Anything not on this list is in scope — D6's answer for
    the LMIA queue is "all of them", and a screen that quietly grew into a
    relevance filter would undo the decision it is meant to serve.
    """
    noc = (posting.noc or "").strip()
    title = posting.title or ""
    body = posting.body or ""

    if noc and any(noc.startswith(p) for p in REGULATED_NOC_PREFIXES):
        return Exclusion(
            "licensed_profession",
            f"NOC {noc} is a regulated occupation — practice requires provincial "
            f"registration he cannot hold. No document fixes that")

    if m := REGULATED_TITLES.search(title):
        return Exclusion(
            "licensed_profession",
            f"{m.group(0)!r} is a licensed occupation; the posting carries "
            f"{'NOC ' + noc if noc else 'no NOC'} to check against")

    if m := ALREADY_AUTHORISED_ONLY.search(body):
        return Exclusion(
            "requires_existing_authorisation",
            f"posting says {m.group(0)!r} — sponsorship is the whole point of "
            f"applying, so this one cannot convert")

    if not profile.has_drivers_licence:
        if m := DRIVING_REQUIRED.search(f"{title}\n{body}"):
            return Exclusion(
                "drivers_licence",
                f"requires {m.group(0)!r}; none on record (PROFILE-GAPS item 8). "
                f"Record a licence in the profile and this stops excluding")

    return None


__all__ = ["screen_posting", "Exclusion"]
