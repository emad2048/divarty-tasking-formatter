"""Markdown → TaskingData.

All assumptions about the LLM-agent input shape live in SCHEMA below. When a
real sample arrives, retune those patterns and the heading/field names here —
do not scatter schema knowledge into render.py.

TODO(verify): real Vantage/LLM markdown schema has not been sampled yet.
The proposed contract (H1 task line, bold field labels, H2/H3/H4 + ordered
lists) is implemented here and is expected to need adjustment.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from divarty_tasking_formatter.models import OutlineNode, TaskingData, TextSpan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SCHEMA — the one place to retune when the real input sample arrives
# ---------------------------------------------------------------------------
SCHEMA = {
    "h1_task": re.compile(
        r"^#\s+TASK\s*#\s*(?P<num>\d+)\s*\((?P<des>FORAC|INFORM)\)\s*:\s*(?P<title>.+)$",
        re.IGNORECASE,
    ),
    "field_affected": re.compile(
        r"^\*{0,2}Affected Unit/Staff:\*{0,2}\s*(?P<value>.*)$",
        re.IGNORECASE,
    ),
    "field_nlt": re.compile(
        r"^\*{0,2}NLT Dates:\*{0,2}\s*(?P<value>.*)$",
        re.IGNORECASE,
    ),
    "field_bluf": re.compile(
        r"^\*{0,2}BLUF:\*{0,2}\s*(?P<value>.*)$",
        re.IGNORECASE,
    ),
    "h2": re.compile(r"^##\s+(?:(?P<num>\d+)\.\s*)?(?P<title>.+?)\s*$"),
    "h3": re.compile(
        r"^###\s+(?:(?P<letter>[A-Za-z])\.\s+)?(?P<title>.+?)\s*$"
    ),
    "h4": re.compile(r"^####\s+(?P<title>.+?)\s*$"),
    "ordered_item": re.compile(r"^(?P<indent>[ \t]*)(?P<num>\d+)\.\s+(?P<text>.*)$"),
    "inline_bold": re.compile(r"\*\*(.+?)\*\*"),
}

CANONICAL_SECTIONS = ("SITUATION", "EXECUTION", "COMMAND AND SIGNAL")

CONCEPT_TITLES = frozenset(
    {
        "concept of operations",
        "concept of the operation",
        "concept of the operations",
    }
)
TASKS_SUBORDINATE_TITLE = "tasks to subordinate units"
COORDINATING_TITLE = "coordinating instructions"
COMMAND_TITLE = "command"
SIGNAL_TITLE = "signal"


def parse_input(markdown_text: str) -> TaskingData:
    """Parse one tasking's structured Markdown into TaskingData.

    Raises ValueError only for empty/non-string input. Missing sections become
    Omitted placeholders; other content issues are recorded as warnings.
    """
    if not isinstance(markdown_text, str) or not markdown_text.strip():
        raise ValueError("markdown_text must be a non-empty string")

    warnings: list[str] = []
    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    raw = _parse_lines(lines, warnings)
    data = _normalize(raw, warnings)
    data.warnings = warnings
    for warning in warnings:
        logger.warning(warning)
    return data


def parse_inline(text: str) -> list[TextSpan]:
    """Split Markdown inline ``**bold**`` into TextSpan runs."""
    spans: list[TextSpan] = []
    pos = 0
    for match in SCHEMA["inline_bold"].finditer(text):
        if match.start() > pos:
            chunk = text[pos : match.start()]
            if chunk:
                spans.append(TextSpan(chunk))
        bold_text = match.group(1)
        if bold_text:
            spans.append(TextSpan(bold_text, bold=True))
        pos = match.end()
    if pos < len(text):
        tail = text[pos:]
        if tail:
            spans.append(TextSpan(tail))
    return spans


def _strip_title(title: str) -> str:
    return title.strip().rstrip(".").strip()


def _norm_key(title: str) -> str:
    return re.sub(r"\s+", " ", _strip_title(title)).casefold()


def _is_concept(title: str) -> bool:
    return _norm_key(title) in CONCEPT_TITLES


def _canonical_section_name(title: str) -> str | None:
    key = _norm_key(title)
    for name in CANONICAL_SECTIONS:
        if key == name.casefold():
            return name
    return None


@dataclass
class _RawParse:
    task_number: int | None = None
    designation: str | None = None
    title: str = ""
    affected_unit_staff: str = ""
    nlt_dates: str = ""
    bluf: str = ""
    sections: list[OutlineNode] = field(default_factory=list)


@dataclass
class _Cursor:
    section: OutlineNode | None = None
    sub: OutlineNode | None = None
    unit: OutlineNode | None = None
    # (indent_width, item_node) stack for the current container
    list_stack: list[tuple[int, OutlineNode]] = field(default_factory=list)

    def container(self) -> OutlineNode | None:
        return self.unit or self.sub or self.section

    def clear_list(self) -> None:
        self.list_stack.clear()

    def enter_section(self, node: OutlineNode) -> None:
        self.section = node
        self.sub = None
        self.unit = None
        self.clear_list()

    def enter_sub(self, node: OutlineNode) -> None:
        self.sub = node
        self.unit = None
        self.clear_list()

    def enter_unit(self, node: OutlineNode) -> None:
        self.unit = node
        self.clear_list()


def _indent_width(indent: str) -> int:
    return len(indent.expandtabs(4))


def _append_body(node: OutlineNode, text: str) -> None:
    spans = parse_inline(text)
    if not spans:
        return
    if node.body:
        # Continuation / additional paragraph: join with a space.
        node.body.append(TextSpan(" "))
    node.body.extend(spans)


def _append_field(raw: _RawParse, field_name: str, text: str) -> None:
    current = getattr(raw, field_name)
    combined = f"{current} {text}".strip() if current else text
    setattr(raw, field_name, combined)


def _parse_lines(lines: list[str], warnings: list[str]) -> _RawParse:
    raw = _RawParse()
    cursor = _Cursor()
    seen_h2 = False
    last_field: str | None = None

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        h1 = SCHEMA["h1_task"].match(stripped)
        if h1:
            raw.task_number = int(h1.group("num"))
            raw.designation = h1.group("des").upper()
            raw.title = h1.group("title").strip()
            last_field = None
            continue

        if not seen_h2:
            affected = SCHEMA["field_affected"].match(stripped)
            if affected:
                raw.affected_unit_staff = affected.group("value").strip()
                last_field = "affected_unit_staff"
                continue
            nlt = SCHEMA["field_nlt"].match(stripped)
            if nlt:
                raw.nlt_dates = nlt.group("value").strip()
                last_field = "nlt_dates"
                continue
            bluf = SCHEMA["field_bluf"].match(stripped)
            if bluf:
                raw.bluf = bluf.group("value").strip()
                last_field = "bluf"
                continue

        # Distinguish ## from ### / #### — startswith("##") also matches ###.
        if line.lstrip().startswith("#"):
            last_field = None
            hashes = len(line.lstrip()) - len(line.lstrip().lstrip("#"))
            heading_text = line.lstrip().lstrip("#").strip()
            if hashes == 2:
                seen_h2 = True
                title = _strip_title(SCHEMA["h2"].match("## " + heading_text).group("title") if SCHEMA["h2"].match("## " + heading_text) else heading_text)
                node = OutlineNode(kind="section", title=title)
                raw.sections.append(node)
                cursor.enter_section(node)
                continue
            if hashes == 3:
                title = _strip_title(heading_text)
                letter_match = re.match(r"^[A-Za-z]\.\s+(.+)$", title)
                if letter_match:
                    title = _strip_title(letter_match.group(1))
                node = OutlineNode(kind="subparagraph", title=title)
                parent = cursor.section
                if parent is None:
                    parent = OutlineNode(kind="section", title="UNPLACED")
                    raw.sections.append(parent)
                    cursor.enter_section(parent)
                    warnings.append(
                        "Subparagraph appeared before any top-level section; "
                        f"attached under a placeholder section near {title!r}."
                    )
                parent.children.append(node)
                cursor.enter_sub(node)
                continue
            if hashes >= 4:
                title = _strip_title(heading_text).rstrip(":")
                node = OutlineNode(kind="unit_header", title=title)
                parent = cursor.sub or cursor.section
                if parent is None:
                    parent = OutlineNode(kind="section", title="UNPLACED")
                    raw.sections.append(parent)
                    cursor.enter_section(parent)
                    warnings.append(
                        "Unit header appeared before any section; "
                        f"attached under a placeholder near {title!r}."
                    )
                parent.children.append(node)
                cursor.enter_unit(node)
                continue
            if hashes == 1 and not h1:
                warnings.append(f"Unrecognized H1 line ignored: {stripped[:80]}")
                continue

        item_match = SCHEMA["ordered_item"].match(line)
        if item_match:
            last_field = None
            indent = _indent_width(item_match.group("indent"))
            text = item_match.group("text").strip()
            parent = cursor.container()
            if parent is None:
                parent = OutlineNode(kind="section", title="UNPLACED")
                raw.sections.append(parent)
                cursor.enter_section(parent)
                warnings.append(
                    "Numbered item appeared before any section; "
                    f"attached under a placeholder near {text[:40]!r}."
                )
            while cursor.list_stack and cursor.list_stack[-1][0] >= indent:
                if cursor.list_stack[-1][0] == indent:
                    cursor.list_stack.pop()
                    break
                cursor.list_stack.pop()
            if cursor.list_stack and cursor.list_stack[-1][0] < indent:
                item_parent = cursor.list_stack[-1][1]
                depth = (item_parent.list_depth or 0) + 1
            else:
                item_parent = parent
                depth = 0
            item = OutlineNode(
                kind="item",
                body=parse_inline(text),
                list_depth=depth,
            )
            item_parent.children.append(item)
            cursor.list_stack.append((indent, item))
            continue

        # Prose / list continuation
        if not seen_h2 and last_field is not None:
            _append_field(raw, last_field, stripped)
            continue
        leading = len(line) - len(line.lstrip(" \t"))
        if cursor.list_stack and leading > 0:
            _append_body(cursor.list_stack[-1][1], stripped)
            continue
        cursor.clear_list()
        target = cursor.container()
        if target is None:
            warnings.append(f"Orphan prose ignored before first section: {stripped[:80]}")
            continue
        _append_body(target, stripped)

    if raw.task_number is None:
        warnings.append("Missing H1 task line; task number/designation/title may be incomplete.")
    return raw


def _has_content(node: OutlineNode) -> bool:
    if any(span.text.strip() for span in node.body):
        return True
    return any(_has_content(child) for child in node.children)


def _omitted_sub(title: str) -> OutlineNode:
    return OutlineNode(kind="subparagraph", title=title, omitted=True)


def _flag_empty_subparagraphs(node: OutlineNode) -> None:
    """Empty required subparagraphs render as Omitted rather than a bare label."""
    for child in node.children:
        if child.kind == "subparagraph" and not _has_content(child):
            child.omitted = True
            child.body = []
        else:
            _flag_empty_subparagraphs(child)


def _take_first(
    nodes: list[OutlineNode], predicate
) -> tuple[OutlineNode | None, list[OutlineNode]]:
    found: OutlineNode | None = None
    rest: list[OutlineNode] = []
    for node in nodes:
        if found is None and predicate(node):
            found = node
        else:
            rest.append(node)
    return found, rest


def _normalize_execution(section: OutlineNode) -> None:
    subs = [c for c in section.children if c.kind == "subparagraph"]
    others = [c for c in section.children if c.kind != "subparagraph"]
    concept, rest = _take_first(subs, lambda n: _is_concept(n.title or ""))
    tasks, rest = _take_first(
        rest, lambda n: _norm_key(n.title or "") == TASKS_SUBORDINATE_TITLE
    )
    coord, extras = _take_first(
        rest, lambda n: _norm_key(n.title or "") == COORDINATING_TITLE
    )
    ordered: list[OutlineNode] = []
    ordered.append(concept or _omitted_sub("Concept of Operations"))
    ordered.append(tasks or _omitted_sub("Tasks to Subordinate Units"))
    ordered.extend(extras)
    ordered.append(coord or _omitted_sub("Coordinating Instructions"))
    # Preserve unexpected non-subparagraph children (e.g. stray items) after
    # the canonical block so render can still emit them with a warning.
    section.children = ordered + others
    _flag_empty_subparagraphs(section)


def _normalize_command_signal(section: OutlineNode) -> None:
    subs = [c for c in section.children if c.kind == "subparagraph"]
    others = [c for c in section.children if c.kind != "subparagraph"]
    command, rest = _take_first(
        subs, lambda n: _norm_key(n.title or "") == COMMAND_TITLE
    )
    signal, extras = _take_first(
        rest, lambda n: _norm_key(n.title or "") == SIGNAL_TITLE
    )
    ordered: list[OutlineNode] = [
        command or _omitted_sub("Command"),
        signal or _omitted_sub("Signal"),
        *extras,
        *others,
    ]
    section.children = ordered
    _flag_empty_subparagraphs(section)


def _find_section(sections: list[OutlineNode], name: str) -> OutlineNode | None:
    for node in sections:
        if _canonical_section_name(node.title or "") == name:
            return node
    return None


def _normalize(raw: _RawParse, warnings: list[str]) -> TaskingData:
    designation = raw.designation if raw.designation in ("FORAC", "INFORM") else None
    if raw.designation and designation is None:
        warnings.append(f"Unrecognized task designation {raw.designation!r}.")

    return TaskingData(
        task_number=raw.task_number,
        designation=designation,
        title=raw.title,
        affected_unit_staff=raw.affected_unit_staff,
        nlt_dates=raw.nlt_dates,
        bluf=raw.bluf,
        sections=canonicalize_sections(raw.sections, warnings),
    )


def canonicalize_sections(
    sections: list[OutlineNode],
    warnings: list[str] | None = None,
) -> list[OutlineNode]:
    """Force SITUATION / EXECUTION / COMMAND AND SIGNAL (plus extras).

    Used by both Markdown parse and LLM JSON import so omitted subparagraphs
    and letter order stay consistent.
    """
    warnings = warnings if warnings is not None else []
    extras: list[OutlineNode] = []
    for node in sections:
        canonical = _canonical_section_name(node.title or "")
        if canonical:
            node.title = canonical
        else:
            warnings.append(
                f"Unrecognized top-level section {node.title!r}; emitting as a best-effort extra section."
            )
            extras.append(node)

    situation = _find_section(sections, "SITUATION") or OutlineNode(
        kind="section", title="SITUATION", omitted=True
    )
    situation.title = "SITUATION"
    if not _has_content(situation):
        situation.omitted = True
        situation.children = []
        situation.body = []

    execution = _find_section(sections, "EXECUTION") or OutlineNode(
        kind="section", title="EXECUTION"
    )
    execution.title = "EXECUTION"
    _normalize_execution(execution)

    command = _find_section(sections, "COMMAND AND SIGNAL") or OutlineNode(
        kind="section", title="COMMAND AND SIGNAL"
    )
    command.title = "COMMAND AND SIGNAL"
    _normalize_command_signal(command)

    return [situation, execution, command, *extras]
