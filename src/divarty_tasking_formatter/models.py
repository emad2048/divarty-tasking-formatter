"""Typed data model for a single DIVARTY tasking.

Parsing produces these dataclasses; rendering consumes them. Keep this module
free of Markdown and python-docx details so the schema can change in parse.py
without rewriting the document builder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

NodeKind = Literal["section", "subparagraph", "unit_header", "item"]
Designation = Literal["FORAC", "INFORM"]


@dataclass
class TextSpan:
    """A run of text with optional inline bold (from Markdown ``**...**``)."""

    text: str
    bold: bool = False


@dataclass
class OutlineNode:
    """One renderable block in the tasking body.

    Children are a homogeneous list of OutlineNode so a subparagraph may contain
    prose-bearing siblings that are unit headers, numbered items, or nested
    items without a separate child type for each pattern.
    """

    kind: NodeKind
    title: str | None = None
    body: list[TextSpan] = field(default_factory=list)
    omitted: bool = False
    children: list[OutlineNode] = field(default_factory=list)
    # Markdown ordered-list nest depth (0 = first numbered level under a
    # subparagraph or unit header). None when kind is not "item".
    list_depth: int | None = None


@dataclass
class TaskingData:
    """Parsed content of one tasking. Always has three canonical sections after normalize."""

    task_number: int | None
    designation: Designation | None
    title: str
    affected_unit_staff: str
    nlt_dates: str
    bluf: str
    sections: list[OutlineNode]
    warnings: list[str] = field(default_factory=list)
