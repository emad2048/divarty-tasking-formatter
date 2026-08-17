"""Classification markings.

TODO(verify): classification banner (e.g. "UNCLASSIFIED") top and bottom of
each page, centered, bold, and colored per classification level. Portion
markings and distribution statements are not yet specified.
"""

from __future__ import annotations

from typing import Any


def add_classification_banner(doc: Any, level: str = "UNCLASSIFIED") -> None:
    """Placeholder integration point for page banners.

    Currently a no-op so callers can invoke it without guessing unconfirmed
    header/footer, color, or portion-marking requirements.
    """
    return None
