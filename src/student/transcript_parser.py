"""Parse UVA SIS transcript PDFs to extract completed course codes."""

from __future__ import annotations

import re


def parse_transcript_pdf(pdf_bytes: bytes) -> list[str]:
    """Extract course codes from a UVA SIS transcript PDF.

    Returns a list of course codes (e.g. ["CS 2120", "MATH 3100"]) for
    courses that have a letter grade (completed, not in-progress).
    """
    import pymupdf

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()

    return extract_courses_from_text(text)


def extract_courses_from_text(text: str) -> list[str]:
    """Extract completed course codes from raw transcript text.

    Matches lines like:
        CS 2120 Discrete Math and Theory 1 A- 3.0
        MATH 3100 Introduction to Probability B 3.0

    Only includes courses with a letter grade (A-F range), excluding
    in-progress courses (no grade) and transfer credits (TE grade).
    """
    # Pattern: DEPT NUMBER CourseName Grade Credits
    # Grade is a letter A-D optionally followed by +/-, or F
    pattern = re.compile(
        r"^([A-Z]{2,4})\s+(\d{4}[A-Z]?)\s+.+?\s+([A-DF][+-]?)\s+\d+\.\d+\s*$",
        re.MULTILINE,
    )

    courses: list[str] = []
    seen: set[str] = set()

    for match in pattern.finditer(text):
        dept = match.group(1)
        number = match.group(2)
        code = f"{dept} {number}"
        if code not in seen:
            seen.add(code)
            courses.append(code)

    return sorted(courses)
