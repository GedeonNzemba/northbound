"""
Tests for `.env` loading and key lookup.

A key in the wrong place, or silently overridden, is the kind of failure that
costs an hour and a confusing SDK error — and in the override case, bills the
wrong account without saying so.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from northbound.env import (
    KEY_NAME, api_key, candidate_paths, load_dotenv, missing_key_message, parse,
)


@pytest.fixture(autouse=True)
def _no_ambient_key(monkeypatch):
    monkeypatch.delenv(KEY_NAME, raising=False)


# ---- parsing --------------------------------------------------------------- #

@pytest.mark.parametrize("line,expected", [
    ("ANTHROPIC_API_KEY=sk-ant-plain", "sk-ant-plain"),
    ('ANTHROPIC_API_KEY="sk-ant-double"', "sk-ant-double"),
    ("ANTHROPIC_API_KEY='sk-ant-single'", "sk-ant-single"),
    ("export ANTHROPIC_API_KEY=sk-ant-exported", "sk-ant-exported"),
    ("ANTHROPIC_API_KEY = sk-ant-spaced", "sk-ant-spaced"),
    ("ANTHROPIC_API_KEY=sk-ant-x  # inline note", "sk-ant-x"),
])
def test_the_shapes_people_actually_write(line, expected):
    assert parse(line)[KEY_NAME] == expected


def test_comments_and_blanks_are_ignored():
    assert parse("# nothing\n\n   \n") == {}


def test_a_hash_inside_a_quoted_value_is_kept():
    """Only an unquoted ` #` starts a comment — a key could contain one."""
    assert parse('K="abc#def"')["K"] == "abc#def"


# ---- finding the file ------------------------------------------------------ #

def test_a_repo_root_env_is_found_from_the_backend_directory(tmp_path):
    """
    The CLI runs from `backend/` and a `.env` almost always sits at the top of
    the repo. Looking only in the working directory would miss exactly where
    people put it.
    """
    (tmp_path / "backend").mkdir()
    (tmp_path / ".env").write_text(f"{KEY_NAME}=sk-ant-root\n", encoding="utf-8")

    key, source = api_key(tmp_path / "backend")
    assert key == "sk-ant-root"
    assert source == str(tmp_path / ".env"), "say WHICH file it came from"


def test_the_nearest_env_wins(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / ".env").write_text(f"{KEY_NAME}=sk-ant-far\n", encoding="utf-8")
    (tmp_path / "backend" / ".env").write_text(f"{KEY_NAME}=sk-ant-near\n",
                                               encoding="utf-8")
    assert api_key(tmp_path / "backend")[0] == "sk-ant-near"


def test_an_exported_key_beats_a_stale_env_file(tmp_path, monkeypatch):
    """
    The one that must never go the other way. Silently preferring a forgotten
    `.env` over a key someone exported on purpose bills the wrong account, and
    nothing says so.
    """
    (tmp_path / ".env").write_text(f"{KEY_NAME}=sk-ant-stale\n", encoding="utf-8")
    monkeypatch.setenv(KEY_NAME, "sk-ant-deliberate")

    key, source = api_key(tmp_path)
    assert key == "sk-ant-deliberate"
    assert source == "the environment"


def test_other_variables_in_the_file_are_loaded_too(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(f"{KEY_NAME}=sk-ant-x\nOTHER=value\n",
                                   encoding="utf-8")
    load_dotenv(tmp_path)
    import os
    assert os.environ.get("OTHER") == "value"


def test_no_env_anywhere_is_not_an_error(tmp_path, monkeypatch):
    # candidate_paths always appends the real repo root; replace it so the test
    # is fully isolated from any .env that exists on the developer's machine.
    monkeypatch.setattr("northbound.env.candidate_paths",
                        lambda start=None: [tmp_path / ".env"])
    assert load_dotenv(tmp_path) is None
    assert api_key(tmp_path) == (None, "")


# ---- the message when it is missing ---------------------------------------- #

def test_the_missing_key_message_names_the_places_it_looked(tmp_path):
    msg = missing_key_message(tmp_path)
    assert KEY_NAME in msg
    assert "PowerShell" in msg and "export" in msg
    assert str(tmp_path) in msg
    assert "gitignored" in msg, "say the key will not be committed"


def test_candidate_paths_walk_upward(tmp_path):
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    paths = candidate_paths(deep)
    assert paths[0] == deep / ".env"
    assert tmp_path / ".env" in paths


def test_the_repo_env_is_gitignored():
    """
    The loader tells people a `.env` in the repo is safe. That has to be true.
    """
    import subprocess

    repo = Path(__file__).resolve().parents[2]
    r = subprocess.run(["git", "check-ignore", "-q", ".env"],
                       cwd=repo, capture_output=True)
    assert r.returncode == 0, ".env is NOT gitignored — a key there would be committed"
