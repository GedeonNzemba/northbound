"""
Tests for the apply/don't-apply screen (config/sources.yaml `exclusions_only`).

The risk here runs in both directions, and the second one is the dangerous one.
Under-screening spends a generation on a posting that cannot convert. **Over**-
screening quietly undoes D6 — Gedeon was explicit that the LMIA queue takes
every occupation, farm and greenhouse and labouring and caregiving included, and
a screen that drifted into a relevance filter would reintroduce exactly the
judgement he ruled out.

So most of these tests assert that things are NOT excluded.
"""

from __future__ import annotations

import pytest
from fixtures import PROFILE

from northbound.generate.generator import Posting
from northbound.generate.screen import screen_posting


def _p(**over) -> Posting:
    base = dict(posting_id="x", title="general labourer - farm",
                employer="Ridge Farms", body="Duties include harvesting.",
                noc="85101", queue="lmia_approved")
    base.update(over)
    return Posting(**base)


# ---- D6: the LMIA queue takes every occupation ---------------------------- #

@pytest.mark.parametrize("title,noc", [
    ("general labourer - farm", "85101"),
    ("dairy farm worker", "85100"),
    ("greenhouse worker", "85103"),
    ("livestock labourer", "85100"),
    ("farm supervisor", "82030"),
    ("butcher - retail or wholesale", "63201"),
    ("child caregiver - private home", "44100"),
    ("kitchen helper", "65201"),
    ("construction trades helper", "75110"),
    ("painter", "73112"),
    ("light duty cleaner", "65310"),
    ("Web developer", "21234"),
])
def test_work_he_can_actually_do_is_never_excluded(title, noc):
    """Every one of these is real LMIA-queue work and in scope under D6."""
    assert screen_posting(_p(title=title, noc=noc), PROFILE) is None, title


def test_a_role_he_has_never_done_is_still_in_scope():
    """
    Inexperience is what Track B and the bridge sentence are for. Only a legal
    bar is a reason not to apply.
    """
    assert screen_posting(
        _p(title="mushroom picker", noc="85101",
           body="No experience required. On-the-job training provided."),
        PROFILE) is None


# ---- licensed professions -------------------------------------------------- #

@pytest.mark.parametrize("title,noc", [
    ("family physician", "31102"),
    ("physiotherapist", "31202"),
    ("registered nurse", "31301"),
    ("pharmacist", "31120"),
    ("veterinarian", "31103"),
    ("lawyer", "41101"),
    ("secondary school teacher", "41220"),
    ("civil engineer", "21300"),
    ("construction electrician", "72200"),
])
def test_a_licensed_profession_is_excluded(title, noc):
    """No document fixes a missing provincial registration."""
    ex = screen_posting(_p(title=title, noc=noc), PROFILE)
    assert ex is not None and ex.rule == "licensed_profession", title


def test_the_trades_boundary_is_72_not_73():
    """
    One digit wide, and it matters: 73112 is painter, which is one of his own
    roles. Excluding 73xx would throw away work he has actually done.
    """
    assert screen_posting(_p(title="painter", noc="73112"), PROFILE) is None
    assert screen_posting(_p(title="concrete finisher", noc="73100"), PROFILE) is None
    assert screen_posting(_p(title="electrician", noc="72200"), PROFILE) is not None


def test_a_licensed_title_is_caught_without_a_noc():
    """Not every posting carries a usable NOC."""
    ex = screen_posting(_p(title="family physician", noc=""), PROFILE)
    assert ex is not None and ex.rule == "licensed_profession"


# ---- driver's licence (PROFILE-GAPS item 8) ------------------------------- #

@pytest.mark.parametrize("body", [
    "Applicants must hold a valid driver's licence.",
    "A valid drivers license is required for this position.",
    "Class 3 licence required.",
    "Own vehicle required for travel between sites.",
])
def test_a_posting_needing_a_driver_is_excluded(body):
    ex = screen_posting(_p(body=body), PROFILE)
    assert ex is not None and ex.rule == "drivers_licence", body


def test_recording_a_licence_turns_the_rule_off():
    """
    The rule reads the profile rather than hardcoding the answer, so the day
    item 8 is resolved the exclusion stops on its own.
    """
    import copy

    from northbound.profile import Profile

    raw = copy.deepcopy(PROFILE.raw)
    raw["identity"]["drivers_licence"] = "Code B, issued 2024"
    licensed = Profile(raw=raw, roles=PROFILE.roles,
                       evidence=PROFILE.evidence, path=PROFILE.path)

    posting = _p(body="Applicants must hold a valid driver's licence.")
    assert screen_posting(posting, PROFILE) is not None
    assert screen_posting(posting, licensed) is None


def test_driving_mentioned_without_being_required_is_not_an_exclusion():
    assert screen_posting(
        _p(body="The farm is a short drive from Leamington; transport provided."),
        PROFILE) is None


# ---- postings that cannot sponsor ----------------------------------------- #

@pytest.mark.parametrize("body", [
    "Canadian citizens and permanent residents only.",
    "We are unable to sponsor applicants for this role.",
    "No visa sponsorship is available.",
    "Applicants must already hold a valid work permit.",
])
def test_a_posting_that_will_not_sponsor_is_excluded(body):
    ex = screen_posting(_p(body=body), PROFILE)
    assert ex is not None and ex.rule == "requires_existing_authorisation", body


def test_the_legally_able_to_work_screening_question_is_not_a_bar():
    """
    A large share of these postings ask it, and answering it is exactly what
    the cover letter's authorisation paragraph does. Treating the question as
    an exclusion would drop most of the queue.
    """
    assert screen_posting(
        _p(body="Are you legally able to work in Canada?\nAre you available "
                "for weekend work?"),
        PROFILE) is None


# ---- against the real harvested set --------------------------------------- #

def test_the_real_golden_set_screens_the_way_it_should():
    """
    16 real postings. Three are licensed professions the first harvest happened
    to return — which is what made this worth building rather than leaving as a
    line in a YAML comment.
    """
    import json
    from pathlib import Path

    from northbound.cli import posting_from_json

    golden = Path(__file__).resolve().parents[2] / "postings" / "golden"
    if not golden.exists():
        pytest.skip("golden set not harvested in this checkout")

    excluded, kept = [], []
    for f in sorted(golden.glob("*.json")):
        if f.name == "MANIFEST.json":
            continue
        p = posting_from_json(f.read_text(encoding="utf-8"), default_id=f.stem)
        (excluded if screen_posting(p, PROFILE) else kept).append(p.title)

    assert sorted(excluded) == ["family physician", "family physician",
                                "physiotherapist"], excluded
    assert any("farm" in t for t in kept) and any("developer" in t.lower() for t in kept)
