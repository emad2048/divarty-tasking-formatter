"""DIVARTY Weekly Tasking Order formatter.

Index fields come from HHQ Orders Repo. The LLM returns TaskingBody JSON
(see docs/vantage_mode2_prompt.md). Python alone writes the .docx.

Open items:
  - Drop in a real 26-42-001 .docx as template_path (letterhead/styles)
  - Foundry Action / MediaSetOutput RIDs
  - Banner color and portion markings
"""

from divarty_tasking_formatter.compile import format_weekly_order
from divarty_tasking_formatter.foundry import generate_weekly_order_bytes
from divarty_tasking_formatter.json_body import parse_llm_json, tasking_from_json
from divarty_tasking_formatter.ontology import (
    HhqOrder,
    pack_llm_context,
    merge_orders_and_bodies,
)
from divarty_tasking_formatter.parse import parse_input
from divarty_tasking_formatter.render import format_tasking

__all__ = [
    "format_tasking",
    "format_weekly_order",
    "generate_weekly_order_bytes",
    "parse_input",
    "parse_llm_json",
    "tasking_from_json",
    "HhqOrder",
    "pack_llm_context",
    "merge_orders_and_bodies",
]
