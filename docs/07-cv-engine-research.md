# 07 — CV engine: research findings and design consequences

Researched 2026-08-02, before implementation. Every finding below is followed by
what it actually changes in the build. Findings that change nothing are omitted.

Source grades follow `docs/00`: **A** = multiple independent credible sources or
primary research; **B** = single credible source; **C** = commercial content with
an interest in the claim.

---

## F-A — DOCX parses far better than PDF. **This inverts the current design.**

2026 testing across six major ATS platforms: **DOCX ~97% parsing accuracy, PDF
~72%**. Independent multi-month testing across Workday, Greenhouse and iCIMS
reports `.docx` parsing reliably where PDF hits edge cases. Image-based or
"Print to PDF" files — which lack a real text layer — fail at up to 85%.

**Grade: B.** Consistent across independent sources and mechanically plausible
(DOCX is a structured XML document; PDF is a page-description format where text
order is a rendering artefact). But no vendor publishes official figures, so
treat the exact percentages as directional.

**Changes:**
- **DOCX becomes the primary artefact**, not the secondary one. `docs/03`
  currently says "HTML → WeasyPrint → PDF, plus a .docx". That is backwards.
- Generate DOCX natively from the structured object via `python-docx` — never by
  converting from PDF or HTML, which reintroduces layout artefacts.
- PDF is produced as a **companion**, for the human reader and for portfolio use.
- Where a posting or form specifies a format, honour it exactly.

## F-B — Contact details in headers/footers are invisible to parsers

Many ATS parsers never read the header/footer region, so a name, email and phone
placed there vanish from the parsed record — the application arrives anonymous.

**Grade: B.**

**Changes:** hard constraint, enforced by the renderer and asserted in tests.
Contact details are body text, first block, plain paragraphs. No header, no
footer, no text box, no table, no column, no image, no icon.

## F-C — Recruiters spend ~7.4 seconds, and ~80% of it on six fields

The Ladders eye-tracking study (30 recruiters, 10 weeks, hundreds of resumes)
found an initial screen of **7.4 seconds**, with roughly **80% of that time on
name, current title and employer, previous title and employer, employment dates,
and education**. Recruiters read in an F/E pattern: current role → previous role
→ right to the dates → down to education. Resumes performed *worse* with
cluttered layouts, multiple columns, long sentences, little white space, and
missing section or job headers.

**Grade: A.** Primary eye-tracking research with published methodology. Widely
replicated in guidance since. Note it measures the *initial human screen*, not
the full review, and it predates ATS ubiquity — so it is about what happens
after the parser, not instead of it.

**Changes — this is a layout specification, not a style preference:**
- Those six fields get visual priority: top of page, left-aligned, bold titles,
  unambiguous date column.
- Employer and job title on their own line, never buried mid-paragraph.
- **Bullets, never prose paragraphs**, in the experience section.
- Generous white space; single column always.
- Education visible without scrolling to a second page where possible — for the
  general-work track especially, since Northlink N1–N2–N4 and the ICAS
  assessment do real work there.
- **Consequence for the LLM:** the generator's careful prose matters far less
  than most people assume. Seven seconds means *structure and keywords carry the
  first pass.* Spend the model's effort on selecting and ordering the right
  facts, not on elegant sentences.

## F-D — Genericness is the risk, not AI. **This is the most important finding.**

2026 surveys: **67% of hiring managers say they can identify AI-generated cover
letters** and **54% view them negatively**. **80% reject generic AI output** —
but **63% accept AI-assisted letters that are genuinely personalised.** Hiring
managers spend **under 30 seconds** on an obviously-AI letter versus **2–3
minutes** on one that reads as authentic. Meanwhile ~29% of candidates now use AI
on applications, up from ~17% the year before, and 67% of HR leaders say
AI-generated applications have slowed their hiring.

**Grade: B/C.** Self-reported survey data, some from vendors selling
"humanisation" tools — the exact percentages deserve scepticism. The *direction*
is corroborated across independent sources and matches the mechanism: reviewers
are saturated with template output and discount anything that pattern-matches to
it.

**Changes — this reframes the engine's objective.** The goal is not "sound
human". It is **be specific**, because specificity is what genericness cannot
fake and what a template cannot produce at volume:

- **Specificity budget.** Every generated paragraph must carry at least two
  concrete particulars — a named employer, a named site, a number, a named tool,
  a detail lifted from *this* posting. Enforced as a check, not a hope.
- **Ban the tells.** "I am excited to apply", "I believe I would be a great fit",
  "dynamic", "passionate", "team player" used as filler, "In today's fast-paced
  world", "I am writing to express my interest". These go in the banned-phrase
  list alongside the fabrication phrases from `docs/04`.
- **Structural variation.** Cover letters must not share a skeleton with only the
  company name swapped. Vary opening move, paragraph order and length across
  applications; a reviewer comparing two of Gedeon's letters should not see a
  template.
- **The screening questions are an asset.** ~30% of LMIA postings ask things like
  *"Are you available for shift or on-call work?"* (spike 4). Answering those
  directly and specifically is inherently non-generic, and most applicants ignore
  them. Always answer them, explicitly, near the top.
- **Use Gedeon's own register.** His real sentences — "working at height in full
  protection", "worked as a team and I've really learnt a lot of team work
  ethics" — are more convincing than polished corporate prose. The generator
  should draw vocabulary from the profile, not from résumé-speak.

## F-E — Entailment (NLI) is the validated method for catching invented claims

Current hallucination-detection research converges on natural language inference:
classify a generated claim against its source as **supported / refuted /
unverifiable**. Fact-level and span-level verification outperform
whole-document scoring, and hybrid detection-plus-verification approaches are
state of the art. Grounding generation in retrieved source text is the primary
mitigation.

**Grade: A.** Peer-reviewed and arXiv literature, multiple independent groups.

**Changes:** confirms the entailment pass added to `docs/04` and sharpens it:
- Verify at **claim level** — one bullet at a time — not per document. Whole-CV
  scoring is documented to be weaker.
- The verifier sees **only** the source entry and the generated line. No posting,
  no CV, nothing that could bias it toward agreeing.
- Three-way output (`supported` / `overstated` / `unsupported`), and it must
  return **the specific span** that goes beyond the source, so retries are
  targeted rather than a blind regenerate.

## F-F — LLM-as-judge is usable for quality, with known biases to design around

Documented failure modes: **position bias** (order of candidates affects the
verdict), **verbosity bias** (longer output scored higher), **self-enhancement
bias** (a model favours its own family's output), and **length-confidence bias**
(fluent hallucination under-penalised). Mitigations: calibrate against human
judgement using **Cohen's kappa** rather than raw agreement; use **panels of
smaller models from disjoint families** rather than one large judge; reserve
frontier models for calibration and audit.

**Grade: A/B.** arXiv research plus consistent practitioner guidance.

**Changes to the evaluation harness (below):**
- Never judge a single document in isolation on an absolute 1–10 scale — that is
  where verbosity bias lives. Prefer pairwise against a reference.
- Randomise position on every pairwise comparison, and run both orders.
- The judge must **not** be the same prompt or configuration as the generator.
- Calibrate on ~20 documents Gedeon rates himself; track kappa. If the judge
  does not agree with him, the judge is wrong, not him.

---

## The evaluation harness — the actual answer to "engineered to fail"

A CV engine fails quietly. It produces plausible documents that get ignored, and
without measurement nobody knows whether the problem is the CV, the targeting or
the market. Four layers, cheapest first, every one automated and run on every
prompt change.

### Layer 1 — Deterministic checks (free, instant, block on failure)

| Check | Fails when |
|---|---|
| Claim audit | Any bullet cites a missing/`verify: true` id, or misstates a name, number or date |
| Coursework rule | Any IT Academy item rendered as a held certification (D1) |
| Referee rule | Any referee name appears at all |
| Structure | Headers/footers, tables, columns, text boxes or images present |
| Length | Over two pages |
| Banned phrases | Fabrication tells or AI-genericness tells present |
| Specificity budget | Any paragraph with fewer than two concrete particulars |
| Screening questions | Posting asks them and the letter does not answer them |
| Canadian English | US spellings present (`color`, `organization`, `license` as noun) |
| Date format | Anything other than `Mon YYYY` |

### Layer 2 — ATS round-trip (the highest-value test in the whole system)

**Generate → parse with a real résumé parser → diff the parsed record against the
structured object we generated from.**

This directly tests the thing that actually kills applications, and nothing else
does. If the parser cannot recover name, email, phone, employers, titles and
dates, the document fails — regardless of how good it looks. Run against at
least two independent open-source parsers so the result is not one library's
quirk.

Threshold: **100% recovery** of the six fields recruiters look at (F-C). Anything
less is a defect, not a warning.

### Layer 3 — LLM-as-judge on quality (with F-F mitigations)

Rubric, scored pairwise against a reference document for the same posting:
1. Does it answer what *this* posting asks for?
2. Is the strongest relevant evidence in the first third?
3. For Track B — is the bridge honest, specific and confident, with no claim of
   experience not held?
4. Would this read as written by a person for this job, or as template output?
5. Are the screening questions answered directly?

Position randomised, both orders run, judge distinct from generator.

### Layer 4 — Human calibration and the real signal

- **Golden set:** 20 real postings captured from the spikes — 15 from the LMIA
  queue spanning farm, greenhouse, food, caregiving and labouring, 5 developer
  roles from the international queue. Frozen, version-controlled, re-run on
  every change.
- **Gedeon rates 20 documents once**, before any auto-send. That is the calibration
  set; kappa against the judge is tracked from then on.
- **The only outcome that matters is reply rate**, tracked per template version.
  Layers 1–3 are proxies. When enough replies exist to compare template versions,
  the proxies get re-tuned against them.

### Regression discipline

Every prompt or template change re-runs the golden set. Layer 1 and 2 must be
100%. Layer 3 must not regress against the previous version. Results are
committed, so the effect of every change on document quality is in git history
rather than in someone's memory.

---

## Consolidated changes to `docs/03` and `docs/04`

1. **DOCX primary, PDF companion.** Reverses the current rendering design.
2. **Native DOCX generation** via `python-docx` from the structured object.
3. **Layout spec driven by F-C** — the six fields get visual priority; bullets
   not prose; single column; no headers/footers.
4. **Specificity budget** as an enforced check, and AI-genericness phrases added
   to the banned list.
5. **Structural variation** required across cover letters.
6. **Screening-question answering** promoted to a hard requirement.
7. **Claim-level entailment** with span-level output, verifier context-isolated.
8. **Four-layer evaluation harness**, with the ATS round-trip as the centrepiece.
9. **Golden set of 20 real postings**, frozen and version-controlled.

---

## Sources

- [DEV — Why 75% of resumes fail ATS screening: technical analysis of parsing systems](https://dev.to/vicente_sansilvestrecha/why-75-of-resumes-fail-ats-screening-a-technical-analysis-of-resume-parsing-systems-1hmg)
- [QuickCV — I tested 8 ATS systems to see how they actually parse resumes](https://quickcv.io/blog/i-tested-8-ats-systems-to-see-how-they-actually-parse-resumes)
- [Resume Optimizer Pro — PDF vs DOCX resume: why PDF fails ATS parsing (2026 data)](https://resumeoptimizerpro.com/blog/why-not-to-use-pdf)
- [Applicant Tracking Software — Why some resumes won't parse](https://support.applicant-tracking.com/support/solutions/articles/3000128879-why-some-resumes-won-t-parse)
- [TheLadders — Eye-tracking study (PDF, full methodology)](https://www.theladders.com/static/images/basicSite/pdfs/TheLadders-EyeTracking-StudyC2.pdf)
- [HR Dive — Eye tracking study shows recruiters look at resumes for 7 seconds](https://www.hrdive.com/news/eye-tracking-study-shows-recruiters-look-at-resumes-for-7-seconds/541582/)
- [PR Newswire — Ladders updates recruiter eye-tracking study](https://www.prnewswire.com/news-releases/ladders-updates-popular-recruiter-eye-tracking-study-with-new-key-insights-on-how-job-seekers-can-improve-their-resumes-300744217.html)
- [Springer — Hallucination to truth: a review of fact-checking and factuality evaluation in LLMs](https://link.springer.com/article/10.1007/s10462-025-11454-w)
- [arXiv — FactSelfCheck: fact-level black-box hallucination detection](https://arxiv.org/pdf/2503.17229)
- [arXiv — HalluciNot: hallucination detection through context and common knowledge verification](https://arxiv.org/pdf/2504.07069)
- [arXiv — Beyond document grounding: span-level hallucination detection](https://arxiv.org/pdf/2607.00895)
- [Evidently AI — LLM-as-a-judge: a complete guide](https://www.evidentlyai.com/llm-guide/llm-as-a-judge)
- [DeepEval — LLM-as-a-judge in 2026: techniques and best practices](https://deepeval.com/blog/llm-as-a-judge)
- [Future AGI — LLM-as-judge best practices 2026: calibration, bias and cost](https://futureagi.com/blog/llm-as-judge-best-practices-2026)
- [arXiv — Leveraging LLMs as meta-judges: a multi-agent framework](https://arxiv.org/pdf/2504.17087)
- [WasItAIGenerated — AI detection in hiring: screening AI-written resumes and cover letters 2026](https://www.wasitaigenerated.com/research/ai-detection-hiring-recruitment)
- [Detection Drama — AI detection in hiring: 2026 statistics](https://detectiondrama.com/ai-detection-in-hiring-statistics/)
- [ResuFit — Can recruiters tell if you used AI on your resume?](https://resufit.com/blog/can-recruiters-tell-if-you-used-ai-to-write-your-resume/)
