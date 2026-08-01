# 00 — Research findings

Researched on **1 August 2026** against live sources rather than recalled from
training data. Where sources disagree, that is stated rather than resolved
silently.

> ## ⚠ Read this before trusting anything below
>
> **No primary source in this document was fetched directly.** The container this
> research ran in blocks outbound HTTPS to `canada.ca`, `jobbank.gc.ca`,
> `open.canada.ca` and `noc.esdc.gc.ca` at the network-policy layer (`CONNECT` →
> 403). Everything here came through a search engine's extracts of those pages.
>
> An earlier version of this file was headed "verified live, not recalled" and
> written in flat declarative prose. That oversold it. Search extracts of a page
> are better than memory and worse than the page.
>
> Every finding is now graded:
>
> | Grade | Meaning |
> |---|---|
> | **A** | Multiple independent sources with reputational stakes (law firms, established immigration press) agreeing |
> | **B** | Single credible secondary source, or an official page seen only through search extract |
> | **C** | Commercial content with an interest in the claim — **treat as a lead, not a fact** |
>
> Anything driving an architectural decision should be re-read from the primary
> URL on a normal connection before code depends on it. `spikes/` exists to do
> exactly this for the two findings that matter most.

---

## F1 — Job Bank's Terms of Use prohibit automated access *(via search)*

Job Bank's Terms of Use — in both the employer and job-seeker versions — prohibit
using "any script, robot, spider, Web crawler, screen scraper, automated query
program, artificial intelligence or other automated device, software, or process"
to access the service.

- <https://www.jobbank.gc.ca/termsofuse-employer.xhtml>
- <https://www.jobbank.gc.ca/reg/indregistertermsofuse>

**This is the single most important constraint on the project.** It does not make
the project impossible, but it decides the architecture: see `docs/02-legal-compliance.md`.

## F2 — There are two *sanctioned* data channels that most people miss

1. **Open data — Job Bank postings.** "Job Postings Advertised on Canada's National
   Job Bank Website" is published as monthly CSV on the Open Government Portal
   under the Open Government Licence – Canada. It carries job title, NOC 2021 and
   NAICS codes, work location, number of vacancies, salary and benefits, hours,
   requirements and employment terms. Files exist through at least January 2026.
   <https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072>
   *Limitation: monthly cadence, and it does not appear to include the employer's
   apply-to email address.*

2. **Job Bank XML feed.** Job Bank operates a partner programme that gives job
   boards an XML feed of postings, filterable by location, industry and other
   criteria. Access is by request.
   <https://www.jobbank.gc.ca/network>
   *This is the correct long-term answer for the discovery layer and should be
   applied for in week 1 — it converts the riskiest part of the system into a
   sanctioned integration.*

3. **TFWP Positive LMIA Employers List.** Quarterly open dataset of employers
   issued a positive LMIA, broken out by program stream, NOC 2021 and business
   location. Data through 2025Q3 is published.
   <https://open.canada.ca/data/en/dataset/90fed587-1364-4f33-a9ee-208181dc0b97>
   *This is a cross-check, not a job feed — it is historical and excludes
   employers whose business name is a personal name. Its real value is
   **corroboration**: an employer that appears here has genuinely obtained an
   LMIA before, which is a strong signal of willingness and capability to do it
   again.*

## F3 — Job Bank application methods

Employers choose one of: by mail, in person, by telephone, **by email**, by fax,
online, or Direct Apply through Job Bank. The address is revealed to the job
seeker by clicking **"Show how to apply"** on the posting.
<https://www.jobbank.gc.ca/support/question?qaid=15&tid=87>

Direct Apply requires a Job Bank **Plus account** for the job seeker. Note that
creating an account means *accepting* the Terms of Use in F1, which materially
worsens the legal position for automation (see `docs/02-legal-compliance.md`).

Job Bank also runs dedicated entry points for exactly this use case:
- <https://www.jobbank.gc.ca/findajob/foreign-candidates> — employers recruiting
  candidates from outside Canada
- <https://www.jobbank.gc.ca/temporary-foreign-workers> — employers who have
  obtained or applied for an LMIA

## F4 — Arranged employment CRS points were removed on 25 March 2025

IRCC removed all additional CRS points for a valid job offer, LMIA-backed or not,
via Ministerial Instructions effective **25 March 2025**. Points already awarded
to candidates in the pool were stripped and scores recalculated; candidates who
already held an ITA were unaffected. The stated reason was fraud — investigations
found LMIA-backed job-offer letters being sold for $20,000–$75,000.

- <https://www.cicnews.com/2025/03/breaking-canada-removes-bonus-crs-points-for-arranged-employment-from-express-entry-0353251.html>
- <https://gands.com/no-more-crs-points-for-arranged-employment-under-express-entry/>
- <https://cila.co/removal-of-express-entry-job-offer-points-the-good-the-bad-and-the-ugly/>

**Sources conflict** on whether a residual 50 points survives for NOC TEER 0
(senior management). One 2026 secondary source describes exactly that; the
primary announcements describe a complete removal. **Do not rely on either
reading** — it does not affect Gedeon (TEER 1) and should be confirmed with IRCC
directly if it ever becomes relevant.

IRCC's 2026–27 Departmental Plan signals a possible *return* of job-offer points
limited to high-wage and regulated occupations. Unconfirmed, and not a basis for
planning.

## F5 — TFWP / LMIA conditions in 2026 are materially tighter

| Change | Effective | Source |
|---|---|---|
| TFWP admissions target cut to 60,000 — down 27% from 82,000 in 2025 | 2026 | <https://ircc.com/news/tfw-program-cuts-2026-what-employers-need-to-know> |
| Low-wage LMIAs **not processed** in census metropolitan areas with unemployment ≥ 6%, reassessed quarterly | in force | <https://www.visaverge.com/news/canada-tightens-lmia-rules-for-low-wage-stream-in-temporary-foreign-worker-program/> |
| Low-wage applicants must advertise the role for 8 consecutive weeks in the 3 months before applying, and must show recruitment efforts aimed at youth | 1 Apr 2026 | <https://mathewsdinsdale.com/new-program-requirements-for-lmias-effective-april-1-2026/> |
| Rural employers may raise the low-wage TFW share from 10% to 15% | 1 Apr 2026 | same |
| New wage thresholds = provincial/territorial median hourly wage **+ 20%** | 17 Jul 2026 | <https://immigration.ca/new-canada-lmia-wage-thresholds-take-effect/> |

**Consequence for strategy:** the squeeze lands almost entirely on the *low-wage*
stream — which is precisely where painter, security-guard, retail and general-labourer
applications sit. The *high-wage* stream, where a TEER 1 web developer sits, is far
less restricted. This does not mean stop applying broadly; it means the expected
value per application is very unevenly distributed. See `docs/01-immigration-strategy.md`.

## F6 — French-language Express Entry rounds are the widest-open door in 2026

| Round type | 2026 CRS cut-offs |
|---|---|
| French-language category | **379 – 446** (lowest recorded 399 on 22 Jul 2026, 5,000 ITAs) |
| General | ~514 – 525 |

Qualifying requires **NCLC 7** in all four skills on an approved test (TEF Canada
or TCF Canada). Meeting NCLC 7 in French *and* CLB 5 in English also adds a
**+50 CRS** bonus.

- <https://www.cicnews.com/2026/07/french-language-express-entry-draw-sees-crs-cutoff-dip-below-400-0778376.html>
- <https://immigration.ca/canada-invites-5000-french-speaking-candidates-express-entry-crs-399-july-22-2026/>
- <https://jcalaw.ca/french-language-proficiency-express-entry-guide/>

Gedeon's home language is French (recorded Excellent/Excellent/Excellent on his
own earlier CV). **This is the highest-leverage fact discovered in this entire
research pass.**

## F7 — NOC 2021 mapping for the primary occupation

**NOC 21234 — Web developers and programmers**, TEER 1.
Hierarchy: 2 (Natural and applied sciences) → 21 → 212 → 2123 (Computer, software
and Web designers and developers).
<https://noc.esdc.gc.ca/Structure/NOCProfile?code=21234&version=2021.0>

TEER 1 means the occupation normally requires a university degree *or* several
years of accumulated experience and expertise in a related TEER 2 occupation.
Gedeon qualifies through the experience route, not the degree route — which is
explicitly provided for, but must be *argued* on the CV rather than assumed.

## F8 — Email deliverability limits are a hard engineering constraint

- Personal Gmail: 500 recipients/day. Google Workspace: 2,000/day. Recipients are
  counted, not messages.
- Practitioner guidance for cold outreach is **~25 per inbox per day** — an order
  of magnitude below the formal cap — because the formal cap is not what triggers
  suspension; reputation is.
- Google/Yahoo bulk-sender rules (in force since Feb 2024, enforcement tightened
  since): SPF **and** DKIM, DMARC alignment with at least `p=none`, spam-complaint
  rate under 0.1%, one-click unsubscribe for bulk mail.
- <https://support.google.com/a/answer/14229414>
- <https://www.gmass.co/blog/gmail-bulk-sender-guidelines/>

**Consequence:** sending job applications from `nzemba48@gmail.com` at volume will
get the account rate-limited and then suspended, and Gedeon would lose his primary
mailbox mid-campaign. The system must send from an authenticated own-domain
mailbox (`gedeonchrist.com`) with SPF/DKIM/DMARC, and must throttle to a
human-plausible daily volume.

## F9 — Scraping case law: the distinction that matters is logged-in vs logged-out

- *hiQ Labs v. LinkedIn* (9th Cir. 2022): scraping **public** pages is not
  unauthorised access under the CFAA. But hiQ was found to have breached
  LinkedIn's User Agreement — which it had accepted **by creating accounts** — and
  the case ended in a consent judgment.
- *Meta v. Bright Data* (N.D. Cal., Jan 2024): summary judgment for Bright Data —
  Meta's terms bound **logged-in** scraping only, not logged-off collection of
  public content.

The line that emerges: *logged-out collection of public data is defensible;
logged-in collection against terms you accepted is not.* Volume still matters
independently (trespass-to-chattels theories survive at extreme request rates).

- <https://iswebscrapinglegal.com/blog/web-scraping-case-law/>

This is US case law and is **persuasive, not binding, in Canada**. It is a guide
to designing something defensible, not a licence.

## F10 — CASL almost certainly does not restrict a personal job application

CASL governs **commercial electronic messages** — messages encouraging
participation in a commercial activity. An individual sending his own CV to an
employer is not that. And even on the conservative reading where it were:

- **Conspicuous publication** gives implied consent where (a) the recipient
  published the address publicly, (b) without a statement refusing unsolicited
  messages, and (c) the message is relevant to that person's business role. An
  employer who publishes an "apply to this address" email on a public job posting
  satisfies all three.
- <https://crtc.gc.ca/eng/com500/faq500.htm>

**Consequence:** the risk here is not legal, it is *reputational* — an obviously
mass-produced application harms Gedeon far more than any regulator would. Design
accordingly: one-to-one messages, real reply-to, no tracking pixels, no
unsubscribe footer (which would itself signal bulk mail).

## F11 — Canadian CV conventions (2026) — **grade C, and that matters**

Every source found for this finding is a **résumé-builder or CV-writing service** —
companies whose product is sold by convincing you your CV will fail without them.
That is the weakest evidence class in this document, and it is currently
load-bearing for the entire template design in `docs/04-cv-engine.md`.

**Struck from the plan:** an earlier version of this file stated *"~75%+ of
Canadian employers screen through an ATS"* and used it to justify format
decisions. The only sources for that figure are résumé-tool marketing pages with a
direct commercial interest in it being alarming. **It has been removed.** No
architectural claim should rest on it.

The conventions themselves are almost certainly right — they are consistent across
sources, they match Canadian human-rights law, and they cost nothing to follow:

- 1–2 pages, reverse-chronological.
- **No photo, no date of birth, no age, no marital status, no nationality, no ID
  number, no gender.** This one is *not* grade C — it follows directly from
  Canadian human-rights legislation on prohibited grounds of discrimination, and
  including such details puts the employer in an awkward position.
- Canadian English spelling: *colour, behaviour, centre, organisation, licence*.
- Standard section headings; no tables, text boxes, columns or images.
- **Mirror the posting's exact vocabulary** — if it says "WHMIS 2015", write
  "WHMIS 2015".
- Newcomers: map job titles to the nearest **NOC 2021** equivalent and cite the
  credential evaluation (WES / ICAS / IQAS / ICES) explicitly.

**The honest position:** ATS parsing behaviour is not verified, and the specific
prevalence is unknown. But single-column plain formatting is free, costs nothing
if no ATS is involved, and is strictly safer if one is — so the design stands on
*asymmetric downside*, not on a statistic. That is a legitimate reason to keep it
and an illegitimate reason to claim it is evidence-based.

Sources (all grade C): <https://resumefy.ca/blog/how-to-write-canadian-resume>,
<https://www.resumemate.io/blog/canada-resume-format-differences-from-us-templates/>,
<https://tailormycv.app/canada/resume-format>

---

## Grade summary

| Finding | Grade | Note |
|---|---|---|
| F1 Job Bank ToU prohibits automated access | **B** | Never read on the page itself. Drives `docs/02` — worth reading directly. |
| F2 Open data + XML feed + LMIA employer list exist | **B** | Existence is solid; **contents are unverified** — `spikes/02` checks this. |
| F3 Job Bank application methods / "Show how to apply" | **B→A** | Corroborated directly by Gedeon, who uses the site. `spikes/01` settles the mechanics. |
| F4 Arranged-employment CRS points removed 25 Mar 2025 | **A** | Multiple law firms and immigration press. One residual disagreement noted in-line. |
| F5 TFWP 2026 conditions | **A** | Law-firm and trade-press coverage agreeing on dates and thresholds. |
| F6 French-language draw cut-offs | **A** | Multiple sources, specific draw dates and numbers. |
| F7 NOC 21234 / TEER 1 | **B** | Structural fact, low risk of being wrong. |
| F8 Email sending limits | **B** | Google's own docs plus practitioner consensus; the ~25/day figure is folklore-grade but conservative in the safe direction. |
| F9 Scraping case law | **B** | US law, **persuasive only in Canada**. Not a licence. |
| F10 CASL | **B** | CRTC guidance via extract. Reasoning is sound; not legal advice. |
| F11 Canadian CV conventions | **C** | See above. Kept on asymmetric-downside grounds, not evidence. |

---

## Sources

- [Job Bank — Terms of Use (Employers)](https://www.jobbank.gc.ca/termsofuse-employer.xhtml)
- [Job Bank — Terms of Use (Job seekers)](https://www.jobbank.gc.ca/reg/indregistertermsofuse)
- [Job Bank — Our network (XML feed)](https://www.jobbank.gc.ca/network)
- [Job Bank — Foreign candidates from outside Canada](https://www.jobbank.gc.ca/findajob/foreign-candidates)
- [Job Bank — Temporary Foreign Workers](https://www.jobbank.gc.ca/temporary-foreign-workers)
- [Job Bank — How can I apply to a job posting?](https://www.jobbank.gc.ca/support/question?qaid=15&tid=87)
- [Open Government — Job Postings Advertised on Canada's National Job Bank Website](https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072)
- [Open Government — TFWP Positive LMIA Employers List](https://open.canada.ca/data/en/dataset/90fed587-1364-4f33-a9ee-208181dc0b97)
- [CIC News — Canada removes bonus CRS points for arranged employment](https://www.cicnews.com/2025/03/breaking-canada-removes-bonus-crs-points-for-arranged-employment-from-express-entry-0353251.html)
- [Green & Spiegel — No more CRS points for arranged employment](https://gands.com/no-more-crs-points-for-arranged-employment-under-express-entry/)
- [CILA — Removal of Express Entry job offer points](https://cila.co/removal-of-express-entry-job-offer-points-the-good-the-bad-and-the-ugly/)
- [Mathews Dinsdale — New program requirements for LMIAs effective April 1, 2026](https://mathewsdinsdale.com/new-program-requirements-for-lmias-effective-april-1-2026/)
- [Immigration.ca — New Canada LMIA wage thresholds from July 17, 2026](https://immigration.ca/new-canada-lmia-wage-thresholds-take-effect/)
- [VisaVerge — Canada tightens LMIA rules for the low-wage stream](https://www.visaverge.com/news/canada-tightens-lmia-rules-for-low-wage-stream-in-temporary-foreign-worker-program/)
- [CIC News — French-language Express Entry draw CRS below 400](https://www.cicnews.com/2026/07/french-language-express-entry-draw-sees-crs-cutoff-dip-below-400-0778376.html)
- [Immigration.ca — 5,000 French-speaking candidates invited at CRS 399](https://immigration.ca/canada-invites-5000-french-speaking-candidates-express-entry-crs-399-july-22-2026/)
- [JCA Law — French language proficiency Express Entry guide](https://jcalaw.ca/french-language-proficiency-express-entry-guide/)
- [ESDC — NOC 21234 Web developers and programmers](https://noc.esdc.gc.ca/Structure/NOCProfile?code=21234&version=2021.0)
- [CRTC — CASL FAQ](https://crtc.gc.ca/eng/com500/faq500.htm)
- [Gmail — Email sender guidelines FAQ](https://support.google.com/a/answer/14229414)
- [GMass — Gmail bulk sender guidelines 2026](https://www.gmass.co/blog/gmail-bulk-sender-guidelines/)
- [Web scraping case law — hiQ v. LinkedIn and beyond](https://iswebscrapinglegal.com/blog/web-scraping-case-law/)
- [Resumefy — How to write a Canadian resume in 2026](https://resumefy.ca/blog/how-to-write-canadian-resume)
- [Resumemate — Canadian resume format 2026](https://www.resumemate.io/blog/canada-resume-format-differences-from-us-templates/)
