"""
Loading `.env`, and finding the API key.

A `.env` file is inert on its own — nothing reads it unless something is told
to. Putting a key there and expecting it to work is a reasonable assumption
that happens to be wrong, so this makes it true rather than making the user
learn otherwise from a confusing SDK error.

Deliberately no dependency. python-dotenv handles more edge cases than this
does, but the file we care about holds one API key, and a twenty-line parser we
control beats a dependency whose behaviour we would have to look up.

**An already-set environment variable always wins.** If someone exported a key
for this shell, a stale `.env` must not silently override it — that is how you
end up billing the wrong account and not knowing why.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

ENV_FILENAME = ".env"
KEY_NAME = "ANTHROPIC_API_KEY"

_LINE = re.compile(r"""^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$""")


def candidate_paths(start: Path | None = None) -> list[Path]:
    """
    Where a `.env` might reasonably be: the working directory and every parent
    up to the repo root.

    The walk upward is the point. The CLI runs from `backend/`, and a `.env`
    almost always sits at the top of the repo — looking only in the working
    directory would miss exactly where people put it.
    """
    here = (start or Path.cwd()).resolve()
    paths = [here / ENV_FILENAME]
    paths += [parent / ENV_FILENAME for parent in here.parents]
    # The installed package's own repo root, so it works regardless of cwd.
    repo_root = Path(__file__).resolve().parents[2]
    for extra in (repo_root / ENV_FILENAME, repo_root / "backend" / ENV_FILENAME):
        if extra not in paths:
            paths.append(extra)
    return paths


def parse(text: str) -> dict[str, str]:
    """Comments, blanks, `export` prefixes and quoted values."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = _LINE.match(raw)
        if not m:
            continue
        name, value = m.group(1), m.group(2)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()
        out[name] = value
    return out


def load_dotenv(start: Path | None = None) -> Path | None:
    """
    Load the first `.env` found, without overriding anything already set.

    Returns the file it used, or None. The path is returned rather than logged
    so the caller can say *which* file a key came from — with several possible
    locations, "it picked up a key" is much less useful than "it picked up a
    key from this one".
    """
    for path in candidate_paths(start):
        if not path.is_file():
            continue
        try:
            values = parse(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        for name, value in values.items():
            os.environ.setdefault(name, value)
        return path
    return None


def api_key(start: Path | None = None) -> tuple[str | None, str]:
    """
    Return (key, where_it_came_from). Never returns the key in the description.
    """
    if key := os.environ.get(KEY_NAME):
        return key, "the environment"
    if used := load_dotenv(start):
        if key := os.environ.get(KEY_NAME):
            return key, str(used)
    return None, ""


def missing_key_message(start: Path | None = None) -> str:
    looked = "\n".join(f"  {p}" for p in candidate_paths(start)[:6])
    return (
        f"no {KEY_NAME} found.\n\n"
        f"Set it for this shell:\n"
        f"  PowerShell   $env:{KEY_NAME} = \"sk-ant-...\"\n"
        f"  bash/zsh     export {KEY_NAME}=\"sk-ant-...\"\n\n"
        f"Or put {KEY_NAME}=sk-ant-... in a .env file. Looked in:\n{looked}\n\n"
        f"A .env inside the repo is gitignored, so the key will not be committed."
    )


__all__ = ["load_dotenv", "api_key", "missing_key_message", "parse",
           "candidate_paths", "KEY_NAME"]
