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
import sys
from pathlib import Path

from .generate.generator import (
    GenerationError, Posting, choose_track, finalise, generate_application,
    render_parked,
)
from .generate.llm import (
    DEFAULT_MODEL, LLMError, RefusalError, UsageTally, default_client,
)
from .generate.prompts import TASK_DIRECTIVE, posting_block, system_blocks
from .generate.screen import screen_posting
from .env import api_key, missing_key_message
from .profile import ProfileError, load_profile

EXIT_OK, EXIT_ERROR, EXIT_PARKED = 0, 1, 2


def posting_from_json(text: str, *, default_id: str) -> Posting:
    """
    Parse one posting file. Unknown keys are an error, not a shrug.

    The golden set is frozen, so a field the harvester writes but `Posting` does
    not accept would break every entry at load time with no way to fix it by
    re-harvesting. Better to fail on the first file than to silently drop data.
    """
    data = json.loads(text)
    data.setdefault("posting_id", default_id)
    data["screening"] = tuple(data.get("screening", ()) or ())
    unknown = set(data) - set(Posting.__dataclass_fields__)
    if unknown:
        raise GenerationError(
            f"unknown field(s) in posting JSON: {', '.join(sorted(unknown))}")
    return Posting(**data)


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
        posting = posting_from_json(
            text, default_id="stdin" if src == "-" else Path(src).stem)
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


def _client():
    """
    Build a client, or explain precisely why we cannot.

    The key is looked up in the environment first and a `.env` second, and the
    source is printed — with several possible locations, "found a key" is much
    less useful than "found a key in this file", especially when two of them
    exist and one is stale.
    """
    key, source = api_key()
    if not key:
        raise GenerationError(missing_key_message())
    print(f"api key : loaded from {source}")
    return default_client(key)


def _cmd_generate(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    posting = _load_posting(args)
    track = args.track or choose_track(posting)

    if not args.no_screen and (excluded := screen_posting(posting, profile)):
        raise GenerationError(
            f"excluded by policy — {excluded}\n"
            "Pass --no-screen to generate anyway.")

    print(f"posting : {posting.employer} — {posting.title} [{posting.posting_id}]")
    print(f"track   : {track}"
          f"{'' if args.track else '  (chosen from NOC/title)'}")
    if qs := posting.questions:
        print(f"screening: {len(qs)} question(s) the letter must answer")

    if args.dry_run:
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

    client = _client()
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
        paths = finalise(outcome, profile, out_dir / "ready", pdf=not args.no_pdf)
        for label, key in (("CV", "cv"), ("Letter", "letter"),
                           ("CV (pdf)", "cv_pdf"), ("Letter (pdf)", "letter_pdf")):
            if key in paths:
                print(f"{label:<13}: {paths[key]}")
        if not args.no_pdf and "cv_pdf" not in paths:
            print("(no PDF companions — LibreOffice cannot convert on this "
                  "machine. The DOCX is the canonical artefact and is unaffected.)")
        return EXIT_OK

    paths = render_parked(outcome, profile, out_dir / "parked")
    print("PARKED — not sendable. Written for review:")
    for k in ("cv", "letter", "report"):
        print(f"  {k:7}: {paths[k]}")
    return EXIT_PARKED


def _cmd_batch(args: argparse.Namespace) -> int:
    """
    Run the whole golden set. One posting failing must not stop the run.

    `--dry-run` here is the cheap smoke test that matters most: it proves every
    posting loads, picks a track, and builds a prompt, across twenty real
    documents, without spending anything. Run it before the first paid pass.
    """
    profile = load_profile(args.profile)
    directory = Path(args.dir)
    files = sorted(f for f in directory.glob("*.json") if f.name != "MANIFEST.json")
    if not files:
        raise GenerationError(f"no posting files in {directory}")

    client = None if args.dry_run else _client()
    out_dir = Path(args.out)
    rows: list[tuple[str, str, str, str]] = []
    totals = UsageTally()
    failures = 0

    print(f"{len(files)} posting(s) from {directory}\n")
    for n, f in enumerate(files, 1):
        try:
            posting = posting_from_json(f.read_text(encoding="utf-8"),
                                        default_id=f.stem)
        except (GenerationError, json.JSONDecodeError, TypeError) as exc:
            rows.append((f.stem, "-", "LOAD-FAIL", str(exc)[:60]))
            failures += 1
            print(f"[{n:>2}/{len(files)}] {f.name}: LOAD FAILED — {exc}")
            continue

        track = args.track or choose_track(posting)
        label = f"{posting.employer[:24]} — {posting.title[:30]}"

        # config/sources.yaml `exclusions_only`. Not a relevance filter — D6's
        # answer for the LMIA queue is "all of them" — but a posting no document
        # can convert should not spend a generation.
        if not args.no_screen and (excluded := screen_posting(posting, profile)):
            rows.append((posting.posting_id, track, "EXCLUDED", excluded.rule))
            print(f"[{n:>2}/{len(files)}] {label}  EXCLUDED — {excluded}")
            continue

        if args.dry_run:
            # Build the prompt for real; a failure here is a bug we want now.
            blocks = system_blocks(profile, track)
            user = posting_block(posting.body, posting.employer, posting.title,
                                 posting.questions)
            rows.append((posting.posting_id, track, "PROMPT-OK",
                         f"{sum(len(b['text']) for b in blocks) + len(user):,} chars, "
                         f"{len(posting.questions)}q"))
            print(f"[{n:>2}/{len(files)}] {label}  [{track}]  ok")
            continue

        try:
            outcome = generate_application(
                client, posting, profile, track=track, model=args.model,
                max_attempts=args.max_attempts, verify_entailment=not args.no_verify)
        except Exception as exc:  # noqa: BLE001 — one posting must not kill the run
            rows.append((posting.posting_id, track, "ERROR", f"{type(exc).__name__}: {exc}"[:60]))
            failures += 1
            print(f"[{n:>2}/{len(files)}] {label}  ERROR — {type(exc).__name__}: {exc}")
            continue

        for field in ("calls", "input_tokens", "output_tokens",
                      "cache_creation_input_tokens", "cache_read_input_tokens"):
            setattr(totals, field, getattr(totals, field) + getattr(outcome.usage, field))

        if outcome.ready:
            try:
                finalise(outcome, profile, out_dir / "ready", pdf=not args.no_pdf)
            except (GenerationError, AssertionError) as exc:
                # Rendering gates (ATS round-trip, page length) fail after every
                # content check has passed. That is still a failure, and it must
                # not take the rest of the batch with it.
                rows.append((posting.posting_id, track, "RENDER-FAIL", str(exc)[:60]))
                failures += 1
                print(f"[{n:>2}/{len(files)}] {label}  RENDER FAILED — {exc}")
                continue
            rows.append((posting.posting_id, track, "READY",
                         f"{outcome.attempts} attempt(s)"))
        else:
            render_parked(outcome, profile, out_dir / "parked")
            rows.append((posting.posting_id, track, "PARKED", outcome.parked_reason[:60]))
        print(f"[{n:>2}/{len(files)}] {label}  [{track}]  {rows[-1][2]}  {rows[-1][3]}")

    # ---- summary ---------------------------------------------------------- #
    print("\n" + "=" * 78)
    width = max(len(r[0]) for r in rows)
    for pid, track, status, note in rows:
        print(f"  {pid:<{width}}  {track:<12}  {status:<10}  {note}")

    counts: dict[str, int] = {}
    for _, _, status, _ in rows:
        counts[status] = counts.get(status, 0) + 1
    print("\n  " + "   ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    if not args.dry_run:
        print("  " + totals.report().replace("\n", "\n  "))

    if failures:
        return EXIT_ERROR
    return EXIT_PARKED if counts.get("PARKED") else EXIT_OK


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
    g.add_argument("--no-pdf", action="store_true",
                   help="skip the PDF companions (DOCX is canonical either way)")
    g.add_argument("--no-screen", action="store_true",
                   help="apply even to postings the exclusion policy rules out")
    # Metadata for plain-text postings, and overrides for JSON ones.
    g.add_argument("--employer")
    g.add_argument("--title")
    g.add_argument("--posting-id")
    g.add_argument("--noc")
    g.add_argument("--location")
    g.add_argument("--queue", choices=["lmia_approved", "international_candidates"])
    g.add_argument("--url")
    g.set_defaults(func=_cmd_generate)

    b = sub.add_parser("batch", help="run every posting in a directory (the golden set)")
    b.add_argument("--dir", default="postings/golden",
                   help="directory of posting JSON files (default: postings/golden)")
    b.add_argument("--out", default="out")
    b.add_argument("--profile", default=None)
    b.add_argument("--track", choices=["direct", "transferable"], default=None)
    b.add_argument("--model", default=DEFAULT_MODEL)
    b.add_argument("--max-attempts", type=int, default=2)
    b.add_argument("--no-verify", action="store_true")
    b.add_argument("--no-pdf", action="store_true")
    b.add_argument("--no-screen", action="store_true",
                   help="apply even to postings the exclusion policy rules out")
    b.add_argument("--dry-run", action="store_true",
                   help="load, choose a track and build every prompt without "
                        "calling the model — the smoke test to run first")
    b.set_defaults(func=_cmd_batch)
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
