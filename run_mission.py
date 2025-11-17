import os
import subprocess
from pathlib import Path

from core.workspace_store import get_workspace_store

# Root directory of AIHomeCoder project
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def list_yalm_files(base_dir: Path | None = None):
    """
    List all mission files (.yalm, .yaml, .yalm.yaml) in the given directory.
    Added multi-extension support on 2025-10-30 for better compatibility.
    """
    scan_dir = base_dir or ROOT_DIR
    valid_exts = (".yalm", ".yaml", ".yalm.yaml")
    try:
        files = [f for f in os.listdir(scan_dir) if f.lower().endswith(valid_exts)]
    except Exception as e:
        print(f"[ERROR] Impossible de lister les fichiers YALM dans {scan_dir}: {e}")
        files = []
    return sorted(files)

def main():
    print("\n==============================")
    print("  AIHomeCoder - Selector YALM")
    print("==============================\n")

    store = get_workspace_store()
    last_workspace = store.get_last_workspace()
    workspace_path = None

    # --- Sélection du workspace ---
    if last_workspace and Path(last_workspace).exists():
        answer = input(
            f"Souhaitez-vous utiliser le dernier workspace connu ?\n[{last_workspace}] (o/n): "
        ).strip().lower()
        if not answer or answer.startswith("o"):
            workspace_path = Path(last_workspace)

    if workspace_path is None:
        print("Aucun workspace externe sélectionné." if not last_workspace else "")
        while True:
            new_path = input(
                "Indiquez le chemin absolu du projet à auditer (laisser vide pour le dépôt courant): "
            ).strip()
            if not new_path:
                workspace_path = Path(ROOT_DIR)
                break
            candidate = Path(new_path).expanduser()
            if candidate.exists() and candidate.is_dir():
                workspace_path = candidate
                break
            print("Chemin invalide. Veuillez réessayer.")

    # Sauvegarde du workspace choisi
    store.set_workspace(str(workspace_path))

    # --- Ajout explicite : affichage du workspace actif ---
    print(f"\n📂 Workspace actif : {workspace_path}\n")
    # -------------------------------------------------------

    # --- Patch ajouté : on se place temporairement dans le workspace pour lire les missions ---
    current_dir = os.getcwd()
    try:
        os.chdir(workspace_path)
        files = list_yalm_files(workspace_path)
    finally:
        os.chdir(current_dir)  # Retour au répertoire d’origine
    # --- Fin du patch ---

    if not files:
        print(f"Aucun fichier .yalm ou .yaml trouvé dans {workspace_path}.")
        print("Créez-en un avec VS Code ou relancez après en avoir copié un.")
        input("\nAppuyez sur une touche pour fermer...")
        return

    # Affichage de la liste
    for i, f in enumerate(files, 1):
        print(f"{i}. {f}")
    print("0. Quit\n")

    # Choix utilisateur
    try:
        choice = int(input("Select the file to execute: "))
    except ValueError:
        print("Invalid entry.")
        return

    if choice == 0:
        return
    if choice < 1 or choice > len(files):
        print("Invalid number.")
        return

    selected = files[choice - 1]
    print(f"\nRunning mission: {selected}")
    print(f"Workspace actif: {workspace_path}\n")

    cmd = [
        os.path.join(ROOT_DIR, "venv", "Scripts", "python.exe"),
        os.path.join(ROOT_DIR, "main.py"),
        "run",
        selected,
        "--verbose"
    ]

    try:
        # L’exécution réelle de la mission se fait toujours depuis AIHomeCoder
        subprocess.run(cmd, cwd=str(workspace_path))
    except Exception as e:
        print(f"Error running mission: {e}")
        input("\nPress any key to close...")
        return

    # Archive option
    archive_dir = os.path.join(ROOT_DIR, "ARCHIVES")
    os.makedirs(archive_dir, exist_ok=True)

    move = input("\nArchive this file? (y/n): ").strip().lower()
    if move == "y":
        src = os.path.join(workspace_path, selected)
        dst = os.path.join(archive_dir, selected)
        try:
            os.replace(src, dst)
            print(f"File moved to ARCHIVES/{selected}")
        except Exception as e:
            print(f"Error moving file: {e}")

    input("\nPress any key to close...")

if __name__ == "__main__":
    main()
