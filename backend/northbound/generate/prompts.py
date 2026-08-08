"""
Prompt construction.

Two design constraints shape everything here:

1. **Cacheability.** The profile block is large, byte-stable and reused on every
   single generation. It goes first, with the cache breakpoint at its end; the
   posting — the only volatile part — goes after. Nothing time-varying is ever
   interpolated into the cached prefix, because a timestamp there would
   invalidate the cache on every call.

2. **The closed world.** The model is told, and shown, that the profile is the
   only permissible source of fact. The audit enforces it afterwards, but a
   prompt that invites invention and an audit that rejects it is a retry loop —
   cheaper to not invite it.
"""

from __future__ import annotations

from ..profile import Evidence, Profile, Role

# --------------------------------------------------------------------------- #
# The stable, cached half
# --------------------------------------------------------------------------- #

SYSTEM_CORE = """\
You write Canadian job application documents for one person, Gedeon Christ Nzemba, \
who is applying from South Africa for roles in Canada that would require employer \
sponsorship through an LMIA.

# The one rule that overrides everything

You may ONLY state facts present in the PROFILE below. You may select from it, \
reorder it, re-word it, re-frame it and re-title it for the posting. You may not \
add a fact that is not there — not a skill, not a number, not a certification, not \
a duty, not a date.

Every bullet you emit carries the `id`s of the profile entries it came from. \
Cite ALL of them — if a sentence merges two records, name both. An automated \
entailment check will read your sentence next to exactly the entries you cited, \
with no other context, and reject it if they do not support it between them. \
Write sentences that would survive that check.

The commonest way to fail it is adding texture that no entry contains. \
"Trenching and excavation" is in the profile; "bending, kneeling and swinging \
hand tools for full days" is not — posture, tools and duration are three new \
assertions. If you want the physical detail in the document, cite an entry that \
states it, or leave it out. A weaker true sentence always beats a vivid one you \
cannot source.

This is not stylistic caution. These documents support an application to a \
government programme that was reformed in 2025 because of misrepresentation. A \
claim that cannot be substantiated does not cost an interview — it costs the \
immigration route.

# What actually gets read

A recruiter spends about 7.4 seconds on the first pass, and roughly 80% of it on \
six things: name, current title, current employer, previous title and employer, \
employment dates, and education. Structure and word choice in those fields matter \
far more than elegant prose anywhere else. Do not write beautiful sentences; write \
the right facts in the right order.

# Specificity is the whole game

Around 80% of hiring managers reject applications that read as generic AI output, \
while most accept AI-assisted applications that are genuinely specific. The \
difference is not tone — it is particulars. Every paragraph you write must contain \
at least two concrete particulars: a named employer, a named place, a number, a \
named tool, or a detail taken from THIS posting. A sentence that would read \
identically on a different application is a failure.

Never write: "I am writing to express my interest", "I am excited to apply", "I \
believe I would be a great fit", "passionate about", "proven ability to", \
"leverage", "dynamic", "cutting-edge", "seamlessly", "hit the ground running".

Prefer Gedeon's own register over corporate résumé language. "Working at height in \
full protection" is better than "operated within comprehensive safety frameworks".

# Canadian conventions — non-negotiable

- Canadian English, which is neither British nor American. It keeps the British \
-our and -re endings and the doubled consonant — colour, behaviour, labour, \
neighbour, centre, travelled, cancelled — and the -ce noun: licence, defence. \
But it takes the AMERICAN -ize and -yze endings: organize, recognize, analyze, \
specialize. And it writes "program", never "programme". Gedeon writes South \
African English, which is British on the -ise endings; do not carry that over.
- Employment dates exactly as given in the profile. Never invent a month or a day.
- Never state: photo, date of birth, age, marital status, nationality, gender, ID \
or passport number, street address, postal code, salary, or referees.
- NEVER mention work permits, visas, LMIA or sponsorship on the CV. That belongs \
in cover letter paragraph 4 and nowhere else.
- Give every foreign employer a short context clause — a Canadian reader does not \
know what Kurtosys, UCOOK, Polarama or Cumpsty Electrical are.
- Map job titles to their NOC 2021 equivalent where they differ materially.
"""

TRACK_A_GUIDANCE = """\
# This is a DIRECT application — the role matches his profession

Structure: Professional Summary, Technical Skills, Work Experience, Projects, \
Education, Languages.

- Lead with the evidence that answers the employer's real doubt about an overseas \
applicant: he already works remotely for a Netherlands company (DataBalk), and has \
delivered for clients across the US, Canada, the UK and the Netherlands — including \
BMO, a Canadian bank.
- His front-end work runs continuously from February 2016 via freelance practice, \
underneath the employed roles. Do not under-state it as four years.
- Mirror the posting's stack vocabulary exactly. If it says TypeScript, write \
TypeScript. The parser matches strings, not concepts.
- NOC 21234 is TEER 1, which admits entry by accumulated experience as well as by \
degree. His route is experience — make the progression legible rather than leaving \
a reader wondering where the qualification is.
- Choose 3–4 portfolio links for THIS posting. Lead with BMO for anything Canadian \
or financial.
"""

TRACK_B_GUIDANCE = """\
# This is a TRANSFERABLE application — the role is outside his profession

This is the harder document and the more important one. Most of these employers \
are in agriculture, food production, caregiving or trades.

Structure, in this order: Summary, Relevant Experience (the general work, in \
detail), Skills (practical first), Additional Experience (the software career, \
compressed to 2–3 lines), Education & Training, Languages, Availability.

The ordering is deliberate. An employer reading for seven seconds must hit relevant \
physical work first. Opening with "Front-End Engineer at a FinTech company" tells \
them in one second that this is the wrong applicant.

What these employers weight, in their order: previous hands-on experience; physical \
capability and stamina; reliability and being asked back; safety awareness; \
English; availability; teamwork.

- Headline the target role in the employer's own words. He is applying for THAT \
job; the document should look like it.
- The software career is NOT hidden and NOT apologised for. It appears under \
Additional Experience, stated plainly.
- The bridge sentence must be honest, specific and confident. Name what he has \
genuinely done, say plainly what he has not, and name the specific training he \
would complete. Never claim a software skill is equivalent to a trade skill — \
"debugging code is like troubleshooting electrical faults" is the exact sentence \
that gets a CV binned.
- Never claim a certification he does not hold (WHMIS, fall-arrest, forklift, first \
aid). Stating willingness to obtain one is honest and expected.
- Plain, concrete register. Short sentences. Real nouns — harness, trench, conduit, \
pallet, shift.
"""


TASK_DIRECTIVE = """\
# Your task

Write BOTH documents for this posting in one pass: the CV and the cover letter.

Write them together, not one then the other. The letter must not restate the CV \
— it points at it, picks the two or three things that answer this employer's \
actual doubt, and adds what a bullet list cannot carry.

Hard constraints the schema does not express:

- `role_id` must be an id from the PROFILE. Every id in `evidence_ids` must be an \
id from the PROFILE. Invented ids are rejected outright. A bullet may cite one id \
or several; cite every entry its sentence actually draws on.
- `dates` must be copied CHARACTER FOR CHARACTER from the profile's \
`dates(exact, use verbatim)` line. Do not reformat, re-abbreviate or "tidy" them. \
Never write "Sept" — write "Sep".
- `employer` must match the profile's employer string.
- `employment_type` must be omitted where the profile says NONE ON RECORD. A \
guessed employment type is a false statement.
- Include only roles that genuinely help THIS application. A short, relevant CV \
beats a complete one.
- Every experience entry needs an `employer_context` clause.
- The cover letter's `authorisation` paragraph is the ONLY place work-permit \
status may appear. Not the CV, not the other paragraphs.
- Answer every screening question the posting asks, in `screening_answers`, one \
string per question, each naming the question's subject so it stands alone.
"""


def retry_block(previous_json: str, audit_failures: list[str],
                entailment_failures: list[str]) -> str:
    """
    The repair turn.

    Targeted correction, not regeneration. The failures name specific fields and,
    for entailment, the exact offending span — so the model can fix those and
    leave everything that passed alone. A blind "try again" would resample the
    same distribution and typically reproduce the same fault.
    """
    L = ["# YOUR PREVIOUS DRAFT WAS REJECTED",
         "",
         "This is what you produced:", "", previous_json, "",
         "These automated checks failed. They are not suggestions — a document "
         "that does not clear them is never sent.", ""]

    if audit_failures:
        L += ["## Rule violations", ""]
        L += [f"- {f}" for f in audit_failures]
        L.append("")

    if entailment_failures:
        L += ["## Claims not supported by the evidence they cite", "",
              "Each of these was checked in isolation: a verifier saw ONLY the "
              "profile entries you cited and your sentence — all of those "
              "entries together, so the failure is not that one of them was "
              "incomplete. The sentence asserts something none of them contains. "
              "Either cut the offending span, or cite the entry that does state "
              "it, or remove the sentence.", ""]
        L += [f"- {f}" for f in entailment_failures]
        L.append("")

    L += ["# What to do",
          "",
          "Return the corrected documents in full. Change ONLY what is needed to "
          "clear the failures above; keep every line that passed exactly as it "
          "was. Do not add new material to compensate — the fix for an "
          "unsupported claim is a weaker true claim, never a different strong one."]
    return "\n".join(L)


def render_profile_block(profile: Profile) -> str:
    """
    The cached prefix. Deterministic ordering, no timestamps, no volatile values —
    any of those would invalidate the cache on every request.

    Only USABLE evidence is included. An excluded entry is not shown to the model
    at all, which is stronger than showing it with a warning: it cannot cite what
    it has never seen.
    """
    L: list[str] = ["# PROFILE — the only permissible source of fact", ""]

    ident = profile.raw["identity"]
    L += [f"Name: {ident['legal_name']}",
          f"Located: {profile.contact_block['location']}", ""]

    ctx = profile.raw.get("general_work_context") or {}
    if ctx.get("summary"):
        L += ["## Background context (for tone; do not embellish)",
              " ".join(str(ctx["summary"]).split()), ""]

    def emit_roles(title: str, roles: list[Role]) -> None:
        L.append(f"## {title}")
        for r in roles:
            head = f"[{r.id}] {r.title_as_held} — {r.employer}"
            L.append(head)
            L.append(f"    dates(exact, use verbatim): {r.display_dates}")
            if r.employment_type:
                L.append(f"    employment_type: {r.employment_type}")
            else:
                L.append("    employment_type: NONE ON RECORD — do not state one")
            if r.location:
                L.append(f"    location: {r.location}")
            if r.context_clause:
                L.append(f"    context: {r.context_clause}")
            if r.canadian_title != r.title_as_held:
                L.append(f"    canadian_equivalent: {r.canadian_title}"
                         + (f" (NOC {r.noc})" if r.noc else ""))
            for b in r.bullets:
                if b.usable:
                    L.append(f"    - [{b.id}] {b.text}")
            L.append("")

    emit_roles("Professional experience", profile.roles_for("professional"))
    emit_roles("General / manual / service work", profile.roles_for("general"))

    L.append("## Education")
    for ed in profile.raw.get("education", []) or []:
        if ed.get("verify"):
            continue
        L.append(f"[{ed.get('id')}] {ed.get('credential')} — {ed.get('institution')}")
        if ed.get("completed") or ed.get("end"):
            L.append(f"    completed: {ed.get('completed') or ed.get('end')}")
        if ed.get("study_mode"):
            L.append(f"    mode: {ed['study_mode']}")
        eca = ed.get("eca")
        if isinstance(eca, dict):
            L.append(f"    ECA: {eca.get('body')} — assessed as "
                     f"{eca.get('canadian_equivalency')}, file {eca.get('file_no')}, "
                     f"issued {eca.get('issued')}")
        cur = ed.get("curriculum")
        if isinstance(cur, dict) and cur.get("summary_line"):
            L.append(f"    curriculum (COURSEWORK, never a held certification): "
                     f"{' '.join(str(cur['summary_line']).split())}")
        L.append("")

    L += ["## Certifications",
          "The ONLY independently verifiable credential is the freeCodeCamp "
          "Responsive Web Design certification (2019).",
          "Every AWS, Microsoft, Azure, Oracle and ISTQB item is COURSEWORK from "
          "remote study at IT Academy. Render them as study under Education. "
          "NEVER as held certifications.", ""]

    L.append("## Skills")
    for group, items in (profile.raw.get("skills") or {}).items():
        if isinstance(items, dict):
            if items.get("verify"):
                continue
            items = items.get("items", [])
        if items:
            L.append(f"{group}: {', '.join(str(i) for i in items)}")
    L.append("")

    L.append("## Languages")
    for lang in profile.raw.get("languages", []) or []:
        L.append(f"- {lang['language']}: speak {lang['speak']}, "
                 f"read {lang['read']}, write {lang['write']}")
    L.append("")

    L.append("## Awards")
    for a in profile.raw.get("awards", []) or []:
        L.append(f"[{a.get('id')}] {a.get('name')} ({a.get('issued')})")
    L.append("")

    L.append("## Portfolio")
    for pl in profile.raw.get("portfolio_links", []) or []:
        tags = f"  tags: {', '.join(pl.get('tags', []))}" if pl.get("tags") else ""
        L.append(f"[{pl['id']}] {pl.get('label')} — {pl.get('url')}{tags}")

    return "\n".join(L)


def posting_block(posting_text: str, employer: str, title: str,
                  screening_questions: list[str] | None = None) -> str:
    """The volatile half. Always AFTER the cache breakpoint."""
    L = ["# THE POSTING", f"Employer: {employer}", f"Title: {title}", "",
         posting_text.strip()]
    if screening_questions:
        L += ["", "# SCREENING QUESTIONS THE EMPLOYER ASKS",
              "Answer each one directly in the cover letter. Most applicants "
              "ignore these; answering them is both required and inherently "
              "specific."]
        L += [f"- {q}" for q in screening_questions]
    return "\n".join(L)


def system_blocks(profile: Profile, track: str) -> list[dict]:
    """
    System prompt as cacheable blocks.

    Order is stable-to-volatile: core rules, track guidance, then the profile,
    with the cache breakpoint on the final block so tools+system are cached
    together.
    """
    guidance = TRACK_A_GUIDANCE if track == "direct" else TRACK_B_GUIDANCE
    return [
        {"type": "text", "text": SYSTEM_CORE},
        {"type": "text", "text": guidance},
        {"type": "text", "text": render_profile_block(profile),
         "cache_control": {"type": "ephemeral"}},
    ]


__all__ = ["system_blocks", "posting_block", "render_profile_block", "retry_block",
           "SYSTEM_CORE", "TASK_DIRECTIVE", "TRACK_A_GUIDANCE", "TRACK_B_GUIDANCE"]
