# 08 — Canadian CV specification

The definitive format spec for every document this system generates. Researched
2026-08-02. **Supersedes `docs/00` F11**, which rested on résumé-builder marketing
pages and was graded C.

This is written as a build specification: rules are testable, and each one names
the reason it exists. Where sources conflict, that is stated rather than resolved
silently.

Two audiences, and they want different documents:

- **Track A — international queue, developer roles.** Professional CV, ATS-first.
- **Track B — LMIA queue, ~70% agriculture / food / caregiving / trades.**
  A different document with different priorities. Most "Canadian résumé" advice
  online is written for office jobs and is **actively wrong** for this track.

---

## Part 1 — Hard rules (apply to both tracks)

### 1.1 What must NEVER appear

Canadian human-rights legislation prohibits discrimination on these grounds, so
including them creates legal exposure for the employer and gets applications
discarded rather than helping:

| Never include | Why |
|---|---|
| Photograph | Creates bias-claim exposure; non-standard in Canada |
| Date of birth / age | Prohibited ground |
| Marital status | Prohibited ground |
| Nationality / citizenship | Prohibited ground |
| Religion | Prohibited ground |
| Gender | Prohibited ground |
| Social Insurance Number | Identity-theft risk; never requested pre-hire |
| Passport / ID / RSA ID number | Same |
| Full street address | Not needed; see 1.3 |
| **Work-permit or visa status** | **See 1.2 — this one is counter-intuitive** |
| References / referee contact details | Canadian convention omits them; also `docs/06` D-referees |
| "References available upon request" | Treated as filler |
| Health status, disabilities | Prohibited ground |
| Salary history / expectations | Not a résumé element in Canada |

**Enforcement:** deterministic check, Layer 1 (`docs/07`). Any hit → reject.

### 1.2 Work-permit status belongs in the COVER LETTER, not the CV

**This corrects `docs/04`**, which specified a line near the top of the CV
reading *"Seeking an LMIA-supported position; available to relocate to Canada."*
That is the wrong document.

Canadian guidance is consistent: immigration status is not a résumé element.
Employers are expected to assess on skills and experience; putting status in the
header invites the reader to filter on it before reading anything else, and it
sits alongside exactly the personal characteristics that must not appear.

**The cover letter is the right place** — one calm, factual sentence. It gets
read by a human who has already seen the qualifications.

**Grade: B.** Consistent across newcomer-focused Canadian sources. Note the
genuine tension: for *this* system the entire point is sponsorship, and an
employer who will not sponsor is wasted effort on both sides. The resolution is
sequencing, not concealment — the CV earns the read, the cover letter's opening
paragraph states the position plainly. Nothing is hidden; it is one paragraph
later.

### 1.3 Contact block — exact specification

```
Gedeon Christ Nzemba
Cape Town, South Africa
+27 83 253 2615  |  gedeon@gedeonchrist.com
linkedin.com/in/nzemba  |  gedeonchrist.com
```

- **City and country only.** No street address, no postal code. Canadian
  convention is city + province; for an overseas applicant, city + country.
- **Phone in full international format**, `+27 …`. A Canadian employer must be
  able to dial it without working out a country code.
- **Body text, first block on page one.** Never a header or footer — many ATS
  parsers never read that region and the application arrives anonymous
  (`docs/07` F-B). Hard-enforced.
- LinkedIn only if it matches the CV (`docs/06`).
- No icons — they are images, and images break parsers.

### 1.4 Language and mechanics

- **Canadian English throughout:** colour, behaviour, favour, centre, metre,
  organisation, recognise, licence (noun) / license (verb), programme, travelled,
  cancelled, enrolled, labour, neighbour.
- **Employment dates: `Mon YYYY – Mon YYYY`**, `Present` for current.
  *Conflict noted:* one source claims Canadian résumés use `DD/MM/YYYY`. That
  reflects general Canadian date-writing (itself inconsistent — government
  standard is ISO `YYYY-MM-DD`). For **employment dates** on a résumé,
  `Mon YYYY` is the convention and is unambiguous to both humans and parsers.
  Use it, and never mix formats within a document.
- **Metric units** where measurements appear — kg, cm, km, °C. Relevant for
  Track B: lifting capacities are quoted in kg or lb by employers; mirror
  whatever the posting uses.
- Spell out month names. `Sept 2023` vs `September 2023` inconsistency is a
  documented parser failure mode (`docs/07`).

### 1.5 Length

- **Track A: 2 pages.** One page under-sells seven years plus a six-and-a-half
  year freelance practice.
- **Track B: 1 page, firmly.** A farm or warehouse employer scanning fifty
  applications does not read page two. Everything that matters fits.
- Never 3 pages. That is a European CV convention and reads as not understanding
  the market.

---

## Part 2 — Layout specification

Driven by the eye-tracking finding in `docs/07` F-C: **7.4-second initial screen,
~80% of it on six fields**, F-pattern reading.

### 2.1 Structural constraints (ATS survival)

| Rule | Reason |
|---|---|
| Single column, always | Multi-column is the top parser-failure cause; also scored worst in eye-tracking |
| No tables | Parsers flatten or drop cell contents |
| No text boxes | Frequently invisible to parsers |
| No images, logos, icons, charts | Not parseable; often stripped |
| No headers or footers | Region often unread (F-B) |
| No columns for dates — use inline text | Tabbed/tabled date columns break parsing |
| Standard section headings only | Parsers pattern-match on them |
| One font, 2–3 sizes | Rendering consistency |
| 10–12 pt body | Legibility |
| Left-aligned, ragged right | Justified text creates irregular spacing that harms parsing |
| Bullets: `•` or `-` only | Exotic glyphs become mojibake |

**Permitted section headings** — parsers look for these strings:
`Professional Summary` · `Summary` · `Work Experience` · `Experience` ·
`Employment History` · `Education` · `Skills` · `Technical Skills` ·
`Certifications` · `Licences and Certifications` · `Languages` · `Projects` ·
`Awards`

Never: "My Journey", "What I Bring", "About Me", "Career Highlights" as a
replacement for Work Experience.

### 2.2 Entry format — exact

```
Front End Engineer                                    Sep 2022 – Dec 2025
Kurtosys Systems — Cape Town, South Africa            Full-time
```

Title first and bold (it is the field recruiters fixate on), employer on the
following line, dates right-aligned via tab stop **not** a table, employment type
present on every entry (`docs/06` — this is what makes concurrent roles read as
normal).

Then bullets. **Never prose paragraphs in the experience section.**

### 2.3 Bullet construction

`[Action verb] + [what] + [context/scale] + [outcome where genuinely known]`

- Past tense for past roles, present for current.
- Start with a verb. Never "Responsible for…", never "Duties included…".
- **Quantify only what is real.** `master-profile.yaml` has genuine numbers —
  150-user network, 3 yr 4 mo, 6 yr 7 mo, R20,000 prize, team of three. Invented
  metrics fail the entailment check (`docs/04`).
- 1–2 lines each. A bullet running to four lines is a paragraph wearing a bullet.
- 3–6 bullets for recent/relevant roles, 1–3 for older ones.

### 2.4 Section order

**Track A (developer):**
1. Contact block
2. Professional Summary — 3–4 lines
3. Technical Skills — mirroring the posting's vocabulary
4. Work Experience — reverse-chronological
5. Projects / Portfolio — 3–4 links max, chosen for the posting
6. Education — including the ICAS assessment
7. Languages

**Track B (general work):** *deliberately different*
1. Contact block
2. Summary — 2–3 lines, plain language
3. **Relevant Experience** — the general work, in full detail
4. **Skills** — practical and physical first
5. **Additional Experience** — professional work, compressed to 2–3 lines
6. Education & Training — Northlink N1–N2–N4 leads for trades roles
7. Languages
8. Availability

Rationale for Track B's ordering: a farm or food employer reading in seven
seconds must hit relevant physical experience immediately. Leading with
"Front-End Engineer at a FinTech company" tells them within one second that this
is the wrong applicant. The software career is not hidden — it appears under
*Additional Experience*, where it reads as context rather than as a mismatch.

---

## Part 3 — Applying from outside Canada

### 3.1 Credential equivalency — state it explicitly

Canadian employers know what an ECA is; most overseas applicants never mention
one. The recommended pattern is to state the Canadian equivalency directly.

For Gedeon:

```
National Senior Certificate — Noorder Paarl High School, South Africa (2016)
Assessed by ICAS (International Credential Assessment Service of Canada) as
equivalent to Canadian Secondary School Graduation. File 24080341 IMM, March 2025.
```

This does real work on both tracks. On Track B it is close to the strongest
education line available — it tells a Canadian employer, in their own frame of
reference, exactly what the qualification is worth, with a verifiable file
number.

**Note:** the ICAS report covers only the secondary certificate. The IT Academy
and Shaw Academy study is unassessed and must be presented as study, never as
an assessed equivalency.

### 3.2 Foreign employers need context

A Canadian reader has no idea what Kurtosys, UCOOK, Polarama or Cumpsty
Electrical are. One clause fixes it:

- `Kurtosys Systems — FinTech / asset-management technology, Cape Town`
- `UCOOK — food-technology e-commerce platform, Cape Town`
- `Polarama — wholesale distribution`
- `Cumpsty Electrical — residential estate electrical contractor, Paarl`

### 3.3 Job titles must be translated, not transcribed

Foreign titles map to the nearest **NOC 2021** equivalent, with the NOC code
stated. It is the vocabulary Canadian employers and the LMIA process both use,
and citing it signals the applicant understands the system.

| As held | Rendered |
|---|---|
| Front End Engineer | Front-End Developer (NOC 21234) |
| IT Support Technician & Media Officer | IT Support Technician (NOC 22220) |
| General Electrical Assistant | Electrician's Helper / Construction Labourer (NOC 75110) |
| Packer | Warehouse Worker / Order Packer (NOC 75101) |
| Kitchen / Food Production Crew | Food Service / Kitchen Helper (NOC 65201) |

Render as `Original Title (Canadian equivalent, NOC 21234)` where they differ
materially — never silently substitute a title he did not hold.

### 3.4 Remote-work evidence is the single best counter-argument

The employer's real doubt about an overseas applicant is *"can this person
actually function in our organisation from a distance, and will they arrive?"*

Gedeon's profile answers the first directly: **DataBalk is a Netherlands company,
worked remotely, currently.** Plus documented client work across the US, Canada,
UK and Netherlands at Kurtosys — including **BMO, a Canadian bank**.

Lead with this on Track A. It is not a claim about willingness; it is evidence of
the thing already happening.

---

## Part 4 — Track B: what agricultural and general-labour employers actually want

Most Canadian résumé advice is written for office roles. **~70% of the LMIA queue
is agriculture, food, caregiving and trades**, and those employers weight
differently.

What they look for, in their order:

1. **Previous hands-on experience** — the single biggest factor. The concern is
   specific and practical: people unused to manual labour often do not last.
   Anything demonstrating sustained physical work matters more than any
   qualification.
2. **Physical capability and stamina** — long hours, repetitive tasks, standing,
   lifting, outdoor conditions.
3. **Reliability and returning** — being asked back is powerful evidence.
4. **Safety awareness** — PPE, working at height, site discipline.
5. **English ability** — explicitly required in agricultural postings.
6. **Availability** — start date, shift/weekend/on-call willingness. Frequently
   the actual screening question (`docs/07`).
7. **Teamwork** — small crews, close quarters.

**How Gedeon's documented history maps** — every one traceable to
`master-profile.yaml`:

| What they want | Evidence |
|---|---|
| Sustained physical work | Cumpsty Electrical ~18 months on estate construction sites; roof painting on multi-storey buildings |
| Working at height / PPE | Painter — full fall-arrest harness, multi-storey |
| Food production, hygiene standards | McDonald's kitchen / food production 2019–2020 |
| Accuracy under time pressure | Polarama — second-count verification against supervisor |
| Being asked back | Polarama promotion during placement |
| Standing shift work | SpeedTrainer — full standing shifts, entrance control |
| Manual tools / excavation | Cumpsty — wall chasing, trenching, site prep |
| Teamwork in small crews | Painting crew; Cumpsty under supervising electrician |
| Technical grounding | Northlink N1–N2–N4 Mechanical Engineering |
| Languages | French (native), English, Lingala, Kituba, Afrikaans |

**Track B tone:** plain, concrete, unembellished. These employers are not reading
for polish; corporate résumé-speak reads as a poor fit. Short sentences. Real
nouns — harness, trench, conduit, pallet, shift.

**What Track B must NOT do:**
- Lead with software.
- Claim certifications he does not hold (WHMIS, fall-arrest, forklift, first aid).
  State willingness to obtain them — that is honest and it is what employers
  expect of an overseas hire.
- Use the software career apologetically. It appears as *Additional Experience*,
  stated plainly, no excuse attached.

---

## Part 5 — Cover letter specification

Canadian convention: one page, four paragraphs, business-letter form. Addressed
to a named person where the posting gives one.

**Paragraph 1 — the role and one specific thing about this employer.**
Named role, where seen. One concrete detail drawn from *this* posting. Never
"I am writing to express my interest" (`docs/07` banned list).

**Paragraph 2 — the strongest matching evidence.** Two or three cited specifics.
Track B answers the screening questions *here*, explicitly — ~30% of postings ask
them and most applicants ignore them.

**Paragraph 3 — the honest bridge (Track B) or the depth argument (Track A).**
Per `docs/04`.

**Paragraph 4 — work authorisation, stated plainly.**

> "I am currently in Cape Town, South Africa and would require a work permit
> supported by an LMIA. I hold an ICAS educational credential assessment for
> Canada, my passport is current, and I can relocate on your timeline."

### 5.1 Understand what you are asking the employer to do

Worth knowing, because it changes the register. Sponsoring costs the employer
**$1,000 per position, non-refundable even if refused**, plus **eight consecutive
weeks of advertising** before they may even apply, plus compliance exposure —
and TFWP compliance penalties were **doubled in July 2026**.

So the employer is being asked for real money, months of delay and audit risk.
The letter should read as though the applicant knows that.

**The honest counter-argument, and it is genuinely strong:** temporary foreign
workers frequently show *better* retention than local hires, because permanent
residence through Express Entry or a provincial nomination depends on continuous
employment. The incentive to stay is structural.

Say it plainly, once, without overclaiming:

> "I understand an LMIA is a significant commitment of cost and time. I am
> applying because I intend to build a long-term future in Canada, and staying
> with the employer who makes that possible is directly in my own interest."

**Never** offer to pay any part of the LMIA cost. Recovering it from a worker is
**illegal**, and offering marks the applicant as either uninformed or a
compliance risk.

---

## Part 6 — Corrections to existing documents

| Document | Change |
|---|---|
| `docs/00` F11 | **Superseded by this file.** Grade-C sourcing replaced. |
| `docs/04` | **Work-permit line removed from the CV** and moved to cover letter paragraph 4. Was: a line near the top of the CV. |
| `docs/04` | Track B section order revised — *Relevant Experience* before *Additional Experience*, education positioned for trades. |
| `docs/04` | Employer context clauses now required for all foreign employers. |
| `docs/04` | ICAS equivalency rendering specified verbatim. |
| `docs/04` | Track A = 2 pages, Track B = 1 page. Was "1–2 pages" for both. |
| `docs/07` | Layer 1 checks extended — see below. |

### New Layer 1 deterministic checks

- No street address, no postal code
- No work-permit or visa language anywhere in the **CV** (cover letter only)
- Phone in `+CC` international format
- Every foreign employer carries a context clause
- Every role carries an employment type
- Section headings drawn only from the permitted list
- Track B: no software content above the *Additional Experience* section
- Track B: 1 page. Track A: ≤ 2 pages
- Metric units where measurements appear
- Consistent date format, months spelled out
- No claimed certification absent from `master-profile.yaml`

---

## Sources

- [CanadaVisa — How to write a Canadian style resume as a newcomer](https://www.canadavisa.com/resume.html)
- [CanadaVisa — Canada employment resume guide for international workers](https://www.canadavisa.com/canadian-employment-resume.html)
- [George Brown College — Adapting your international resume (PDF)](https://www.georgebrown.ca/media/adapting-your-international-resume-pdf)
- [RBC — Newcomer's guide to finding a job in Canada (PDF)](https://www.rbc.com/newcomers/_assets-custom/pdf/Finding-a-Job-Guide-for-Newcomers.pdf)
- [WelcomeAide — Resume and cover letter guide for newcomers to Canada](https://welcomeaide.com/en/blog/resume-cover-letter-guide-newcomers-canada)
- [Moving2Canada — How to format your resume for Canada's employers](https://moving2canada.com/work/finding-jobs/career-resources/resume-format-in-canada/)
- [Immigration.ca — Guide to getting your credentials recognised](https://immigration.ca/guide-to-getting-your-credentials-recognised-as-an-immigrant-to-canada/)
- [Government of Canada — Employer's roadmap to hiring and retaining internationally trained workers](https://www.canada.ca/en/immigration-refugees-citizenship/corporate/publications-manuals/employer-roadmap-hiring-retaining-internationally-trained-workers.html)
- [Government of Canada — Employer-specific work permits: eligibility, LMIA](https://www.canada.ca/en/immigration-refugees-citizenship/services/work-canada/employer-specific.html)
- [Government of Canada — TFWP compliance penalties doubled, July 2026](https://www.canada.ca/en/employment-social-development/news/2026/07/the-government-of-canada-highlights-doubling-of-compliance-monetary-penalties-under-the-temporary-foreign-worker-program.html)
- [Indeed Canada — General farm worker job description](https://ca.indeed.com/hire/job-description/general-farm-worker)
- [Crossing Oceans — Temporary foreign worker retention rates](https://www.crossingoceansimmigration.com/post/temporary-foreign-worker-retention-rates-why-international-hires-stay-longer-than-you-think)
- [Can X Global — LMIA fees and costs in Canada 2026](https://canxglobal.com/lmia-fees-costs-canada-2026-2/)
- [ResumesCanada — EU CV vs North American resume](https://www.resumescanada.ca/eu-cv-vs-north-american-resume-what-really-matters-for-job-applications/)
- [Novoresume — Canadian resume format, tips and examples](https://novoresume.com/career-blog/canada-resume-format)
