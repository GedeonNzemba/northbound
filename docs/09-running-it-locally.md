# Running Northbound on your own machine

Written for Windows (PowerShell), with the macOS/Linux equivalents beside each
step. Everything below runs from the repo you cloned:

```
C:\Users\nzemb\Documents\northbound
```

---

## 1. Python

Needs **3.11 or newer** — the code uses `X | None` type syntax that older
versions reject at import.

```powershell
py --version          # expect 3.11+; if it's missing, install from python.org
```

Create the environment and install:

```powershell
cd C:\Users\nzemb\Documents\northbound\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

macOS/Linux:

```bash
cd ~/northbound/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

**Check the venv is actually active.** Your prompt gains a `(.venv)` prefix:

```
(.venv) PS C:\Users\nzemb\Documents\northbound\backend>
```

If that prefix is missing, the environment is not active and nothing below will
be found. Activation is per terminal window — open a new tab and you activate
again.

If PowerShell refuses to run the activate script, it's the execution policy,
not the project:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### `northbound` vs `python -m northbound.cli`

The install puts a `northbound` command on PATH *inside the venv*. It is
shorter, and it is the thing that breaks — it disappears the moment the venv is
not active, and on Windows it can also land in a Scripts directory that is not
on PATH at all.

**Every example below uses `python -m northbound.cli`**, which works from
`backend\` whether or not the venv is active and whether or not the editable
install succeeded. Use the short `northbound` form once you have it working, if
you prefer it.

    'northbound' is not recognized  →  the venv is not active, or the install
                                       did not run. Use python -m, or activate.

---

## 2. Prove it works before trusting it

```powershell
python -m pytest -q
```

**156 tests, all passing, no API key and no network.** That is deliberate: the
whole engine is testable offline, so a failure here is a real problem with your
setup rather than a billing or connectivity question.

A handful will report `skipped` if LibreOffice isn't installed — that's step 4
and it's optional.

---

## 3. Look at the prompt without spending anything

```powershell
python -m northbound.cli batch --dir ..\postings\golden --dry-run
```

This loads every posting in the golden set, picks a track for each, and builds
the complete prompt — **without calling the model**. Run it first every time.
Every format problem in the postings surfaces here rather than a third of the
way through a paid run.

To read the exact prompt for one posting:

```powershell
python -m northbound.cli generate --posting ..\postings\golden\<id>.json --dry-run
```

That prints the full system prompt, the profile block, the posting and the task
directive — everything the model will see. Worth reading once end to end; if
something about you is wrong in there, it will be wrong in every CV.

---

## 4. PDF companions (optional)

DOCX is the canonical artefact — it parses at ~97% across applicant tracking
systems against PDF's ~72%. The PDF is a companion for an employer who opens
the attachment directly. **Skip this and you still get a complete, sendable
application.**

```powershell
winget install TheDocumentFoundation.LibreOffice
```

macOS: `brew install --cask libreoffice`. Linux: `apt install libreoffice-writer`.

You do **not** need to add it to PATH — the code looks in the standard install
locations, because neither the Windows installer nor the macOS app bundle puts
it there. To confirm it's usable:

```powershell
python -c "from northbound.generate.render_pdf import pdf_available; print(pdf_available())"
```

That converts a real test document rather than just looking for the binary. A
LibreOffice install missing the Writer module has `soffice` on disk and
converts nothing, which is how it was found.

---

## 5. The paid run

You need an API key from <https://console.anthropic.com>. Set it for the
session:

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Permanently (survives a reboot, and no other program sees it in your shell
history):

```powershell
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```

macOS/Linux: `export ANTHROPIC_API_KEY="sk-ant-..."` in `~/.zshrc`.

**Never put the key in a file inside the repo.** `note.txt` is gitignored for
exactly this reason; nothing else is.

Then one posting first — not the whole set:

```powershell
python -m northbound.cli generate --posting ..\postings\golden\<id>.json --out ..\out
```

Read what it produced before running the batch. Then:

```powershell
python -m northbound.cli batch --dir ..\postings\golden --out ..\out
```

---

## 6. Reading the output

```
out\ready\    Gedeon-Nzemba-<employer>-<title>-CV.docx  (+ .pdf)
              Gedeon-Nzemba-<employer>-<title>-Cover-Letter.docx  (+ .pdf)
out\parked\   the same pair, plus <name>-WHY-PARKED.txt
```

**Parked is not failure.** It means a document did not clear every check twice
and is being held for you to look at rather than sent. The `WHY-PARKED.txt`
names the exact rule and the exact line.

Exit codes, because a scheduler will eventually read them:

| Code | Meaning |
|---|---|
| 0 | Everything ready |
| 2 | Something parked — documents written, not sendable |
| 1 | Something errored |

The usage line at the end of a batch is worth watching:

```
usage: 41 call(s)  prompt 812,400 (734,000 cached = 90%)  output 38,200
```

That cached percentage is the only evidence the profile prefix is being reused
rather than re-billed on every posting. If it reads 0% across a batch,
something is invalidating it and the run costs roughly ten times what it should.

---

## 7. What is deliberately not automated yet

The system does **not** send anything. Discovery (scraping Job Bank on a
schedule) and sending (email) are Phase 2 and 3. Right now it turns a saved
posting into checked documents, and you decide what happens to them.

Postings come from the golden set, harvested by GitHub Actions — the
development container cannot reach `gc.ca`, so scraping runs there. To rebuild
it: Actions tab → *spikes* → *Run workflow* → tick `harvest_golden_set` and
`skip_other_spikes`. It refuses to overwrite an existing set on purpose; a
frozen evaluation input is the only kind two runs can be compared against.
