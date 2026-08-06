"""
`northbound` — the command line entry point.

Phase 1 is one command: turn a posting into a checked application. Discovery and
sending are Phase 2 and 3; until then the posting arrives as a file that a human
saved, which is also the fastest way to build the golden set.

    northbound generate --posting postings/49816590.json --out out/
    northbound generate --posting posting.txt --employer "Ridge Farms" \\
        --title "general labourer - farm" --out out/

Exit codes are meaningful, because this will eventually be called by a scheduler
and not by a person:

    0   ready    — every check passed, documents written
    2   parked   — documents written for human review, NOT sendable
    1   error    — the pipeline could not run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .generate.generator import (
    GenerationError, Posting, choose_track, finalise, generate_application,
    render_parked,
)
from .generate.llm import DEFAULT_MODEL, LLMError, RefusalError, default_client
from .profile import ProfileError, load_profile

EXIT_OK, EXIT_ERROR, EXIT_PARKED = 0, 1, 2


def _load_posting(args: argparse.Namespace) -> Posting:
    """
    Accept a JSON posting, a plain-text body, or stdin.

    JSON is the form the scraper will emit; plain text is the form a human has
    when they have copied a page out of a browser, which is how the golden set
    gets built before the scraper exists.
    """
    src = args.posting

    if src.startswith(("http://", "https://")):
        raise GenerationError(
            "fetching a posting by URL is Phase 2 — the discovery layer, with the "
            "two-click contact reveal, is not built yet. Save the posting to a "
            "file and pass that, or pass its JSON."
        )

    text = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")

    if src.endswith(".json") or text.lstrip().startswith("{"):
        data = json.loads(text)
        data.setdefault("posting_id", "stdin" if src == "-" else Path(src).stem)
        data["screening"] = tuple(data.get("screening", ()) or ())
        known = {f for f in Posting.__dataclass_fields__}
        unknown = set(data) - known
        if unknown:
            raise GenerationError(
                f"unknown field(s) in posting JSON: {', '.join(sorted(unknown))}")
        posting = Posting(**data)
    else:
        if not (args.employer and args.title):
            raise GenerationError(
                "a plain-text posting needs --employer and --title (a JSON posting "
                "carries them itself)")
        posting = Posting(
            posting_id=args.posting_id or (Path(src).stem if src != "-" else "stdin"),
            title=args.title, employer=args.employer, body=text,
            url=args.url or "", location=args.location or "", noc=args.noc or "",
            queue=args.queue or "",
        )

    # Explicit flags win over the file, so one saved posting can be re-run with
    # a corrected NOC or title without editing it.
    over = {k: v for k, v in (("title", args.title), ("employer", args.employer),
                              ("noc", args.noc), ("location", args.location),
                              ("queue", args.queue), ("url", args.url)) if v}
    return Posting(**{**posting.__dict__, **over}) if over else posting


def _cmd_generate(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    posting = _load_posting(args)
    track = args.track or choose_track(posting)

    print(f"posting : {posting.employer} — {posting.title} [{posting.posting_id}]")
    print(f"track   : {track}"
          f"{'' if args.track else '  (chosen from NOC/title)'}")
    if qs := posting.questions:
        print(f"screening: {len(qs)} question(s) the letter must answer")

    if args.dry_run:
        from .generate.prompts import TASK_DIRECTIVE, posting_block, system_blocks
        blocks = system_blocks(profile, track)
        print("\n===== SYSTEM =====")
        for b in blocks:
            print(b["text"])
            print("-" * 70)
        print("===== USER =====")
        print(posting_block(posting.body, posting.employer, posting.title, qs))
        print()
        print(TASK_DIRECTIVE)
        return EXIT_OK

    client = default_client(os.environ.get("ANTHROPIC_API_KEY"))
    outcome = generate_application(
        client, posting, profile,
        track=track, model=args.model, max_attempts=args.max_attempts,
        verify_entailment=not args.no_verify,
    )

    print()
    print(outcome.report())
    print()

    out_dir = Path(args.out)
    if outcome.ready:
        paths = finalise(outcome, profile, out_dir / "ready")
        print(f"CV     : {paths['cv']}")
        print(f"Letter : {paths['letter']}")
        return EXIT_OK

    paths = render_parked(outcome, profile, out_dir / "parked")
    print("PARKED — not sendable. Written for review:")
    for k in ("cv", "letter", "report"):
        print(f"  {k:7}: {paths[k]}")
    return EXIT_PARKED


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="northbound", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="produce a CV and cover letter for one posting")
    g.add_argument("--posting", required=True,
                   help="path to a posting (.json or .txt), or '-' for stdin")
    g.add_argument("--out", default="out", help="output directory (default: out)")
    g.add_argument("--profile", default=None, help="override the master profile path")
    g.add_argument("--track", choices=["direct", "transferable"], default=None,
                   help="force a track; default is chosen from the posting's NOC/title")
    g.add_argument("--model", default=DEFAULT_MODEL)
    g.add_argument("--max-attempts", type=int, default=2,
                   help="drafts before parking (default 2: one draft, one repair)")
    g.add_argument("--no-verify", action="store_true",
                   help="skip the entailment pass. Faster and cheaper for prompt "
                        "iteration; NEVER appropriate for a document to be sent")
    g.add_argument("--dry-run", action="store_true",
                   help="print the exact prompt and exit without calling the model")
    # Metadata for plain-text postings, and overrides for JSON ones.
    g.add_argument("--employer")
    g.add_argument("--title")
    g.add_argument("--posting-id")
    g.add_argument("--noc")
    g.add_argument("--location")
    g.add_argument("--queue", choices=["lmia_approved", "international_candidates"])
    g.add_argument("--url")
    g.set_defaults(func=_cmd_generate)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except RefusalError as exc:
        print(f"error: {exc}\n"
              "The request was declined by a safety classifier. Retrying the "
              "same posting will fail the same way — check what in the posting "
              "text triggered it before trying again.", file=sys.stderr)
        return EXIT_ERROR
    except (GenerationError, ProfileError, LLMError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except ImportError as exc:
        print(f"error: {exc}\n"
              "The Anthropic SDK is needed for real generation: pip install anthropic",
              file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
