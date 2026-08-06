"""
CLI tests.

The exit code is the contract: a scheduler will read it, and the difference
between 0 and 2 is the difference between a document going to an employer and a
document waiting for a human. That gets tested directly.
"""

from __future__ import annotations

import json

import pytest
from fixtures import POSTING_BODY, cv, docset
from test_generator import FakeClient

from northbound import cli

POSTING = {
    "posting_id": "49816590",
    "title": "general labourer - farm",
    "employer": "Ridge Farms",
    "location": "Leamington, Ontario",
    "noc": "85101",
    "queue": "lmia_approved",
    "body": POSTING_BODY,
}


@pytest.fixture
def posting_file(tmp_path):
    p = tmp_path / "49816590.json"
    p.write_text(json.dumps(POSTING), encoding="utf-8")
    return p


def _patch_client(monkeypatch, drafts, verdict_for=None):
    client = FakeClient(drafts, verdict_for)
    monkeypatch.setattr(cli, "default_client", lambda *a, **k: client)
    return client


# --------------------------------------------------------------------------- #

def test_dry_run_needs_no_api_key_and_prints_the_prompt(posting_file, capsys):
    code = cli.main(["generate", "--posting", str(posting_file), "--dry-run"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "===== SYSTEM =====" in out and "===== USER =====" in out
    assert "Ridge Farms" in out
    assert "track   : transferable" in out


def test_ready_application_exits_zero_and_writes_documents(
        posting_file, tmp_path, monkeypatch, capsys):
    _patch_client(monkeypatch, [docset()])
    code = cli.main(["generate", "--posting", str(posting_file),
                     "--out", str(tmp_path / "out")])
    out = capsys.readouterr().out

    assert code == cli.EXIT_OK
    assert "READY" in out
    written = list((tmp_path / "out" / "ready").glob("*.docx"))
    assert len(written) == 2


def test_parked_application_exits_two_and_is_not_in_ready(
        posting_file, tmp_path, monkeypatch, capsys):
    bad = docset(cv_=cv(summary_evidence_ids=["gen.does.not.exist"]))
    _patch_client(monkeypatch, [bad, bad])
    code = cli.main(["generate", "--posting", str(posting_file),
                     "--out", str(tmp_path / "out")])
    out = capsys.readouterr().out

    assert code == cli.EXIT_PARKED
    assert "PARKED — not sendable" in out
    assert not (tmp_path / "out" / "ready").exists(), \
        "a parked application must never land in the ready directory"
    assert (tmp_path / "out" / "parked").exists()


def test_a_url_is_refused_with_a_straight_answer(capsys):
    code = cli.main(["generate", "--posting",
                     "https://www.jobbank.gc.ca/jobsearch/jobposting/49816590"])
    err = capsys.readouterr().err
    assert code == cli.EXIT_ERROR
    assert "Phase 2" in err


def test_plain_text_posting_requires_employer_and_title(tmp_path, capsys):
    p = tmp_path / "posting.txt"
    p.write_text(POSTING_BODY, encoding="utf-8")
    code = cli.main(["generate", "--posting", str(p)])
    assert code == cli.EXIT_ERROR
    assert "--employer and --title" in capsys.readouterr().err


def test_plain_text_posting_works_with_metadata_flags(
        tmp_path, monkeypatch, capsys):
    p = tmp_path / "posting.txt"
    p.write_text(POSTING_BODY, encoding="utf-8")
    _patch_client(monkeypatch, [docset()])
    code = cli.main(["generate", "--posting", str(p),
                     "--employer", "Ridge Farms",
                     "--title", "general labourer - farm",
                     "--out", str(tmp_path / "out")])
    assert code == cli.EXIT_OK
    assert "Ridge Farms" in capsys.readouterr().out


def test_unknown_json_field_is_rejected_rather_than_ignored(tmp_path, capsys):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({**POSTING, "salary": "$17.50/hr"}), encoding="utf-8")
    code = cli.main(["generate", "--posting", str(p), "--dry-run"])
    assert code == cli.EXIT_ERROR
    assert "salary" in capsys.readouterr().err


def test_a_flag_overrides_the_saved_posting(posting_file, capsys):
    cli.main(["generate", "--posting", str(posting_file), "--dry-run",
              "--title", "web developer"])
    out = capsys.readouterr().out
    assert "web developer" in out
    assert "track   : direct" in out, "the corrected title must change the track"


def test_forcing_a_track_overrides_the_chooser(posting_file, capsys):
    cli.main(["generate", "--posting", str(posting_file), "--dry-run",
              "--track", "direct"])
    out = capsys.readouterr().out
    assert "track   : direct" in out
    assert "chosen from" not in out


# --------------------------------------------------------------------------- #
# batch — the golden-set runner
# --------------------------------------------------------------------------- #

DEV_POSTING = {
    "posting_id": "49900001",
    "title": "front end developer",
    "employer": "Northwind Digital",
    "location": "Toronto, Ontario",
    "noc": "21234",
    "queue": "international_candidates",
    "body": "Hiring a front end developer for React and TypeScript dashboards.",
}


@pytest.fixture
def golden(tmp_path):
    """A miniature golden set: one of each track, plus the manifest."""
    d = tmp_path / "golden"
    d.mkdir()
    (d / "49816590.json").write_text(json.dumps(POSTING), encoding="utf-8")
    (d / "49900001.json").write_text(json.dumps(DEV_POSTING), encoding="utf-8")
    (d / "MANIFEST.json").write_text(json.dumps({"frozen": True}), encoding="utf-8")
    return d


def test_batch_dry_run_builds_every_prompt_without_an_api_key(golden, capsys):
    """The cheap smoke test: run this before spending anything."""
    code = cli.main(["batch", "--dir", str(golden), "--dry-run"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "2 posting(s)" in out, "MANIFEST.json must not be treated as a posting"
    assert out.count("PROMPT-OK") >= 2


def test_batch_chooses_a_track_per_posting(golden, capsys):
    cli.main(["batch", "--dir", str(golden), "--dry-run"])
    out = capsys.readouterr().out
    assert "transferable" in out and "direct" in out


def test_batch_exits_two_when_anything_parked(golden, tmp_path, monkeypatch, capsys):
    bad = docset(cv_=cv(summary_evidence_ids=["gen.does.not.exist"]))
    _patch_client(monkeypatch, [docset(), bad, bad, docset()])
    code = cli.main(["batch", "--dir", str(golden), "--out", str(tmp_path / "out"),
                     "--no-pdf"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_PARKED
    assert "READY" in out and "PARKED" in out


def test_one_unloadable_posting_does_not_stop_the_run(golden, tmp_path, monkeypatch, capsys):
    """A twenty-posting run must not die on file three."""
    (golden / "broken.json").write_text('{"posting_id": "x", "salary": "$17"}',
                                        encoding="utf-8")
    _patch_client(monkeypatch, [docset(), docset()])
    code = cli.main(["batch", "--dir", str(golden), "--out", str(tmp_path / "out"),
                     "--no-pdf"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_ERROR, "a load failure is reported, not swallowed"
    assert "LOAD-FAIL" in out
    assert out.count("READY") >= 2, "the other postings still ran"


def test_batch_aggregates_usage_across_postings(golden, tmp_path, monkeypatch, capsys):
    """
    Cache effectiveness is only visible across postings — the first call writes
    the prefix, every one after it should read it.
    """
    _patch_client(monkeypatch, [docset(), docset()])
    cli.main(["batch", "--dir", str(golden), "--out", str(tmp_path / "out"),
              "--no-pdf"])
    out = capsys.readouterr().out
    assert "cached" in out and "call(s)" in out


def test_batch_on_an_empty_directory_says_so(tmp_path, capsys):
    (tmp_path / "empty").mkdir()
    code = cli.main(["batch", "--dir", str(tmp_path / "empty"), "--dry-run"])
    assert code == cli.EXIT_ERROR
    assert "no posting files" in capsys.readouterr().err
