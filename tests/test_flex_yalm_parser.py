"""Tests for the flexible YAML parser."""

from textwrap import dedent

import pytest

from data.flex_yalm_parser import FlexYALMParser, FlexYALMParserError


def test_parse_meta_and_mission_only():
    parser = FlexYALMParser()
    content = dedent(
        """
        meta:
          project_name: Flex YALM Demo
        mission: "Audit rapide du projet actuel"
        mode: read_only
        """
    )

    mission = parser.parse_content(content, source="inline-test")

    assert mission.name == "Flex YALM Demo"
    assert len(mission.tasks) == 1
    assert mission.tasks[0].goal == "Audit rapide du projet actuel"

    diagnostics = parser.get_last_diagnostics()
    assert diagnostics["mode"] == "flex_meta"
    assert diagnostics["fallback_chain"][0]["source"] == "root.mission"


def test_parse_prompt_only_string():
    parser = FlexYALMParser()

    mission = parser.parse_content("Fais un audit rapide du projet actuel")

    assert mission.name.startswith("mission_")
    assert len(mission.tasks) == 1
    assert mission.tasks[0].goal == "Fais un audit rapide du projet actuel"

    diagnostics = parser.get_last_diagnostics()
    assert diagnostics["mode"] == "prompt_only"
    assert diagnostics["fallback_chain"][0]["source"] == "root_string"


def test_meta_task_fallback_priority():
    parser = FlexYALMParser()
    content = dedent(
        """
        meta:
          project_name: Solo Meta
          task: "Analyser la configuration actuelle"
        """
    )

    mission = parser.parse_content(content)

    assert mission.name == "Solo Meta"
    assert mission.tasks[0].goal == "Analyser la configuration actuelle"

    diagnostics = parser.get_last_diagnostics()
    assert diagnostics["fallback_chain"][0]["source"] == "meta.task"


def test_empty_content_raises():
    parser = FlexYALMParser()

    with pytest.raises(FlexYALMParserError):
        parser.parse_content("\n\n    \n")


