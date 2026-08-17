"""Foundry transform adapter stub.

This module is NOT imported by the core parse/render path. Keep
``format_tasking`` unit-testable outside Foundry; swap this wrapper once the
pipeline IO is confirmed.

TODO(verify): confirm the correct Foundry transform decorator/signature for a
function that consumes a tabular/text dataset (markdown tasking content) and
emits a binary docx output to a Media Set (not a standard Foundry dataset).
Options to check:
  - @transform + Output(MediaSetOutput) pattern
  - @transform.spark.using
  - @transform_generator
  - A stand-alone function invoked by an existing Action Type in this pipeline
Confirm the exact input dataset shape (column name for markdown) once the
upstream Vantage/LLM step is wired up. Also confirm the ``transforms-media``
conda dependency.
"""

from __future__ import annotations

from io import BytesIO

from divarty_tasking_formatter.parse import parse_input
from divarty_tasking_formatter.render import format_tasking


def tasking_docx_bytes(
    markdown_text: str,
    template_path: str | None = None,
) -> tuple[bytes, list[str]]:
    """Foundry-agnostic helper: markdown in, .docx bytes + warnings out."""
    data = parse_input(markdown_text)
    document, warnings = format_tasking(data, template_path=template_path)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue(), warnings


# TODO(verify): uncomment and retune once dataset RIDs / paths and the Media Set
# output are known. Likely Palantir docs pattern (unconfirmed for this pipeline):
#
#   from transforms.api import transform, Input
#   from transforms.mediasets import MediaSetOutput
#
#   @transform(
#       source=Input("/path/or/ri.foundry.main.dataset...."),
#       output=MediaSetOutput("/path/or/ri.mio.main.media-set...."),
#   )
#   def compute(source, output):
#       # Confirm column name for markdown (placeholder: "markdown_text").
#       for row in source.dataframe().collect():
#           markdown = row["markdown_text"]
#           payload, warnings = tasking_docx_bytes(markdown)
#           task_no = row.get("task_number", "unknown")
#           output.put_media_item(BytesIO(payload), f"task_{task_no}.docx")
#           for warning in warnings:
#               log.warning(warning)
#
# Alternate signatures to check: @transform.spark.using, @transform_generator,
# or an Action Type that calls tasking_docx_bytes() directly.
