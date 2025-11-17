# Audit : Champ `goal` de la classe Task

**Date :** 2025-11-02  
**Objectif :** Déterminer le rôle réel du champ 'goal' dans AIHomeCoder  
**Mode :** Audit en lecture seule  
**Statut :** ✅ Complété

---

## 📋 Résumé Exécutif

Le champ `goal` de la classe `Task` est un **champ obligatoire et critique** dans l'architecture AIHomeCoder. Bien que son utilisation opérationnelle soit **limitée au logging et aux diagnostics**, il est profondément intégré dans le système de validation et de sérialisation, rendant sa suppression ou son assouplissement non-trivial en termes de compatibilité rétroactive.

### Conclusion Principale

Le champ `goal` est **optionnel du point de vue fonctionnel** (non utilisé dans la logique d'exécution des tâches), mais **obligatoire du point de vue structurel** (validation stricte à plusieurs niveaux). En V2, il serait possible de le rendre optionnel uniquement avec des modifications coordonnées dans 4 fichiers clés.

---

## 🔍 Analyse Détaillée

### 1. Définition et Validation

#### Fichier : `domain/entities/task.py`

```python
@dataclass
class Task:
    name: str
    goal: str  # Ligne 26 : champ obligatoire (non-optionnel)
    task_type: str = "generic"
    # ...
    
    def __post_init__(self):
        if not self.name:
            raise ValueError("Task name cannot be empty")
        if not self.goal:  # Ligne 37-38 : validation stricte
            raise ValueError("Task goal cannot be empty")
```

**Constats :**
- `goal` est déclaré comme `str` (non-`Optional[str]`)
- Validation obligatoire dans `__post_init__` avec exception explicite
- Aucune valeur par défaut (`""` est refusée par la validation)

---

### 2. Utilisation dans le Parsing YAML

#### 2.1 Parser Standard (`data/yaml_parser.py`)

**Lignes 137-139 :**
```python
task = Task(
    name=task_name,
    goal=task_data.get("goal", ""),  # ⚠️ Chaîne vide comme fallback
    task_type=task_type,
    parameters=parameters
)
```

**Problème identifié :**
- Le parser utilise `task_data.get("goal", "")` comme fallback
- Si `goal` est absent du YAML, le parser passe `""` à `Task.__init__`
- La validation `__post_init__` **rejettera** cette chaîne vide et lancera une exception
- **Cette configuration est contradiction intrinsèque**

**Ligne 188-189 (Validation YAML) :**
```python
if "goal" not in task and "name" not in task:
    errors.append(f"Task {i+1} must have at least 'goal' or 'name'")
```

**Constats :**
- La validation YAML accepte des tâches sans `goal` si `name` est présent
- Mais la création de `Task` échouera quand même si `goal` est absent ou vide

---

#### 2.2 Parser Flexible (`data/flex_yalm_parser.py`)

**Lignes 332-345 :**
```python
goal_value = self._pick_first(
    raw_task,
    ["goal", "prompt", "description", "summary"],  # Fallback multi-sources
)

if isinstance(goal_value, list):
    goal = " ".join(str(item).strip() for item in goal_value if str(item).strip())
else:
    goal = str(goal_value).strip() if goal_value else ""

if not goal:
    raise FlexYALMParserError(  # ⚠️ Exception explicite si goal vide
        f"Task {index}: missing goal/description in provided mapping."
    )
```

**Constats :**
- Le flex parser utilise un système de **fallback multi-sources** (goal → prompt → description → summary)
- Si aucune source n'est fournie, le parser lève une exception explicite
- **Pas de chaîne vide** : soit un goal valide, soit une erreur

**Ligne 371-374 (String simple) :**
```python
if isinstance(raw_task, str):
    goal = raw_task.strip()
    if not goal:
        raise FlexYALMParserError(f"Task {index}: empty instruction string.")
```

**Constats :**
- Les tâches basées sur des chaînes utilisent la chaîne entière comme `goal`
- Validation de non-viduité

---

### 3. Utilisation Opérationnelle

#### 3.1 Exécuteur (`domain/services/executor_service.py`)

**Ligne 138 : Guardrail**
```python
enforce_task_restrictions(task.goal or "", mode)
```

**Constats :**
- Le `goal` est utilisé comme **texte source pour analyse lexicale** de restrictions read_only
- La vérification recherche les mots-clés "write", "delete", "move" dans le texte du goal
- **Seule utilisation fonctionnelle** du champ `goal` dans l'exécution

**Lignes 147, 160 : Diagnostics**
```python
{"event": "blocked", "task": task.name, "goal": task.goal, "mode": mode, "error": str(exc)}
{"event": "started", "task": task.name, "goal": task.goal, "mode": mode}
```

**Constats :**
- Le `goal` est inclus dans les événements de diagnostic pour contexte
- **Usage informatif uniquement**

**Ligne 237-238 : Validation de Mission**
```python
if not task.goal:
    errors.append(f"Task '{task.name}' has no goal")
```

**Constats :**
- L'exécuteur vérifie la présence du `goal` dans sa validation
- **Doublon** de la validation de `Task.__post_init__`

---

#### 3.2 Handler de Logique (`domain/services/task_logic_handler.py`)

**Recherche exhaustive :**
- **Aucune utilisation** du champ `goal` dans le handler
- Le handler se base sur `task_name` et `task_type` pour le dispatch
- Les fonctions `task_tree_scan`, `task_gather_documents`, `task_apply_writes`, etc. n'utilisent pas `goal`

**Constats :**
- Le `goal` est **complètement ignoré** dans l'exécution concrète des tâches
- Seuls `name`, `task_type` et `parameters` sont utilisés

---

#### 3.3 Context Bridge (`core/context_bridge.py`)

**Recherche exhaustive :**
- **Aucune utilisation** du champ `goal`
- Le context_bridge gère workspace, outputs, diagnostics, mais ne référence jamais `goal`

---

#### 3.4 Guardrail (`core/guardrail.py`)

**Lignes 105-115 :**
```python
def enforce_task_restrictions(task_text: str, mode: str | None = None) -> None:
    active_mode = mode or _get_current_mode_from_config()
    if str(active_mode).lower() == "read_only":
        lowered = (task_text or "").lower()
        for keyword in ("write", "delete", "move"):
            if keyword in lowered:
                raise GuardrailError("Forbidden in read_only mode")
```

**Constats :**
- La fonction reçoit `task.goal` comme `task_text`
- C'est l'**unique mécanisme de protection read_only basé sur le contenu**
- Si `goal` est vide, la protection est inefficace

---

### 4. Sérialisation / Désérialisation

#### 4.1 Task.to_dict() (`domain/entities/task.py`, ligne 42-44)

```python
def to_dict(self) -> Dict[str, Any]:
    return {
        "name": self.name,
        "goal": self.goal,  # Toujours inclus
        "task_type": self.task_type,
        # ...
    }
```

**Constats :**
- `goal` est systématiquement inclus dans la sérialisation
- Aucune logique conditionnelle

---

#### 4.2 Task.from_dict() (`domain/entities/task.py`, ligne 57-58)

```python
return cls(
    name=data["name"],
    goal=data["goal"],  # Accès direct sans fallback
    # ...
)
```

**Constats :**
- Accès direct à `data["goal"]` sans `get()` ni valeur par défaut
- **Exception KeyError** si `goal` absent du dictionnaire
- Pas de compatibilité dégradée

---

#### 4.3 Mission.to_dict() / from_dict() (`domain/entities/mission.py`)

**Ligne 68 :**
```python
"tasks": [task.to_dict() for task in self.tasks]
```

**Constats :**
- `goal` est propagé via `to_dict()` des tâches
- Mission ne manipule pas directement `goal`

---

### 5. Tests et Couverture

#### Fichier : `tests/test_flex_yalm_parser.py`

**Lignes 25, 39, 59 :**
```python
assert mission.tasks[0].goal == "Audit rapide du projet actuel"
assert mission.tasks[0].goal == "Fais un audit rapide du projet actuel"
assert mission.tasks[0].goal == "Analyser la configuration actuelle"
```

**Constats :**
- Tests vérifient la présence et la valeur exacte du `goal`
- Aucun test de compatibilité dégradée (goal absent/vide)

---

### 6. Diagnostic et FlexParser

#### Fichier : `data/flex_yalm_parser.py`

**Ligne 206 :**
```python
"primary_prompt": tasks[0]["goal"] if tasks else ""
```

**Constats :**
- Le `goal` de la première tâche est utilisé comme "primary_prompt" dans les diagnostics
- Information meta pour traçabilité, non critique

---

## 🎯 Réponses aux Questions d'Audit

### 1. Le champ 'goal' est-il référencé en dehors de la validation initiale de la classe Task ?

**✅ OUI**, mais **limitément** :
- `executor_service.py` : diagnostics (lignes 147, 160) + guardrail (ligne 138)
- `flex_yalm_parser.py` : diagnostics (ligne 206)
- Tests : assertions

**Aucune utilisation dans la logique d'exécution réelle des tâches** (`task_logic_handler.py`).

---

### 2. Est-il utilisé dans le logging, les rapports Markdown, le context_bridge ou les diagnostics ?

**✅ OUI dans diagnostics** :
- `executor_service.py` : événements "blocked", "started"
- `flex_yalm_parser.py` : "primary_prompt"

**❌ NON dans** :
- Logging Markdown (`presentation/logger.py`) : aucune trace
- Rapports Markdown générés : non analysé en profondeur, mais aucun pattern identifié
- Context Bridge : aucune utilisation

---

### 3. Y a-t-il des dépendances implicites (ex. context_meta, mission.metadata, etc.) liées à ce champ ?

**❌ NON**, aucune dépendance implicite identifiée :
- `mission.metadata` ne contient pas de référence à `goal`
- `context_meta` ne référence pas `goal`
- Le champ `goal` reste isolé au niveau `Task`

**Exception :**
- Le `flex_yalm_parser` place parfois `tasks[0]["goal"]` dans `description_hint` (lignes 136, 162, 177)
- Utilisation **informelle** pour description de mission, non contractuelle

---

### 4. En V2, peut-on le rendre optionnel sans casser la compatibilité rétroactive ?

**⚠️ PARTIELLEMENT** :

#### Modifications Nécessaires :
1. **`domain/entities/task.py`** :
   - Changer `goal: str` → `goal: Optional[str] = None`
   - Supprimer/modifier validation dans `__post_init__`
   - Gérer `from_dict()` avec `get("goal", None)`

2. **`domain/services/executor_service.py`** :
   - Gérer `task.goal or ""` de manière explicite partout
   - Mettre à jour validation (ligne 237-238)

3. **`data/flex_yalm_parser.py`** :
   - Accepter tâches sans `goal` (modifier lignes 342-345)
   - Fournir valeur par défaut raisonnable

4. **`data/yaml_parser.py`** :
   - Gérer absence de `goal` dans `_build_mission` (ligne 139)
   - Aligner validation (ligne 188)

#### Risques :
- **Breaking change** pour missions existantes si `goal` devenait totalement absent
- **Perte de protection read_only** si `goal` est vide et `guardrail` est utilisé
- **Tests à adapter** (3 assertions dans `test_flex_yalm_parser.py`)

#### Compatibilité :
- **Rétrocompatibilité possible** si valeur par défaut `""` ou None raisonnable
- Parsers déjà tolérants via fallback multi-sources

---

## 📊 Matrice d'Utilisation

| Composant | Lecture | Écriture | Validation | Logging | Logique |
|-----------|---------|----------|------------|---------|---------|
| `Task.__post_init__` | ❌ | ❌ | ✅ | ❌ | ❌ |
| `Task.to_dict()` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `Task.from_dict()` | ❌ | ✅ | ❌ | ❌ | ❌ |
| `yaml_parser._build_mission()` | ❌ | ✅ | ⚠️ | ❌ | ❌ |
| `flex_yalm_parser._coerce_task_blueprint()` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `executor_service._execute_task()` | ✅ | ❌ | ❌ | ✅ | ❌ |
| `executor_service.validate_mission()` | ✅ | ❌ | ✅ | ❌ | ❌ |
| `executor_service.publish_diagnostic()` | ✅ | ❌ | ❌ | ✅ | ❌ |
| `guardrail.enforce_task_restrictions()` | ✅ | ❌ | ❌ | ❌ | ✅ |
| `task_logic_handler.execute()` | ❌ | ❌ | ❌ | ❌ | ❌ |
| `context_bridge.*` | ❌ | ❌ | ❌ | ❌ | ❌ |
| Tests | ✅ | ❌ | ❌ | ❌ | ❌ |

**Légende :**
- ✅ : Utilisation avérée
- ❌ : Aucune utilisation
- ⚠️ : Utilisation contradictoire/incorrecte

---

## 🚨 Incohérences Identifiées

### 1. Validation Contradictoire YAML vs Task

**Fichier : `data/yaml_parser.py`**  
**Ligne 188-189 :**
```python
if "goal" not in task and "name" not in task:
    errors.append(f"Task {i+1} must have at least 'goal' or 'name'")
```

**Ligne 139 :**
```python
goal=task_data.get("goal", "")  # Chaîne vide par défaut
```

**Problème :**
- La validation YAML accepte des tâches sans `goal` (si `name` présent)
- Le parser utilise `""` comme fallback
- `Task.__post_init__` **rejette** `""` avec `ValueError`
- **Configuration invalide** : la validation YAML n'empêche pas les erreurs à l'exécution

**Impact :** Moyen - Confusion possible pour utilisateurs

---

### 2. Utilisation Fallback Incorrecte

**Fichier : `data/yaml_parser.py`**  
**Ligne 139 :**
```python
goal=task_data.get("goal", "")
```

**Problème :**
- Le fallback vers `""` est inutile car il sera rejeté
- Devrait être : `goal=task_data.get("goal")` ou `None` et lever une exception explicite

**Impact :** Moyen - Exceptions confuses pour développeurs

---

### 3. Doublon de Validation

**Fichier : `domain/services/executor_service.py`**  
**Ligne 237-238 :**
```python
if not task.goal:
    errors.append(f"Task '{task.name}' has no goal")
```

**Problème :**
- Cette validation est redondante avec `Task.__post_init__`
- Si l'on arrive à l'exécuteur, les Task sont déjà validées
- Cette vérification ne peut jamais être déclenchée sauf si `Task` est modifiée

**Impact :** Faible - Code mort potentiel

---

### 4. Protection Read_Only Fragile

**Fichier : `core/guardrail.py`**  
**Ligne 105 :**
```python
def enforce_task_restrictions(task_text: str, mode: str | None = None) -> None:
```

**Problème :**
- Si `task.goal` est `""`, la protection read_only est inefficace
- Le système repose entièrement sur le contenu textuel du `goal`
- Aucune vérification structurelle sur `task_type` ou `parameters`

**Impact :** Élevé - Bypass possible si `goal` vide

---

## 💡 Recommandations

### Pour V2 (Optionnel)

#### Option A : Rendre `goal` Optionnel avec Valeur par Défaut
```python
@dataclass
class Task:
    name: str
    goal: Optional[str] = None  # Optionnel
    task_type: str = "generic"
    
    def __post_init__(self):
        if not self.name:
            raise ValueError("Task name cannot be empty")
        # Supprimer validation de goal
```

**Avantages :**
- Compatibilité rétroactive possible
- Simplifie l'utilisation pour certains cas

**Inconvénients :**
- Perte de protection read_only si `goal` est None
- Potentiel de confusion ("quel est le but de cette tâche ?")

#### Option B : Rendre `goal` Optionnel avec Default Meaningful
```python
@dataclass
class Task:
    name: str
    goal: Optional[str] = None
    
    def __post_init__(self):
        if not self.name:
            raise ValueError("Task name cannot be empty")
        if not self.goal:
            self.goal = f"Execute {self.name}"  # Génération automatique
```

**Avantages :**
- Toujours un `goal` disponible pour guardrail
- Pas de breaking change majeur

**Inconvénients :**
- Génération artificielle de texte
- Perd le sens original si fourni par l'utilisateur

#### Option C : Conserver `goal` Obligatoire mais Améliorer Validation
```python
# Garder l'obligation mais corriger les inconsistances
def _build_mission(self, data: Dict[str, Any]) -> Mission:
    # ...
    for task_data in tasks_data:
        if not task_data.get("goal"):
            raise YAMLParserError(f"Task requires 'goal' field")
```

**Avantages :**
- Pas de breaking change
- Clarité maximale

**Inconvénients :**
- Restriction stricte maintenue
- Pas de flexibilité accrue

---

### Actions Immédiates (V1)

#### Priorité 1 : Corriger Contradiction YAML Parser
**Fichier : `data/yaml_parser.py`**

**Ligne 139 :**
```python
# AVANT
goal=task_data.get("goal", "")

# APRÈS
goal=task_data["goal"]  # Levera KeyError si absent
# OU
if "goal" not in task_data:
    raise YAMLParserError(f"Task requires 'goal' field")
goal=task_data["goal"]
```

**Rationale :** Éliminer la configuration invalide où validation YAML et validation Task se contredisent.

#### Priorité 2 : Supprimer Validation Redondante Executor
**Fichier : `domain/services/executor_service.py`**

**Lignes 237-238 :**
```python
# SUPPRIMER
if not task.goal:
    errors.append(f"Task '{task.name}' has no goal")
```

**Rationale :** Code mort, `Task.__post_init__` garantit déjà la présence de `goal`.

#### Priorité 3 : Documenter Protection Read_Only
**Fichier : `core/guardrail.py`**

Ajouter documentation :
```python
def enforce_task_restrictions(task_text: str, mode: str | None = None) -> None:
    """
    Enforce read_only restrictions on task text.
    
    ⚠️ IMPORTANT: Cette protection repose sur l'analyse textuelle du goal.
    Si task.goal est vide ou None, la protection est inefficace.
    Pour une protection robuste, task.goal doit toujours contenir du texte.
    """
```

---

## 📝 Annexes

### Fichiers Analysés

1. ✅ `domain/entities/task.py` - Définition et validation
2. ✅ `data/yaml_parser.py` - Parser standard
3. ✅ `data/flex_yalm_parser.py` - Parser flexible
4. ✅ `domain/services/executor_service.py` - Exécuteur
5. ✅ `domain/services/task_logic_handler.py` - Handler logique
6. ✅ `core/context_bridge.py` - Bridge contextuel
7. ✅ `core/guardrail.py` - Garde-fous
8. ✅ `tests/test_flex_yalm_parser.py` - Tests
9. ✅ `domain/entities/mission.py` - Sérialisation mission

### Méthodologie

- **Recherche sémantique** : "Where is goal field used"
- **Grep pattern** : `\.goal`, `task\.goal`, `task\[.goal\]`
- **Lecture exhaustive** : Fichiers clés complets
- **Analyse de flux** : De parsing → validation → exécution → sérialisation

---

**Fin du rapport d'audit**

