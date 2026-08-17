"""DIVARTY tasking formatter — one Markdown tasking → one .docx chunk.

Open items still pending verification:
  - Foundry transform signature (MediaSetOutput vs Action Type vs generator)
  - Unit .docx template file (named paragraph styles / letterhead / margins)
  - Classification banner spec (page headers, color, portion markings)
  - Real Vantage/LLM input schema (parse.py SCHEMA is the swap point)

This package does not compile a Weekly Tasking Order, emit REFERENCES /
ACKNOWLEDGE blocks, or render redline markup.
"""

from divarty_tasking_formatter.parse import parse_input
from divarty_tasking_formatter.render import format_tasking

__all__ = ["parse_input", "format_tasking"]
