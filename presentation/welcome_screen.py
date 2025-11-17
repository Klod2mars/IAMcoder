"""Terminal welcome screen for AIHomeCoder.

The script lists available YALM missions located at the repository root
and provides quick-start instructions for operators.
"""

from pathlib import Path

from core.workspace_store import get_workspace_store


ROOT_DIR = Path(__file__).resolve().parent.parent


def collect_missions() -> list[str]:
    """Return sorted mission filenames available at repository root."""

    patterns = ("*.yalm", "*.yalm.yaml")
    result: set[str] = set()

    for pattern in patterns:
        for candidate in ROOT_DIR.glob(pattern):
            if candidate.parent == ROOT_DIR:
                result.add(candidate.name)

    return sorted(result)


def render_header() -> None:
    store = get_workspace_store()
    last_workspace = store.get_last_workspace()
    active_workspace = Path(last_workspace) if last_workspace else ROOT_DIR

    print("=" * 70)
    print(" AIHomeCoder :: Terminal Welcome Screen")
    print("=" * 70)
    print("Workspace actif:", active_workspace)
    print()

    if not last_workspace:
        print("Aucun workspace externe sélectionné.")
        print("Utilisez `run_mission.py` ou `python main.py --workspace <CHEMIN>` pour en définir un.")
        print("Option: Saisir un nouveau workspace lors du prochain lancement.")
        print()


def render_mission_list(missions: list[str]) -> None:
    if not missions:
        print("No YALM missions detected at the repository root.")
        return

    print("Detected YALM missions:")
    for index, name in enumerate(missions, start=1):
        print(f"  {index:02d}. {name}")
    print()


def render_next_steps() -> None:
    print("Quick commands:")
    print("  python main.py                        # interactive CLI")
    print("  python run_mission.py <file.yalm>     # launch a mission")
    print("  python presentation/welcome_screen.py # refresh this screen")
    print()

    print("Before running write-enabled missions, verify `config/settings.yaml`." )
    print("For audits and logs, inspect the `reports/` and `logs/` directories.")


def main() -> None:
    render_header()
    missions = collect_missions()
    render_mission_list(missions)
    render_next_steps()


if __name__ == "__main__":
    main()

