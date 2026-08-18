import json
from pathlib import Path

from divarty_tasking_formatter.json_body import parse_llm_json, tasking_from_json
from divarty_tasking_formatter.ontology import (
    HhqOrder,
    RunningEstimate,
    estimates_for_order,
    merge_orders_and_bodies,
    pack_llm_context,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_pack_llm_context_drops_unapproved() -> None:
    order = HhqOrder.from_record(_load("hhq_orders.json")[0])
    estimates = [RunningEstimate.from_record(r) for r in _load("running_estimates.json")]
    pack = pack_llm_context(order, estimates)
    sections = [row["staffSection"] for row in pack["runningEstimates"]]
    assert sections == ["S3"]
    assert "S2" not in sections


def test_estimates_join_on_primary_key_and_order_name() -> None:
    order = HhqOrder.from_record(_load("hhq_orders.json")[0])
    estimates = [RunningEstimate.from_record(r) for r in _load("running_estimates.json")]
    approved = estimates_for_order(order, estimates, approved_only=True)
    assert len(approved) == 1
    assert approved[0].staff_section == "S3"


def test_merge_uses_ontology_index_and_task_number_join() -> None:
    orders = _load("hhq_orders.json")
    estimates = _load("running_estimates.json")
    payload = _load("llm_bodies.json")
    taskings = merge_orders_and_bodies(orders, estimates, payload)
    assert [t.task_number for t in taskings] == [1, 3]
    first = taskings[0]
    assert first.designation == "FORAC"
    assert first.title.startswith("FRAGORD 1")
    assert "3-16 FAR" in first.affected_unit_staff
    assert first.nlt_dates == "06 AUG 26"
    assert "Salute Battery" in first.bluf
    third = taskings[1]
    assert third.designation == "INFORM"
    assert third.task_number == 3


def test_parse_fenced_json() -> None:
    bodies = parse_llm_json("```json\n{\"task_number\": 9, \"situation\": \"x\"}\n```")
    assert bodies[0]["task_number"] == 9
    data = tasking_from_json(bodies[0], title="X", designation="INFORM")
    assert data.task_number == 9
    assert "SITUATION" in (data.sections[0].title or "")
