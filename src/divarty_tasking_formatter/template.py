"""Letterhead template helper.

Pass a real 26-42-001 .docx as template_path when you have it (styles, header
letterhead art). Until then, format_weekly_order draws HQ / location / date
in Times New Roman and add_classification_banner writes UNCLASSIFIED
header/footer.
"""

from __future__ import annotations

from pathlib import Path

from divarty_tasking_formatter.classification import add_classification_banner
from divarty_tasking_formatter.render import create_document


def write_letterhead_template(path: str | Path, *, classification: str = "UNCLASSIFIED") -> Path:
    """Write a blank TNR document with classification banners (fallback template)."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc, _ = create_document(None)
    add_classification_banner(doc, level=classification)
    doc.save(str(dest))
    return dest
