"""
Tests for the golden-set harvester's selection logic (spikes/06_golden_set.py).

The harvest itself runs on a GitHub Actions runner and cannot be tested here —
this container's egress policy blocks gc.ca. But the parts that decide *what
lands in the frozen set*, and *what shape it lands in*, are pure functions, and
they are worth testing precisely because the set is frozen: a posting admitted
with a truncated body or a missing employer is a permanent hole in every
evaluation run that follows, and re-harvesting to fix it destroys
comparability.

The file is loaded by path rather than imported, because `spikes/` is a
standalone script directory with no package and no repo imports — that is
deliberate, so a spike runs on a bare runner.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from fixtures import POSTING_BODY

from northbound.generate.generator import Posting

SPIKE = Path(__file__).resolve().parents[2] / "spikes" / "06_golden_set.py"


def _load():
    spec = importlib.util.spec_from_file_location("golden_set", SPIKE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gs = _load()


def _rec(**over) -> dict:
    base = {
        "posting_id": "49816590",
        "title": "general labourer - farm",
        "employer": "Ridge Farms",
        "body": POSTING_BODY + "x" * 400,
        "queue": "lmia_approved",
        "noc": "85101",
        "_body_chars": len(POSTING_BODY) + 400,
        "_screening_count": 1,
        "_emails": ["jobs@ridgefarms.example"],
        "_revealed_additional": True,
        "_extraction_paths": {"title": "jsonld"},
    }
    base.update(over)
    return base


# ---- admission ------------------------------------------------------------ #

def test_a_complete_posting_is_admitted():
    ok, why = gs.usable(_rec())
    assert ok, why


@pytest.mark.parametrize("field", ["title", "employer", "body"])
def test_a_posting_missing_a_required_field_is_rejected(field):
    ok, why = gs.usable(_rec(**{field: ""}))
    assert not ok and field in why


def test_a_truncated_body_is_rejected():
    """
    The likeliest silent failure: a selector matches a stub container and the
    'posting' is a nav fragment. It would generate a plausible-looking CV
    against nothing.
    """
    ok, why = gs.usable(_rec(body="Apply now", _body_chars=9))
    assert not ok and "too short" in why


def test_a_fetch_error_is_rejected_rather_than_stored():
    ok, why = gs.usable({"posting_id": "x", "error": "TimeoutError: nav"})
    assert not ok and "Timeout" in why


# ---- D6: the international queue takes developer roles only --------------- #

@pytest.mark.parametrize("title", [
    "web developer", "front-end developer", "Full Stack Developer",
    "software engineer", "programmer analyst", "React Developer",
])
def test_developer_titles_are_recognised(title):
    assert gs.is_dev_role(_rec(title=title, noc=""))


@pytest.mark.parametrize("title", [
    "general labourer - farm", "kitchen helper", "long haul truck driver",
    "painter", "food service supervisor",
])
def test_general_titles_are_not_developer_roles(title):
    assert not gs.is_dev_role(_rec(title=title, noc="85101"))


def test_a_tech_noc_admits_a_role_whose_title_says_nothing():
    assert gs.is_dev_role(_rec(title="IT specialist", noc="21234"))


# ---- shape: what gets written --------------------------------------------- #

def test_written_fields_are_exactly_the_fields_posting_accepts():
    """
    The CLI rejects unknown keys in a posting file. If the harvester writes a
    field Posting doesn't have, every golden posting fails to load — and the
    set is frozen, so it cannot be fixed by re-harvesting.
    """
    assert set(gs.POSTING_FIELDS) <= set(Posting.__dataclass_fields__)


def test_a_written_posting_round_trips_into_the_generator_input():
    rec = _rec()
    payload = {k: rec[k] for k in gs.POSTING_FIELDS if k in rec}
    payload["screening"] = tuple(rec.get("screening", ()) or ())
    posting = Posting(**payload)
    assert posting.posting_id == "49816590"
    assert posting.slug.startswith("Ridge-Farms")
    assert posting.questions, "the fixture posting asks a screening question"


def test_provenance_stays_out_of_the_posting_file():
    """Underscore-prefixed diagnostics belong in the manifest, not the input."""
    assert not [f for f in gs.POSTING_FIELDS if f.startswith("_")]


# ---- body cleaning -------------------------------------------------------- #

def test_boilerplate_tail_is_cut():
    text = "Real duties here.\n\nSimilar jobs\nSome other posting\nDate modified: 2026"
    assert gs._clean(text) == "Real duties here."


def test_blank_line_runs_are_collapsed():
    assert "\n\n\n" not in gs._clean("a\n\n\n\n\nb")


# ---- the listing walk: filter before fetching ----------------------------- #

LISTING_HTML = """
<ul>
 <li><a href="/jobsearch/jobposting/1001?x=1">web developer</a><span>Acme</span></li>
 <li><a href="/jobsearch/jobposting/1002?x=1">general labourer - farm</a><span>Ridge</span></li>
 <li><a href="/jobsearch/jobposting/1003?x=1">Full Stack Developer</a><span>North</span></li>
 <li><a href="/jobsearch/jobposting/1004?x=1">long haul truck driver</a><span>Transp</span></li>
 <li><a href="/jobsearch/jobposting/1005?x=1">programmer analyst</a><span>Data Co</span></li>
 <li><a href="/jobsearch/jobposting/1006?x=1">kitchen helper</a><span>Cafe</span></li>
</ul>"""


class _Resp:
    status_code = 200
    text = LISTING_HTML


class _Session:
    def get(self, url, timeout=None):
        return _Resp()


@pytest.fixture(autouse=True)
def _no_politeness_delay(monkeypatch):
    monkeypatch.setattr(gs.time, "sleep", lambda *a: None)


@pytest.mark.skipif(gs.BeautifulSoup is None, reason="beautifulsoup4 not installed")
def test_the_lmia_walk_takes_every_occupation():
    """D6: sponsorship is proven, so occupation is not a filter here."""
    assert gs.collect(_Session(), "u{page}", 1) == [
        "1001", "1002", "1003", "1004", "1005", "1006"]


@pytest.mark.skipif(gs.BeautifulSoup is None, reason="beautifulsoup4 not installed")
def test_the_international_walk_filters_titles_before_fetching_anything():
    """
    D6 the other way — and the reason it happens at the listing stage.

    Developer roles are ~0.4% of the international queue. Loading each posting
    and deciding afterwards means hundreds of browser navigations, each with two
    disclosure clicks, to find five. The title is already in the result card, so
    one cheap HTML fetch covers 25 postings.
    """
    got = gs.collect(_Session(), "u{page}", 1, title_filter=gs.TECH_TITLE)
    assert got == ["1001", "1003", "1005"]
    assert "1002" not in got and "1006" not in got, "general work is out of scope here"


# ---- extraction path reporting -------------------------------------------- #

def test_first_reports_which_path_won():
    value, path = gs._first(("jsonld", ""), ("h1", "  Farm   Worker "), ("title", "x"))
    assert value == "Farm Worker" and path == "h1"


def test_first_reports_none_when_every_path_is_empty():
    assert gs._first(("a", ""), ("b", None)) == ("", "none")
