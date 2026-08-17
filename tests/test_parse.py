import pytest

from divarty_tasking_formatter.parse import parse_input


def test_empty_input_raises() -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        parse_input("")
    with pytest.raises(ValueError, match="non-empty string"):
        parse_input("   \n  ")
    with pytest.raises(ValueError, match="non-empty string"):
        parse_input(None)  # type: ignore[arg-type]


def test_ceremony_parses_forac_and_unit_headers(fixture_text) -> None:
    data = parse_input(fixture_text("ceremony_units.md"))
    assert data.task_number == 1
    assert data.designation == "FORAC"
    assert "FRAGORD 1" in data.title
    assert data.affected_unit_staff.startswith("HHBn")
    assert data.nlt_dates == "06 AUG 26"
    assert "Salute Battery" in data.bluf

    titles = [section.title for section in data.sections[:3]]
    assert titles == ["SITUATION", "EXECUTION", "COMMAND AND SIGNAL"]

    execution = data.sections[1]
    sub_titles = [child.title for child in execution.children if child.kind == "subparagraph"]
    assert sub_titles[:3] == [
        "Concept of Operations",
        "Tasks to Subordinate Units",
        "Coordinating Instructions",
    ]

    tasks = execution.children[1]
    unit_names = [child.title for child in tasks.children if child.kind == "unit_header"]
    assert unit_names == ["3-16 FAR", "HHBN", "6-56 ADAR"]

    honor = tasks.children[1].children[0]
    assert honor.kind == "item"
    assert honor.body[0].bold is True
    assert honor.body[0].text == "Honor Guard:"

    coord = execution.children[2]
    assert coord.children[0].kind == "item"
    assert coord.children[0].list_depth == 0
    nested = coord.children[1].children[0]
    assert nested.kind == "item"
    assert nested.list_depth == 1


def test_omitted_sections_keep_canonical_labels(fixture_text) -> None:
    data = parse_input(fixture_text("omitted_sections.md"))
    execution = data.sections[1]
    assert [c.title for c in execution.children if c.kind == "subparagraph"] == [
        "Concept of Operations",
        "Tasks to Subordinate Units",
        "Coordinating Instructions",
    ]
    assert execution.children[2].omitted is True
    assert execution.children[2].title == "Coordinating Instructions"

    command_signal = data.sections[2]
    assert command_signal.children[0].title == "Command"
    assert command_signal.children[0].omitted is True
    assert command_signal.children[1].title == "Signal"
    assert command_signal.children[1].omitted is False


def test_inform_keeps_concept_of_the_operation_and_all_unit(fixture_text) -> None:
    data = parse_input(fixture_text("inform_all.md"))
    assert data.designation == "INFORM"
    assert data.task_number == 3
    execution = data.sections[1]
    assert execution.children[0].title == "Concept of the Operation"
    tasks = execution.children[1]
    assert tasks.children[0].kind == "unit_header"
    assert tasks.children[0].title == "All"
    command = data.sections[2].children[0]
    assert command.title == "Command"
    assert command.omitted is True


def test_malformed_item_under_execution_is_preserved(fixture_text) -> None:
    data = parse_input(fixture_text("malformed_nesting.md"))
    execution = data.sections[1]
    stray_items = [c for c in execution.children if c.kind == "item"]
    assert len(stray_items) == 1
    assert "no parent subparagraph" in "".join(s.text for s in stray_items[0].body)
