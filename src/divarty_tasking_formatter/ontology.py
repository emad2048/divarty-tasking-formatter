"""Map HHQ Orders Repo + Running Estimates onto index fields and LLM context packs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

from divarty_tasking_formatter.json_body import parse_llm_json, tasking_from_json
from divarty_tasking_formatter.models import TaskingData

CANONICAL_UNITS = ("HHBN", "3-16 FAR", "1-82 FA", "2-82 FA", "6-56 ADAR")


def _get(row: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    # case-insensitive
    lower = {str(k).casefold(): v for k, v in row.items()}
    for key in keys:
        found = lower.get(key.casefold())
        if found not in (None, ""):
            return found
    return default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().casefold() in {"true", "1", "yes", "y"}


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _format_nlt(value: Any) -> str:
    text = _as_text(value)
    if not text:
        return ""
    # ISO timestamp → uppercase Army-ish date if it looks like a date
    if "T" in text:
        text = text.split("T", 1)[0]
    return text


@dataclass
class HhqOrder:
    """One HHQ Orders Repo object (one selectable tasking)."""

    primary_key: str = ""
    order_name: str = ""
    task_number: int | None = None
    action_type: str | None = None
    bluf: str = ""
    affected_units: str = ""
    media_reference: Any = None
    upload_date: str = ""
    uploaded_by: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_record(cls, row: dict[str, Any]) -> HhqOrder:
        raw_action = _as_text(_get(row, "actionType", "action_type")).upper()
        action = raw_action if raw_action in ("FORAC", "INFORM") else None
        return cls(
            primary_key=_as_text(_get(row, "primaryKey_", "primary_key")),
            order_name=_as_text(_get(row, "orderName", "order_name")),
            task_number=_as_int(_get(row, "taskNumber", "task_number", default=None)),
            action_type=action if action else None,
            bluf=_as_text(_get(row, "bluf")),
            affected_units=_as_text(_get(row, "affectedUnits", "affected_units")),
            media_reference=_get(row, "mediaReference", "media_reference", default=None),
            upload_date=_as_text(_get(row, "uploadDate", "upload_date")),
            uploaded_by=_as_text(_get(row, "uploadedBy", "uploaded_by")),
            raw=dict(row),
        )


@dataclass
class RunningEstimate:
    """One Running Estimates object."""

    primary_key: str = ""
    title: str = ""
    order_name: str = ""
    order_reference: str = ""
    staff_section: str = ""
    running_estimate: str = ""
    staff_response: str = ""
    status: str = ""
    suspense_date: str = ""
    order_poc: str = ""
    approved_for_drafting: str = ""
    compilation_status: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_record(cls, row: dict[str, Any]) -> RunningEstimate:
        return cls(
            primary_key=_as_text(_get(row, "primaryKey_", "primary_key")),
            title=_as_text(_get(row, "title")),
            order_name=_as_text(_get(row, "orderName", "order_name")),
            order_reference=_as_text(
                _get(row, "orderReference", "order_reference", "orderForeignKey", "order_foreign_key")
            ),
            staff_section=_as_text(_get(row, "staffSection", "staff_section")),
            running_estimate=_as_text(_get(row, "runningEstimate", "running_estimate")),
            staff_response=_as_text(_get(row, "staffResponse", "staff_response")),
            status=_as_text(_get(row, "status")),
            suspense_date=_format_nlt(_get(row, "suspenseDate", "suspense_date", default="")),
            order_poc=_as_text(_get(row, "orderPoc", "order_poc")),
            approved_for_drafting=_as_text(
                _get(row, "approvedForDrafting", "approved_for_drafting")
            ),
            compilation_status=_as_bool(
                _get(row, "compilationStatus", "compilation_status", default=False)
            ),
            raw=dict(row),
        )

    def is_approved(self) -> bool:
        return bool(self.approved_for_drafting) or self.compilation_status


def sort_hhq_orders(orders: Iterable[HhqOrder]) -> list[HhqOrder]:
    return sorted(
        orders,
        key=lambda o: (o.task_number is None, o.task_number or 0, o.order_name),
    )


def estimates_for_order(
    order: HhqOrder,
    estimates: Iterable[RunningEstimate],
    *,
    approved_only: bool = True,
) -> list[RunningEstimate]:
    keys = {k for k in (order.primary_key, order.order_name) if k}
    matched: list[RunningEstimate] = []
    for estimate in estimates:
        refs = {k for k in (estimate.order_reference, estimate.order_name) if k}
        if keys & refs or (
            order.order_name and estimate.order_name == order.order_name
        ):
            if approved_only and not estimate.is_approved():
                continue
            matched.append(estimate)
    return matched


def nlt_from_estimates(estimates: Iterable[RunningEstimate]) -> str:
    dates = [e.suspense_date for e in estimates if e.suspense_date]
    if not dates:
        return ""
    # Prefer a single shared suspense; otherwise join unique values.
    unique = list(dict.fromkeys(dates))
    return unique[0] if len(unique) == 1 else ", ".join(unique)


def pack_llm_context(
    order: HhqOrder,
    estimates: Iterable[RunningEstimate],
) -> dict[str, Any]:
    """Context bundle sent to the Vantage agent for one task number."""
    approved = estimates_for_order(order, estimates, approved_only=True)
    return {
        "taskNumber": order.task_number,
        "actionType": order.action_type,
        "orderName": order.order_name,
        "affectedUnits": order.affected_units,
        "bluf": order.bluf,
        "nltDatesHint": nlt_from_estimates(approved),
        "runningEstimates": [
            {
                "staffSection": e.staff_section,
                "runningEstimate": e.running_estimate,
                "staffResponse": e.staff_response,
                "orderPoc": e.order_poc,
                "suspenseDate": e.suspense_date,
                "status": e.status,
            }
            for e in approved
        ],
    }


def index_tasking(
    order: HhqOrder,
    estimates: Iterable[RunningEstimate] | None = None,
    body: dict[str, Any] | None = None,
) -> TaskingData:
    """Ontology index merged with an optional LLM body object."""
    estimates = list(estimates or [])
    nlt = ""
    if body:
        nlt = str(body.get("nlt_dates") or "").strip()
    if not nlt:
        nlt = nlt_from_estimates(estimates_for_order(order, estimates, approved_only=False))
    designation = order.action_type if order.action_type in ("FORAC", "INFORM") else None
    if body is None:
        from divarty_tasking_formatter.parse import canonicalize_sections
        from divarty_tasking_formatter.models import OutlineNode

        return TaskingData(
            task_number=order.task_number,
            designation=designation,
            title=order.order_name,
            affected_unit_staff=order.affected_units,
            nlt_dates=nlt,
            bluf=order.bluf,
            sections=canonicalize_sections([]),
        )
    return tasking_from_json(
        body,
        task_number=order.task_number,
        designation=designation,
        title=order.order_name,
        affected_unit_staff=order.affected_units,
        nlt_dates=nlt,
        bluf=order.bluf,
    )


def merge_orders_and_bodies(
    orders: Iterable[HhqOrder | dict[str, Any]],
    estimates: Iterable[RunningEstimate | dict[str, Any]],
    llm_payload: str | dict[str, Any] | list[Any],
) -> list[TaskingData]:
    """Join selected HHQ orders to LLM JSON bodies by task_number."""
    parsed_orders = [
        o if isinstance(o, HhqOrder) else HhqOrder.from_record(o) for o in orders
    ]
    parsed_estimates = [
        e if isinstance(e, RunningEstimate) else RunningEstimate.from_record(e)
        for e in estimates
    ]
    bodies = parse_llm_json(llm_payload)
    by_number: dict[int, dict[str, Any]] = {}
    extras: list[dict[str, Any]] = []
    for body in bodies:
        number = body.get("task_number")
        try:
            by_number[int(number)] = body
        except (TypeError, ValueError):
            extras.append(body)

    taskings: list[TaskingData] = []
    unused = list(extras)
    for order in sort_hhq_orders(parsed_orders):
        body = by_number.pop(order.task_number, None) if order.task_number is not None else None
        if body is None and unused:
            body = unused.pop(0)
        related = estimates_for_order(order, parsed_estimates, approved_only=False)
        taskings.append(index_tasking(order, related, body))
    return taskings
