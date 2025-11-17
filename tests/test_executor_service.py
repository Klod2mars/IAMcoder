from domain.entities import Mission, Task, TaskStatus, MissionStatus
from domain.services.executor_service import ExecutorService


def build_sample_mission() -> Mission:
    mission = Mission(name="m", description="d")
    mission.add_task(Task(name="t1", goal="g1"))
    mission.add_task(Task(name="t2", goal="g2"))
    return mission


def test_validate_mission_ok():
    mission = build_sample_mission()
    errors = ExecutorService().validate_mission(mission)
    assert errors == []


def test_execute_mission_success_updates_statuses():
    mission = build_sample_mission()
    service = ExecutorService()

    ok = service.execute_mission(mission)
    assert ok is True
    assert mission.status == MissionStatus.COMPLETED
    assert all(t.status == TaskStatus.COMPLETED for t in mission.tasks)


