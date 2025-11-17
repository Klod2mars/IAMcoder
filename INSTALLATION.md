# Installation et utilisation d'AIHomeCoder

## Installation

### 1. Prérequis

- Python 3.10 ou supérieur
- [Ollama](https://ollama.ai/) installé et configuré (optionnel pour l'IA locale)
- Un modèle IA local (Qwen ou DeepSeek) - optionnel

### 2. Installation des dépendances

```bash
pip install -r requirements.txt
```

### 3. Installation des modèles Ollama (optionnel)

```bash
# Installer Qwen2-Coder
ollama pull qwen2-coder:7b-instruct

# Ou installer DeepSeek-Coder
ollama pull deepseek-coder:6.7b
```

## Utilisation

### Exécuter une mission

```bash
python main.py run example_mission.yalm
```

### Options disponibles

```bash
# Utiliser un modèle spécifique
python main.py run mission.yalm --model qwen2-coder:7b-instruct

# Mode dry-run (simulation)
python main.py run mission.yalm --dry-run

# Mode verbeux
python main.py run mission.yalm --verbose
```

### Autres commandes

```bash
# Afficher le diff entre deux fichiers
python main.py diff file1.py file2.py

# Afficher la version
python main.py version

# Aide
python main.py --help
```

## Architecture

Le projet suit une Clean Architecture avec trois couches principales :

1. **Domain Layer** (`domain/`) : Logique métier pure
   - `entities/` : Entités (Task, Mission, DiffResult)
   - `services/` : Services métier (ExecutorService)

2. **Data Layer** (`data/`) : Accès aux données
   - `yaml_parser.py` : Parseur YAML
   - `diff_engine.py` : Moteur de diff et rollback
   - `context_index.py` : Index vectoriel (ChromaDB)
   - `ai_connector.py` : Connecteur Ollama

3. **Presentation Layer** (`presentation/`) : Interface utilisateur
   - `cli.py` : CLI principale
   - `logger.py` : Gestion des logs
   - `ui_diff_view.py` : Affichage des diffs

4. **Core** (`core/`) : Utilitaires transverses
   - `guardrail.py` : Protection des chemins
   - `file_manager.py` : Gestion des fichiers
   - `settings.py` : Configuration globale

## Configuration

Les fichiers de configuration se trouvent dans `config/` :

- `config/settings.yaml` : Configuration principale
- `config/profiles/` : Profils IA

## Logs

Les logs sont générés automatiquement dans `logs/` au format Markdown :
- Nom de fichier : `session_YYYYMMDD_HHMMSS.md`

## Compatibilité Windows

Le système gère automatiquement la compatibilité des emojis avec Windows en les remplaçant par des alternatives ASCII dans la console.

## Notes importantes

- Les fonctionnalités d'IA nécessitent Ollama et un modèle installé
- Le système de rollback fonctionne automatiquement dans un dépôt Git
- Les zones "sanctuaires" sont protégées par le guardrail
