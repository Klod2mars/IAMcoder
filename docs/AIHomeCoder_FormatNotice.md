# Notice utilisateur AIHomeCoder

> Mise a disposition de la notice bilingue pour l'interface AIHomeCoder (31-10-2025).

## Notice FR

### Objectif
AIHomeCoder propose une interface CLI pour orchestrer des missions YALM et suivre les operations du moteur. Cette notice presente les bonnes pratiques d'installation, de lancement et de diagnostic.

### Prerequis
- Python 3.10 ou version superieure installee.
- Environnement virtuel configure via `python -m venv venv` et active.
- Dependances installees: `pip install -r requirements.txt`.
- Acces lecture/ecriture au repertoire de travail et aux fichiers `.yalm`.

### Installation initiale
1. Cloner ou decompresser le depot AIHomeCoder.
2. Se placer dans la racine du projet (`aihomecoder/`).
3. Creer et activer l'environnement virtuel si necessaire.
4. Installer les dependances Python.
5. Configurer les profils dans `config/profiles/` selon le mode voulu (`read_only` ou `write_enabled`).

### Lancement rapide
- `python main.py` : ouvre le shell interactif AIHomeCoder.
- `python run_mission.py <mission.yalm>` : execute une mission specifique.
- `python presentation/welcome_screen.py` : affiche la page d'accueil terminale et listera les missions YALM disponibles.

### Utilisation responsable
- Toujours verifier le `mode` actif dans `config/settings.yaml` avant de lancer une mission sensible.
- Conserver une copie de sauvegarde des missions `.yalm` dans `ARCHIVES/`.
- Consulter les rapports generes dans `reports/` pour tracer les actions.

### Assistance
- Consulter `README.md` pour la presentation generale.
- Ouvrir une issue interne si une mission echoue.
- Consulter `logs/` pour diagnostiquer les erreurs runtime.

## User Guide EN

### Purpose
AIHomeCoder delivers a CLI interface designed to orchestrate YALM missions and review engine activity. This guide outlines installation steps, runtime usage, and troubleshooting tips.

### Requirements
- Python 3.10 or newer available on the workstation.
- Virtual environment prepared with `python -m venv venv` and activated.
- Project dependencies installed via `pip install -r requirements.txt`.
- Read/write access to the workspace and `.yalm` mission files.

### Initial setup
1. Clone or extract the AIHomeCoder repository.
2. Move into the project root (`aihomecoder/`).
3. Create and activate the Python virtual environment if needed.
4. Install Python dependencies.
5. Adjust profile settings in `config/profiles/` for the desired mode (`read_only` or `write_enabled`).

### Quick start
- `python main.py`: opens the interactive AIHomeCoder shell.
- `python run_mission.py <mission.yalm>`: runs a dedicated mission file.
- `python presentation/welcome_screen.py`: launches the terminal welcome screen and lists available YALM missions.

### Safe usage guidelines
- Always confirm the active `mode` in `config/settings.yaml` before executing sensitive missions.
- Keep backup copies of `.yalm` missions inside `ARCHIVES/`.
- Review generated reports in `reports/` to track operations and audits.

### Support
- Read `README.md` for the project overview.
- Raise an internal issue ticket if a mission fails.
- Inspect `logs/` files to troubleshoot runtime errors.

## Revision
- 2025-10-31 : Premiere diffusion de la notice bilingue via AIHomeCoder.

