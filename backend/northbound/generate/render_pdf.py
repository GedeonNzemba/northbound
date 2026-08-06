"""
The PDF companion. docs/07 F-A.

**Derived, never parallel.** The PDF is produced by converting the canonical
DOCX, not by a second renderer built from the same object. A second renderer
would have to be kept in step with the first by discipline alone, and the day it
drifts, the employer reads a document that says something the CV does not.
Converting means there is exactly one layout, and the PDF is by construction the
document a reader would see if they opened the DOCX in Word.

This is not the conversion docs/07 warns about. That warning is against
*generating the DOCX* from HTML or PDF, which reintroduces the layout artefacts
that break ATS parsers. This runs the other way: the DOCX stays native and
canonical, and the PDF is a read-only companion for a human.

Why a companion at all, when DOCX parses at ~97% against PDF's ~72%: some
employers open the attachment directly rather than feeding it to an ATS, and a
DOCX renders differently on their machine than it did on ours. The PDF is
fixed. Send both, lead with the DOCX.

LibreOffice does the conversion, so it is **optional by design** — a machine
without it still produces the DOCX, which is the artefact that matters. Nothing
in the send path may depend on the PDF existing.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

CONVERTER_NAMES = ("soffice", "libreoffice")
TIMEOUT_S = 120


class PdfUnavailable(RuntimeError):
    """LibreOffice is not installed. Not an error — the DOCX is the deliverable."""


def converter_path() -> str | None:
    for name in CONVERTER_NAMES:
        if found := shutil.which(name):
            return found
    return None


_CAPABILITY: bool | None = None


def pdf_available(*, recheck: bool = False) -> bool:
    """
    Whether a PDF can actually be produced — probed, not inferred.

    Checking that `soffice` is on PATH is not enough, and the failure it misses
    is silent. A LibreOffice install without the Writer module — which is what
    this was first written against — has the binary, exits 0, prints "source
    file could not be loaded", and produces nothing, for every document. A
    presence check would report the capability as available and the whole batch
    would produce no PDFs with no error anyone reads.

    So the probe converts a real (tiny) document. It costs a couple of seconds
    once per process, and it is the difference between knowing and assuming.
    """
    global _CAPABILITY
    if _CAPABILITY is not None and not recheck:
        return _CAPABILITY
    _CAPABILITY = _probe()
    return _CAPABILITY


def _probe() -> bool:
    if converter_path() is None:
        return False
    try:
        from docx import Document  # noqa: PLC0415

        with tempfile.TemporaryDirectory(prefix="northbound-probe-") as d:
            src = Path(d) / "probe.docx"
            doc = Document()
            doc.add_paragraph("probe")
            doc.save(str(src))
            render_pdf(src, d)
        return True
    except Exception:
        return False


def render_pdf(docx_path: Path | str, out_dir: Path | str | None = None) -> Path:
    """
    Convert a rendered DOCX to PDF.

    Runs against a throwaway LibreOffice profile: the default profile takes a
    lock, so two conversions in the same session — which is exactly what a batch
    of applications is — would serialise or fail outright.
    """
    docx_path = Path(docx_path)
    if not docx_path.exists():
        raise FileNotFoundError(docx_path)

    binary = converter_path()
    if binary is None:
        raise PdfUnavailable(
            "LibreOffice not found. Install it for PDF companions "
            "(`apt install libreoffice-writer` / `brew install --cask libreoffice`); "
            "the DOCX is unaffected.")

    out_dir = Path(out_dir) if out_dir else docx_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="northbound-lo-") as profile:
        result = subprocess.run(
            [binary, "--headless", "--norestore",
             f"-env:UserInstallation=file://{profile}",
             "--convert-to", "pdf", "--outdir", str(out_dir), str(docx_path)],
            capture_output=True, text=True, timeout=TIMEOUT_S, check=False,
        )

    produced = out_dir / (docx_path.stem + ".pdf")
    if not produced.exists():
        raise RuntimeError(
            f"PDF conversion produced nothing (exit {result.returncode}).\n"
            f"stdout: {result.stdout.strip()[:400]}\n"
            f"stderr: {result.stderr.strip()[:400]}")
    return produced


def extract_pdf_text(path: Path | str) -> str:
    """Read the PDF back the way a human reader's viewer would."""
    from pypdf import PdfReader  # noqa: PLC0415 — only needed to verify

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def page_count(path: Path | str) -> int:
    from pypdf import PdfReader  # noqa: PLC0415

    return len(PdfReader(str(path)).pages)


__all__ = ["render_pdf", "pdf_available", "converter_path", "extract_pdf_text",
           "page_count", "PdfUnavailable"]
