import os
from pathlib import Path

from data.yaml_parser import yaml_parser, YAMLParserError
from domain.entities import Mission


def test_create_mission_from_example_yaml():
    example_path = str(Path(__file__).resolve().parent.parent / "example_mission.yalm")
    assert os.path.exists(example_path), "example_mission.yalm should exist at repo root"

    mission = yaml_parser.create_mission_from_yaml(example_path)
    assert isinstance(mission, Mission)
    assert mission.name == "example_mission"
    assert len(mission.tasks) == 3

    task_names = [t.name for t in mission.tasks]
    assert "Créer module example" in task_names
    assert "Ajouter tests unitaires" in task_names
    assert "Créer README" in task_names


def test_validate_yaml_structure_ok():
    example_path = str(Path(__file__).resolve().parent.parent / "example_mission.yalm")
    data = yaml_parser.parse_file(example_path)
    errors = yaml_parser.validate_yaml_structure(data)
    assert errors == []


