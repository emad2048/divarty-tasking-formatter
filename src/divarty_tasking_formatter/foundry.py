"""Foundry / Vantage Action adapter.

Core generate_weekly_order_bytes() is Foundry-agnostic. The Action Type
should pass an object set of HHQ Orders Repo plus related Running Estimates
and the LLM JSON (or a precomputed TaskingBody payload).

TODO(verify):
  - Exact Action Type parameter names vs Ontology API property aliases
  - MediaSetOutput RID / path for the generated .docx
  - Whether the LLM is invoked inside the Action or Vantage writes JSON first
  - transforms-media conda dependency if this runs as a transform instead
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from divarty_tasking_formatter.compile import format_weekly_order
from divarty_tasking_formatter.models import WeeklyOrderData
from divarty_tasking_formatter.ontology import (
    HhqOrder,
    RunningEstimate,
    merge_orders_and_bodies,
)


def generate_weekly_order_bytes(
    hhq_orders: list[dict[str, Any] | HhqOrder],
    running_estimates: list[dict[str, Any] | RunningEstimate],
    llm_payload: str | dict[str, Any] | list[Any],
    *,
    order_number: str,
    date_line: str,
    references: list[str] | None = None,
    time_zone: str = "Central Daylight Time",
    task_organization: str = "Omitted",
    acknowledge_name: str = "",
    official_name: str = "",
    attachments: list[str] | None = None,
    template_path: str | None = None,
    headquarters: str = "HQ, 1CD DIVARTY",
    location: str = "FORT HOOD, TX",
) -> tuple[bytes, list[str]]:
    """Action-ready helper: ontology rows + LLM JSON → .docx bytes."""
    taskings = merge_orders_and_bodies(hhq_orders, running_estimates, llm_payload)
    order = WeeklyOrderData(
        order_number=order_number,
        date_line=date_line,
        headquarters=headquarters,
        location=location,
        references=list(references or []),
        time_zone=time_zone,
        task_organization=task_organization,
        taskings=taskings,
        acknowledge_name=acknowledge_name,
        official_name=official_name,
        attachments=list(attachments or []),
    )
    document, warnings = format_weekly_order(order, template_path=template_path)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue(), warnings


def tasking_docx_bytes(
    markdown_text: str,
    template_path: str | None = None,
) -> tuple[bytes, list[str]]:
    """Legacy single-tasking path (Markdown fallback)."""
    from divarty_tasking_formatter.parse import parse_input
    from divarty_tasking_formatter.render import format_tasking

    data = parse_input(markdown_text)
    document, warnings = format_tasking(data, template_path=template_path)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue(), warnings


# Vantage / Ontology Action contract (not executed here):
#
#   Action: Generate Weekly Tasking Order
#   Parameter: hhqOrders : ObjectSet<HHQ Orders Repo>
#   Side load: Running Estimates where orderReference in selected keys
#              AND (approvedForDrafting IS NOT NULL OR compilationStatus = true)
#   LLM: send pack_llm_context(order, estimates) per task; collect TaskingBody JSON
#   Output: Media Set item  1CD_DIVARTY_WTO_{order_number}.docx
#
#   from transforms.api import transform, Input
#   from transforms.mediasets import MediaSetOutput
#
#   @transform(
#       orders=Input("ri.foundry.main.dataset...."),       # optional snapshot
#       output=MediaSetOutput("ri.mio.main.media-set...."),
#   )
#   def compute(orders, output):
#       payload, warnings = generate_weekly_order_bytes(...)
#       output.put_media_item(BytesIO(payload), f"1CD_DIVARTY_WTO_{order_no}.docx")
