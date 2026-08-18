"""LLM TaskingBody JSON → TaskingData.

Index fields (title, FORAC/INFORM, affected units, BLUF) are merged from the
ontology. This module only builds the 1/2/3 outline. Python assigns markers.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from divarty_tasking_formatter.models import OutlineNode, TaskingData, TextSpan
from divarty_tasking_formatter.parse import canonicalize_sections, parse_inline

SCHEMA_PATH = Path(__file__).with_name("tasking_body.schema.json")

NONE_TEXTS = frozenset({"", "none", "none.", "n/a", "na", "omitted", "omitted."})

UNIT_CANON = {
    "hhbn": "HHBN",
    "hhbn,": "HHBN",
    "3-16 fa": "3-16 FAR",
    "3-16 far": "3-16 FAR",
    "1-82 fa": "1-82 FA",
    "2-82 fa": "2-82 FA",
    "6-56 adar": "6-56 ADAR",
}

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def load_tasking_body_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def parse_llm_json(payload: str | dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """Accept a dict, a list of bodies, or a JSON string (optionally fenced)."""
    if isinstance(payload, dict):
        if "taskings" in payload and isinstance(payload["taskings"], list):
            return [item for item in payload["taskings"] if isinstance(item, dict)]
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("LLM JSON payload must be a non-empty string, object, or list")
    text = payload.strip()
    text = _FENCE.sub("", text).strip()
    data = json.loads(text)
    return parse_llm_json(data)


def _plain(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_none(text: str) -> bool:
    return text.strip().casefold() in NONE_TEXTS


def _canon_unit(name: str) -> str:
    key = re.sub(r"\s+", " ", name.strip().rstrip(":")).casefold()
    return UNIT_CANON.get(key, name.strip().rstrip(":"))


def _items_from(value: Any, *, depth: int = 0) -> list[OutlineNode]:
    if value is None:
        return []
    if isinstance(value, str):
        if _is_none(value):
            return []
        return [
            OutlineNode(kind="item", body=parse_inline(value), list_depth=depth)
        ]
    if isinstance(value, dict):
        text = _plain(value.get("text") or value.get("body") or "")
        children_raw = value.get("children") or value.get("items") or []
        node = OutlineNode(
            kind="item",
            body=parse_inline(text) if text else [],
            list_depth=depth,
            children=_items_from(children_raw, depth=depth + 1)
            if not isinstance(children_raw, str)
            else _items_from([children_raw], depth=depth + 1),
        )
        if not text and not node.children:
            return []
        return [node]
    if isinstance(value, list):
        nodes: list[OutlineNode] = []
        for entry in value:
            nodes.extend(_items_from(entry, depth=depth))
        return nodes
    return []


def _unit_blocks(value: Any) -> list[OutlineNode]:
    blocks: list[OutlineNode] = []
    if not value:
        return blocks
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return blocks
    for entry in value:
        if not isinstance(entry, dict):
            continue
        unit = _canon_unit(_plain(entry.get("unit") or entry.get("section") or ""))
        if not unit:
            continue
        items = _items_from(entry.get("items") or entry.get("tasks") or [])
        if not items:
            continue
        blocks.append(OutlineNode(kind="unit_header", title=unit, children=items))
    return blocks


def _prose_spans(text: str) -> list[TextSpan]:
    cleaned = re.sub(r"\(\s*U\s*\)\s*", "", text).strip()
    if not cleaned or _is_none(cleaned):
        return []
    return parse_inline(cleaned)


def tasking_from_json(
    body: dict[str, Any],
    *,
    task_number: int | None = None,
    designation: str | None = None,
    title: str = "",
    affected_unit_staff: str = "",
    nlt_dates: str = "",
    bluf: str = "",
) -> TaskingData:
    """Merge ontology index fields with one LLM body object."""
    warnings: list[str] = []
    number = body.get("task_number", task_number)
    try:
        number = int(number) if number is not None and number != "" else task_number
    except (TypeError, ValueError):
        warnings.append(f"Non-integer task_number {number!r}; using ontology value.")
        number = task_number

    nlt = _plain(body.get("nlt_dates")) or nlt_dates
    situation_text = _plain(body.get("situation"))
    situation = OutlineNode(
        kind="section",
        title="SITUATION",
        body=_prose_spans(situation_text),
        omitted=not _prose_spans(situation_text),
    )

    execution_raw = body.get("execution") or {}
    if not isinstance(execution_raw, dict):
        execution_raw = {}
        warnings.append("execution was not an object; treated as empty.")

    concept_title = _plain(execution_raw.get("concept_title")) or "Concept of Operations"
    concept_text = _plain(execution_raw.get("concept_of_operations"))
    concept = OutlineNode(
        kind="subparagraph",
        title=concept_title,
        body=_prose_spans(concept_text),
    )

    tasks_sub = OutlineNode(
        kind="subparagraph",
        title="Tasks to Subordinate Units",
        children=_unit_blocks(execution_raw.get("tasks_to_subordinate_units")),
    )
    staff_blocks = _unit_blocks(execution_raw.get("tasks_to_staff"))
    extras: list[OutlineNode] = []
    if staff_blocks:
        extras.append(
            OutlineNode(
                kind="subparagraph",
                title="Tasks to Staff",
                children=staff_blocks,
            )
        )
    coord_items = _items_from(execution_raw.get("coordinating_instructions"))
    coord = OutlineNode(
        kind="subparagraph",
        title="Coordinating Instructions",
        children=coord_items,
    )

    execution = OutlineNode(
        kind="section",
        title="EXECUTION",
        children=[concept, tasks_sub, *extras, coord],
    )

    cs_raw = body.get("command_and_signal") or {}
    if not isinstance(cs_raw, dict):
        cs_raw = {}
        warnings.append("command_and_signal was not an object; treated as empty.")

    command_items = _items_from(cs_raw.get("command"))
    signal_items = _items_from(cs_raw.get("signal"))
    command_and_signal = OutlineNode(
        kind="section",
        title="COMMAND AND SIGNAL",
        children=[
            OutlineNode(kind="subparagraph", title="Command", children=command_items),
            OutlineNode(kind="subparagraph", title="Signal", children=signal_items),
        ],
    )

    des = designation if designation in ("FORAC", "INFORM") else None
    sections = canonicalize_sections(
        [situation, execution, command_and_signal],
        warnings,
    )
    return TaskingData(
        task_number=number,
        designation=des,
        title=title,
        affected_unit_staff=affected_unit_staff,
        nlt_dates=nlt,
        bluf=bluf,
        sections=sections,
        warnings=warnings,
    )
