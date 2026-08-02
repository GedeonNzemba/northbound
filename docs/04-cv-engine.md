# 04 — The CV engine

The part of this system that actually decides whether it works.

---

## The generation contract

Three rules, enforced in code, not in the prompt.

**Rule 1 — Closed-world.** The generator receives exactly two inputs: `master-profile.yaml`
and the job posting. It has no web access and no other context. It may select,
reorder, re-word, re-frame and re-title anything in the profile. It may not add a
fact that is not there.

**Rule 2 — Every claim is cited.** Output is a structured object in which every
bullet carries the `id` of the profile entry it came from:

```python
class Bullet(BaseModel):
    text: str
    evidence_id: str        # must exist in master-profile.yaml

class GeneratedCV(BaseModel):
    headline: str
    summary: str
    summary_evidence_ids: list[str]
    experience: list[Section]     # each with cited bullets
    education: list[Entry]
    skills: dict[str, list[str]]
    certifications: list[Entry]
    target_noc: str
    canadian_title: str
```

**Rule 3 — Post-generation audit, and it can block.** Before a document is rendered:

*Structural checks (deterministic, cheap):*

1. Every `evidence_id` resolves to a real profile entry. Unknown id → **reject**.
2. No entry flagged `verify: true` was used. → **reject**.
3. Numbers, dates, employer names and job titles are checked verbatim against the
   profile. Any mismatch → **reject**.
4. Certification items are checked against `certifications.coursework_completed`.
   If a coursework item is rendered as a held credential → **reject**. (See
   `profile/PROFILE-GAPS.md` item 1.)
5. Banned-phrase scan for fabricated-competence language.

*Semantic check (the one that actually prevents lying):*

6. **Entailment pass.** Every generated bullet goes to a second, independent
   model call that sees **only** the source entry text and the generated line —
   no job posting, no CV, no context that could pull it toward being agreeable —
   and answers one question:

   > Does the source statement support the generated statement? `supported` /
   > `overstated` / `unsupported`, plus the specific words that go beyond the
   > source.

   Anything not `supported` → **reject**.

**Why 6 exists, and why 1–5 are not enough.** Checks 1–5 verify that a bullet
*cites* something. They do not verify that the citation *supports* it. Those are
different properties, and the gap between them is exactly where a CV becomes a
misrepresentation.

Concretely: the generator cites `gen.painter.h2` — *"Worked at height in full
body protection / fall-arrest harness on multi-storey buildings"* — and writes
**"Certified in fall-arrest systems."** Real id. Real underlying experience. Every
structural check passes. And it is false, in a way an employer can verify and a
work-permit officer can treat as misrepresentation.

The banned-phrase list in check 5 cannot catch this. It is a keyword filter, and
the failure mode is semantic drift, which has unlimited surface area. Only an
entailment check closes it.

**Cost.** One extra call per bullet, ~20 bullets per CV, on a short prompt with no
cached prefix to preserve. At `claude-opus-5` rates this is cents per application
— trivially worth it. If it ever isn't, this is the one place `claude-sonnet-5`
would be a defensible downgrade, since the task is narrow and well-specified.

**Failure handling.** A rejected generation retries once with the specific audit
failures fed back. A second failure parks the application in `DOCS_GENERATED` for
human review and it is **never auto-sent**. Truth is a hard gate, not a quality
score — and per `docs/06-decisions.md` D2, an audit failure also resets that
category's trust-ramp counter and re-locks auto-send.

---

## Canadian format rules (from `docs/00-research-findings.md` F11)

Baked into the template, not left to the model:

- **1–2 pages**, reverse-chronological.
- **No photo. No date of birth. No age. No marital status. No nationality. No ID
  number. No gender.** Canadian human-rights law makes these unwelcome and they
  get applications discarded.
- Canadian English throughout: *colour, behaviour, centre, organisation, licence
  (noun), programme*.
- **Single column. No tables, no text boxes, no images, no icons, no headers or
  footers.** ~75%+ of Canadian employers screen through an ATS and every one of
  those constructs is a parsing hazard.
- Standard section headings only: `Professional Summary`, `Work Experience`,
  `Education`, `Skills`, `Certifications`. Not "My Journey".
- Dates as `Mon YYYY – Mon YYYY`; `Present` for current.
- Locations as `City, Province` for Canadian roles; `Cape Town, South Africa` for
  his.
- Phone in international format, `+27 83 253 2615`.
- **Mirror the posting's exact vocabulary.** If the posting says "WHMIS 2015",
  write "WHMIS 2015" — the ATS is matching strings, not concepts.
- **Map the title to NOC 2021.** *"Front-End Engineer"* → *"Front-End Developer
  (NOC 21234)"*. Cite the ICAS assessment explicitly under Education — Canadian
  employers know what an ECA is and its presence signals a serious candidate.
- One line, near the top: *"Seeking an LMIA-supported position; available to
  relocate to Canada."* Employers who are not open to sponsorship should know in
  five seconds, and the ones who are should know they are in the right place.

---

## Two tracks

The `track` field from the matcher decides which of these runs.

### Track A — direct (NOC 21234 and adjacent)

Standard strong technical CV. What matters:

- Lead the summary with **7 years of production front-end experience**, and with
  the fact that he has shipped for **North American clients including BMO** — a
  Canadian bank is the single most relevant line in the whole profile for a
  Canadian employer.
- Mirror the posting's stack precisely. React role → React work first. WordPress
  role → Kurtosys and Eat Creative first. TypeScript in the posting →
  TypeScript in the skills line, not "JavaScript (ES6+), TypeScript, …".
- **TEER 1 without a degree must be argued, not assumed.** NOC 21234 is TEER 1,
  which allows entry either by university degree *or* by accumulated experience
  in a related occupation. His route is experience. The summary should make the
  seven-year progression legible — Next Steps → Eat Creative → UCOOK → Kurtosys →
  DataBalk — so a reader is never left wondering where the qualification is.
- Portfolio: 3–4 links maximum, chosen for the posting. `bmo.com` leads for
  anything Canadian or financial.

### Track B — transferable (everything else)

This is the harder document, and the one the user specifically asked to get right.
It must be **honest, specific, and confident** — not apologetic, not padded, and
never implying experience he doesn't have.

**Structure:**

1. **Headline** names the target role in the employer's own words —
   *"Painter — Residential & Commercial"*, not *"Front-End Developer"*. He is
   applying for that job; the CV should look like it.
2. **Professional summary, 3–4 lines**, in this order:
   - the relevant real experience, stated plainly;
   - what he does now, stated plainly (never hidden — an unexplained
     developer-shaped gap reads as evasion);
   - the honest bridge sentence;
   - availability and work-authorisation status.
3. **Relevant Experience** — the documented general work, in full, with the
   physical and practical detail spelled out.
4. **Additional Experience** — the professional work, compressed to 2–3 lines,
   framed for what actually transfers: reliability, working to a spec, safety
   discipline, communication with clients.
5. **Education & Training** — Northlink N1–N2–N4 Mechanical Engineering leads
   here for any trades or technical role. It is the strongest formal technical
   credential he has for non-software work and it is currently missing from his
   2026 CV entirely.
6. **Skills** — practical first. Working at height with fall-arrest PPE. Hand
   tools. Stock counting and verification. Customer service. Then languages —
   **French, English, Lingala, Kituba, Afrikaans is a genuine asset** in a
   Canadian workplace and belongs on a general CV, not buried.

**The bridge sentence.** This is the sentence the user asked for. It must do four
things: say the true thing, name the real transferable ground, be specific about
what he'd need to learn, and be short. Worked examples:

> **Painter.** "I worked as a roof painter on school and multi-storey buildings,
> working at height in full fall-arrest harness as part of a small crew. I have
> since built a career in software, and I am returning to hands-on trade work
> deliberately. I know the site discipline and I am comfortable at height; I would
> expect to complete WHMIS and any fall-protection certification your province
> requires before starting."

> **Warehouse / general labour.** "I packed and verified customer orders in a
> high-volume wholesale environment, where every order was counted twice against a
> supervisor's count — I was promoted during that placement. Seven years of
> professional work since then have been built on the same thing that made me good
> at it: accuracy under time pressure and showing up. I am ready to start at the
> floor level and learn your systems."

> **Security.** "I worked as a store security guard on full standing shifts,
> controlling the entrance and monitoring the floor, with sole accountability for
> stock loss on my shift. I understand that the job is sustained attention when
> nothing is happening. I would complete the provincial security licence before
> starting."

> **Retail sales.** "I sold footwear on the shop floor, including moving a customer
> from an entry-level product to the highest-value shoe in the store by matching the
> product to what they actually needed. Since then I have spent seven years
> explaining technical work to clients across the US, Canada and the UK. Both jobs
> are the same job: listen first, then recommend honestly."

> **Electrician's helper / construction labour.** "I worked as a general assistant
> at Cumpsty Electric — chasing and breaking walls, trenching for cable runs, and
> site preparation alongside qualified electricians. I also completed N1–N2–N4
> Mechanical Engineering at Northlink College, so I read technical drawings
> comfortably. I am applying as a helper and I expect to learn the trade from the
> ground up."

**Rules for the bridge:**

- ✅ "I have not done X professionally, but I have done Y, and here is why that
  carries over."
- ✅ Name the specific certification or training he would need. It shows he has
  looked into the actual job.
- ✅ Say plainly that he is a developer applying for manual work, and that it is
  deliberate. Employers notice the mismatch in three seconds; the CV should get
  there first.
- ❌ Never "extensive experience in" anything he hasn't done.
- ❌ Never a claim that a software skill is equivalent to a trade skill.
  *"Debugging code is like troubleshooting electrical faults"* is the exact
  sentence that gets a CV binned.
- ❌ Never inflate the general roles. They were vacation placements; they were
  real, they were rated well, and that is enough.

### Specificity is the defence — not sounding human (F-D)

2026 surveys: **67%** of hiring managers say they can spot an AI-written cover
letter and **54%** view them negatively. But **80% reject *generic* AI output
while 63% accept AI-assisted applications that are genuinely personalised**, and
reviewers spend **under 30 seconds** on an obviously-templated letter versus
**2–3 minutes** on one that reads as written for them.

So the objective is not "sound human". It is **be specific** — because
specificity is exactly what a template cannot produce at volume, and what a
reviewer uses to tell the difference.

- **Specificity budget — enforced, not aspirational.** Every generated paragraph
  must carry at least **two concrete particulars**: a named employer, a named
  site, a number, a named tool, or a detail lifted from *this* posting. A
  paragraph that would read identically on another application fails the check.
- **Structural variation.** Cover letters must not share a skeleton with the
  company name swapped. Vary the opening move, paragraph order and length.
  Two of Gedeon's letters side by side must not look like one template.
- **Answer the screening questions.** ~30% of LMIA postings ask them (spike 4).
  Answering directly, near the top, is inherently non-generic — and most
  applicants ignore them entirely.
- **Use Gedeon's own register.** His real phrasing — *"working at height in full
  protection"*, *"I've really learnt a lot of team work ethics"* — is more
  convincing than polished corporate prose. Draw vocabulary from the profile,
  not from résumé-speak.

**Banned phrases** (audit rule 5): *extensive experience in* [uncited], *expert
in* [uncited], *fully certified*, *licensed* (without a licence in the profile),
*years of experience in* [a field with no profile entry], *proven track record in*
[uncited], *equivalent to*, *essentially the same as*.

**AI-genericness tells**, banned for the same reason (F-D): *I am writing to
express my interest*, *I am excited to apply*, *I believe I would be a great
fit*, *In today's fast-paced world*, *I am confident that my skills*, *dynamic*,
*passionate about*, *team player* used as filler rather than evidenced,
*leverage* as a verb, *proven ability to*, *seamlessly*, *cutting-edge*.

---

## Cover letters

One page, four paragraphs, and **never a template with a swapped company name** —
that is worse than no personalisation because it is visibly mass-produced.

1. The specific role, where it was seen, and one concrete sentence about *this*
   employer drawn from the posting itself.
2. The strongest matching evidence — two or three cited specifics, not adjectives.
3. Track A: the depth argument. Track B: the bridge sentence.
4. Work authorisation, stated directly and without apology: *"I am currently in
   South Africa and would require an LMIA-supported work permit. I hold an ICAS
   educational credential assessment for Canada and I am prepared to move on your
   timeline."*

Signed with his real name, phone, email and portfolio. No tracking, no unsubscribe
footer.

---

## Rendering

**REVISED 2026-08-02 by `docs/07-cv-engine-research.md` — DOCX is now primary.**

Earlier this said "HTML → WeasyPrint → PDF, plus a .docx". That was backwards.
Testing across six major ATS platforms puts **DOCX at ~97% parsing accuracy and
PDF at ~72%** (F-A), and PDFs without a proper text layer fail at up to 85%.

- **DOCX is the canonical artefact**, generated natively via `python-docx` from
  the structured object — never converted from HTML or PDF, which reintroduces
  the layout artefacts that break parsers.
- **PDF is a companion** for the human reader and portfolio use, rendered
  separately from the same structured object.
- Where a posting specifies a format, honour it exactly.

### Layout is a specification, not a style choice

Eye-tracking research (F-C: 30 recruiters, 10 weeks) shows a **7.4-second**
initial screen with **~80% of it on six fields**: name, current title, current
employer, previous title/employer, employment dates, education. Reading follows
an F-pattern. Therefore:

- Those six fields get visual priority — top of page, left-aligned, bold titles,
  an unambiguous date column.
- Employer and title on their own line. Never buried mid-paragraph.
- **Bullets, never prose**, in the experience section.
- Single column, generous white space, clear section headings.
- **Contact details are body text in the first block. NEVER a header or footer** —
  many parsers never read that region, and the application arrives anonymous (F-B).
- No tables, columns, text boxes, images or icons anywhere.

The practical consequence for generation: at seven seconds, *structure and
keyword placement carry the first pass, not prose quality*. The model's effort
belongs in selecting and ordering the right facts.

- Filename: `Gedeon-Nzemba-CV-{Employer}-{Role}.docx`. It shows up in the
  employer's inbox and it should look considered.
- **ATS round-trip test — the highest-value check in the system.** Every
  generated document is parsed back by a real résumé parser and the result is
  diffed against the structured object it came from. If the parser cannot recover
  all six fields from F-C, the document is **rejected**, however good it looks.
  Run against at least two independent parsers so a pass is not one library's
  quirk. Threshold is 100% on those fields — anything less is a defect.
- Both DOCX and PDF are produced and retained.
- Every generated document is retained and linked from the application record.
  When an employer replies three weeks later, Gedeon needs to see exactly what
  they were sent.
