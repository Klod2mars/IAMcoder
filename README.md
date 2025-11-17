# 🧠 AIHomeCoder

**Version:** 1.0.0  
**Architecture:** Clean Architecture (domain / data / presentation)  
**Language:** Python 3.10+

## Description

AIHomeCoder est un moteur local de co-édition de code inspiré de Cursor. Il utilise un modèle IA local (Qwen ou DeepSeek via Ollama) pour interpréter et appliquer des missions définies dans des fichiers `.YALM`, avec système de diff, rollback et logs Markdown.

## 🎯 Objectifs

- Exécution locale de code via IA
- Interprétation de fichiers `.YALM` pour audits, refactors et diffs
- Clean Architecture modulaire et maintenable
- Protection des zones sensibles (guardrails)
- Système de rollback via Git
- Logs générés en Markdown

## 📦 Installation

### Prérequis

- Python 3.10 ou supérieur
- [Ollama](https://ollama.ai/) installé et configuré
- Un modèle IA local (Qwen ou DeepSeek)

### Installation des dépendances

```bash
pip install -r requirements.txt
```

### Installation des modèles Ollama

```bash
# Installer Qwen2-Coder
ollama pull qwen2-coder:7b-instruct

# Ou installer DeepSeek-Coder
ollama pull deepseek-coder:6.7b
```

## 🚀 Utilisation

### Exécution d'une mission

```bash
python -m presentation.cli run example_mission.yalm
```

### Options disponibles

```bash
# Utiliser un modèle spécifique
python -m presentation.cli run mission.yalm --model qwen2-coder:7b-instruct

# Mode dry-run (simulation)
python -m presentation.cli run mission.yalm --dry-run

# Mode verbeux
python -m presentation.cli run mission.yalm --verbose
```

### Autres commandes

```bash
# Afficher le diff entre deux fichiers
python -m presentation.cli diff file1.py file2.py

# Afficher la version
python -m presentation.cli version

# Audit (à venir)
python -m presentation.cli audit target/
```

## 📁 Structure du Projet

```
aihomecoder/
├── domain/              # Layer Domain (entities et services)
│   ├── entities/        # Entités métier (Task, Mission, DiffResult)
│   └── services/        # Services métier (ExecutorService)
├── data/                # Layer Data
│   ├── yaml_parser.py   # Parseur YAML
│   ├── diff_engine.py   # Moteur de diff et rollback
│   ├── context_index.py # Index vectoriel ChromaDB
│   └── ai_connector.py  # Connecteur Ollama
├── presentation/        # Layer Presentation
│   ├── cli.py           # Interface CLI
│   ├── logger.py        # Gestion des logs
│   └── ui_diff_view.py  # Affichage des diffs
├── core/                # Utilitaires transverses
│   ├── guardrail.py     # Protection chemins sanctuaire
│   ├── file_manager.py  # Gestion fichiers
│   └── settings.py      # Configuration globale
├── config/              # Configuration
│   ├── settings.yaml
│   └── profiles/        # Profils IA
├── logs/                # Journaux de session
├── tests/               # Tests unitaires
├── requirements.txt
├── README.md
└── .aihomecoderignore
```

## 📝 Format des fichiers .YALM

Un fichier `.yalm` définit une mission avec ses tâches :

```yaml
meta:
  project_name: "my_project"
  description: "Description de la mission"
  version: "1.0.0"

tasks:
  - name: "Nom de la tâche"
    goal: "Objectif de la tâche"
    task_type: "code_generation"
    parameters:
      param1: "value1"
```

## 🛡️ Sécurité

AIHomeCoder inclut un système de protection des chemins "sanctuaires" :

- Chemins protégés par défaut :
  - `data/hive_boxes/**`
  - `.env`
  - `private/**`
  - `.git/**`

Ces chemins ne peuvent pas être modifiés par l'application.

## 🔄 Rollback

Le système de rollback utilise Git pour créer des checkpoints et restaurer l'état précédent si nécessaire. Il fonctionne automatiquement si vous êtes dans un dépôt Git.

## 📊 Logs

Les logs sont générés automatiquement dans `logs/` au format Markdown :
- `logs/session_YYYYMMDD_HHMMSS.md`

Chaque session inclut :
- Détails de la mission
- Progression des tâches
- Diffs des modifications
- Erreurs éventuelles

## 🧩 Architecture

AIHomeCoder suit les principes de Clean Architecture :

1. **Domain Layer** : Logique métier pure, sans dépendances
2. **Data Layer** : Accès aux données (fichiers, IA, index)
3. **Presentation Layer** : Interface utilisateur (CLI, logs, affichage)

Cette séparation garantit une maintenabilité et une évolutivité optimales.

## 🔧 Configuration

### Fichier `config/settings.yaml`

```yaml
ia:
  engine: "ollama"
  model_default: "qwen2-coder:7b-instruct"
  alt_model: "deepseek-coder:6.7b"

security:
  rollback: true
  sanctuary_paths:
    - "data/hive_boxes/**"
    - ".env"
```

### Profils IA

Des profils IA prédéfinis sont disponibles dans `config/profiles/` :
- `default.yaml` : Configuration par défaut
- `qwen_local.yaml` : Profil Qwen optimisé
- `deepseek_local.yaml` : Profil DeepSeek optimisé

## 🧪 Tests

```bash
# Exécuter les tests (à venir)
pytest tests/
```

## 📚 Contribution

Ce projet est structuré pour faciliter les contributions. Respectez la Clean Architecture :

- Ajouter de la logique métier dans `domain/`
- Implémenter l'accès aux données dans `data/`
- Créer des interfaces utilisateur dans `presentation/`

## 📄 Licence

Ce projet est fourni "tel quel" sans garantie.

## 🤝 Crédits

Développé avec Claude AI et inspiré par Cursor.

---

**Note :** Cette application est en développement actif. Certaines fonctionnalités peuvent être incomplètes ou en cours d'implémentation.
