# 🔍 Audit de la Logique d'Écriture — AIHomeCoder V1
**Rapport d'analyse : Diagnostic de `task_apply_writes`**

---

## 📋 Métadonnées de l'Audit

- **Date :** 2025-11-02
- **Auditeur :** Cursor (Agent Pré-Humain)
- **Mission audité :** `cursor_audit.yaml`
- **Mode :** READ_ONLY_ANALYSIS
- **Objectif :** Comprendre pourquoi `task_apply_writes` peut être exécutée sans logique spécifique

---

## 🎯 Résumé Exécutif

### Problème Identifié

La tâche `task_apply_writes` dispose d'une implémentation complète et fonctionnelle dans `domain/services/task_logic_handler.py` (fonction `task_apply_writes`, lignes 782-1361). Cependant, **il existe une incohérence dans la logique de dispatch** qui peut empêcher son exécution correcte dans certains cas.

### Conclusion Principale

✅ **La fonction `task_apply_writes` existe et est complète**  
⚠️ **Le dispatcher présente une incohérence de routage**  
✅ **Aucun problème identifié au niveau du guardrail ou du workspace**

---

## 🔬 Analyse Détaillée

### 1. Architecture du Dispatcher

**Fichier :** `domain/services/task_logic_handler.py`  
**Méthode :** `TaskLogicHandler.execute()` (lignes 48-78)

#### Logique de Routage Actuelle

```python
def execute(self, task, mission):
    ttype = (task.task_type or "generic").lower()
    task_name = (task.name or "").lower()
    
    # Dispatch par nom de tâche (prioritaire pour les tâches spécifiques)
    if task_name == "task_gather_overview" or ttype in {"read", "gather_overview"}:
        # ... routage task_gather_overview
    elif task_name == "task_generate_report" or ttype in {"report", "generate_report"}:
        # ... routage task_generate_report
    
    # Dispatch par type de tâche (pour compatibilité)
    elif ttype == "analysis":
        # ... routage analysis
    elif ttype in {"task_apply_writes", "apply_writes"}:  # ⚠️ PROBLÈME ICI
        context = self._build_execution_context(task, mission)
        return task_apply_writes(params, context)
    
    else:
        return f"[INFO] Tâche '{task.name}' exécutée sans logique spécifique."
```

#### ⚠️ Problème Identifié : Incohérence de Routage

**Observation critique :**

1. **Pour `task_gather_overview` et `task_generate_report`** (lignes 55, 58) :
   - Le dispatcher vérifie **à la fois le nom ET le type**
   - Format : `task_name == "..." OR ttype in {...}`

2. **Pour `task_apply_writes`** (ligne 72) :
   - Le dispatcher vérifie **uniquement le type**
   - Format : `ttype in {"task_apply_writes", "apply_writes"}`

**Conséquence :**

Si une tâche est définie avec :
- `name="task_apply_writes"` 
- `task_type="generic"` (ou autre valeur non correspondante)

Elle ne sera **pas routée** vers `task_apply_writes()` mais tombera dans le fallback (ligne 78) :
```python
return f"[INFO] Tâche '{task.name}' exécutée sans logique spécifique."
```

### 2. Analyse de la Fonction `task_apply_writes`

**Fichier :** `domain/services/task_logic_handler.py`  
**Fonction :** `task_apply_writes()` (lignes 782-1361)

#### ✅ Points Positifs

1. **Implémentation Complète :**
   - Gestion des plans inline et externes (lignes 856-948)
   - Support de multiples actions : `overwrite`, `append`, `insert_before`, `insert_after`, `replace_block` (lignes 1157-1248)
   - Mode dry-run intégré (ligne 978)
   - Gestion d'encodage configurable (lignes 979-983)
   - Intégration complète avec guardrail (ligne 831, 904, 1080, etc.)

2. **Intégration ContextBridge :**
   - Diagnostics publiés à chaque étape (lignes 1025-1355)
   - Enregistrement des sorties dans context_bridge (lignes 1335-1342)
   - Rapports détaillés de chaque changement (lignes 1039-1276)

3. **Gestion des Erreurs :**
   - Validation du plan YAML (lignes 949-976)
   - Validation de chaque changement (lignes 1049-1112)
   - Messages d'erreur explicites (exemples : lignes 874, 950, 965)

4. **Rapport d'Exécution :**
   - Génération automatique d'un rapport Markdown (lignes 1280-1321)
   - Statistiques complètes (applied_changes, dry_run_changes, errors)
   - Format structuré et exploitable

#### ⚠️ Points d'Attention

1. **Dépendance au Paramètre `plan_path` :**
   - Si aucun plan n'est fourni (ni inline, ni via `plan_path`), la fonction retourne une erreur (lignes 872-885)
   - Ce comportement est correct mais peut expliquer des échecs silencieux si le plan n'est pas correctement transmis

2. **Mode Dry-Run :**
   - Par défaut, `dry_run=False` (ligne 978)
   - Si `dry_run=True` dans les paramètres ou le plan, aucun fichier ne sera écrit (comportement attendu mais peut être source de confusion)

### 3. Analyse du Parsing YAML

**Fichier :** `data/yaml_parser.py`  
**Méthode :** `_build_mission()` (lignes 78-154)

#### Extraction du `task_type`

```python
task_type = (
    task_data.get("type")
    or task_data.get("task_type")
    or task_id
    or "generic"
)
```

**Analyse :**

✅ Le parser cherche le `task_type` dans plusieurs champs (ordre de priorité) :
1. `type` (champ direct)
2. `task_type` (champ explicite)
3. `id` (fallback)
4. `"generic"` (défaut)

**Risque identifié :**

Si une mission définit une tâche avec :
```yaml
tasks:
  - name: "task_apply_writes"
    goal: "..."
    # Pas de champ 'type' ni 'task_type'
    id: "my_custom_id"
```

Le `task_type` sera `"my_custom_id"` et ne correspondra pas à `"task_apply_writes"` dans le dispatcher, causant un routage vers le fallback.

**Exemple réel :**
Le fichier `config/prompts/mission_apply_changes.yaml` définit correctement :
```yaml
- id: "apply_writes"
  task_type: "task_apply_writes"  # ✅ Correct
```

### 4. Analyse du Workspace et Context

**Fichier :** `domain/services/task_logic_handler.py`  
**Méthode :** `_build_execution_context()` (lignes 153-198)

#### ✅ Points Positifs

1. **Résolution du Workspace :**
   - Cherche dans plusieurs sources : `params`, `context_section`, `metadata` (lignes 160-177)
   - Résolution des placeholders (ligne 168)
   - Gestion des chemins relatifs/absolus (lignes 173-177)

2. **Variables et Placeholders :**
   - Collection depuis `params` et `context_section` (lignes 200-206)
   - Résolution récursive dans les structures complexes (lignes 19-37)

3. **Intégration des Outils :**
   - Fournit `file_manager`, `guardrail`, `context_bridge` dans le contexte (lignes 195-197)

**Aucun problème identifié** dans la construction du contexte d'exécution.

### 5. Analyse du Guardrail

**Fichier :** `core/guardrail.py`

#### ✅ Protection des Chemins Sanctuaires

1. **Vérification avant Écriture :**
   - `guardrail.check_path()` appelé avant chaque opération (lignes 826, 831, 904, etc.)
   - `GuardrailError` levée si chemin protégé (lignes 55-59)

2. **Intégration dans FileManager :**
   - `file_manager.write_file()` vérifie automatiquement le guardrail (lignes 59-61 de `file_manager.py`)

**Aucun problème identifié** qui bloquerait l'écriture légitime.

#### ⚠️ Mode READ_ONLY

Une fonction `enforce_task_restrictions()` existe (ligne 105) pour bloquer les opérations d'écriture en mode `read_only`, mais elle n'est **pas appelée** dans le flux d'exécution de `task_apply_writes`.

**Note :** Ce n'est pas un problème critique car le guardrail vérifie déjà les chemins, et le mode est géré au niveau du contexte de la mission.

---

## 📊 Diagnostic Final

### Scénarios de Défaillance

#### Scénario 1 : Routage Incorrect (PROBABLE)

**Cause :** Incohérence dans le dispatcher  
**Condition :** `task.task_type != "task_apply_writes" AND task.task_type != "apply_writes"`  
**Résultat :** Fallback → message `"[INFO] Tâche 'task_apply_writes' exécutée sans logique spécifique."`

**Exemple :**
```yaml
tasks:
  - name: "task_apply_writes"
    goal: "Appliquer les modifications"
    type: "generic"  # ❌ Mauvais type
```

#### Scénario 2 : Plan Manquant

**Cause :** Paramètre `plan_path` manquant ou invalide  
**Condition :** Aucun plan inline fourni ET `plan_path` non défini/invalide  
**Résultat :** Retour d'erreur `"[ERROR] task_apply_writes: missing plan_path or inline plan."`

**Note :** Ce comportement est correct mais peut donner l'impression d'un échec silencieux.

#### Scénario 3 : Mode Dry-Run

**Cause :** Paramètre `dry_run=True`  
**Condition :** Dry-run activé dans les paramètres ou le plan  
**Résultat :** Aucun fichier écrit (comportement attendu), message `"[DRY] Plan applique : 0 change(s), N en simulation"`

### Scénarios de Succès

#### ✅ Routage Correct

```yaml
tasks:
  - name: "Appliquer les modifications"
    task_type: "task_apply_writes"  # ✅ Correct
    parameters:
      plan_path: "plans/write_plan.yaml"
```

#### ✅ Plan Inline

```yaml
tasks:
  - name: "task_apply_writes"
    task_type: "task_apply_writes"
    parameters:
      plan:
        changes:
          - file: "test.txt"
            action: "overwrite"
            content: "Hello World"
```

---

## 🔧 Recommandations de Correction

### Correction Minimale (Prioritaire)

**Fichier :** `domain/services/task_logic_handler.py`  
**Ligne :** 72

**Avant :**
```python
elif ttype in {"task_apply_writes", "apply_writes"}:
    context = self._build_execution_context(task, mission)
    return task_apply_writes(params, context)
```

**Après (pour cohérence avec les autres tâches) :**
```python
elif task_name == "task_apply_writes" or ttype in {"task_apply_writes", "apply_writes"}:
    context = self._build_execution_context(task, mission)
    return task_apply_writes(params, context)
```

**Bénéfice :** Routage correct même si `task_type` est mal défini mais `name="task_apply_writes"`.

### Amélioration Supplémentaire (Recommandée)

Harmoniser toutes les tâches pour vérifier à la fois le nom ET le type :

```python
# Dispatch par nom OU type de tâche (cohérent)
if task_name == "task_gather_overview" or ttype in {"read", "gather_overview"}:
    # ...
elif task_name == "task_generate_report" or ttype in {"report", "generate_report"}:
    # ...
elif task_name == "task_apply_writes" or ttype in {"task_apply_writes", "apply_writes"}:
    # ...
elif task_name == "task_tree_scan" or ttype in {"tree_scan", "tree"}:
    # ...
elif task_name == "task_gather_documents" or ttype in {"task_gather_documents", "gather_documents"}:
    # ...
```

### Validation Améliorée

Ajouter une validation dans le YAML parser pour s'assurer que les tâches critiques ont le bon `task_type` :

```python
# Dans yaml_parser.py, après création de la tâche
if task_name.lower() == "task_apply_writes" and task_type != "task_apply_writes":
    logger.warning(
        f"Task '{task_name}' should have task_type='task_apply_writes' "
        f"but has '{task_type}' instead"
    )
```

---

## 📝 Fonctions Concernées

### Fichiers Modifiés Nécessaires

1. **`domain/services/task_logic_handler.py`**
   - Méthode `execute()` (ligne 72)
   - Impact : Correction minimale d'une ligne

### Fichiers à Examiner (Pas de Modification Nécessaire)

1. **`domain/services/task_logic_handler.py`**
   - Fonction `task_apply_writes()` (lignes 782-1361) — ✅ Complète
   - Méthode `_build_execution_context()` (lignes 153-198) — ✅ Correcte

2. **`data/yaml_parser.py`**
   - Méthode `_build_mission()` (lignes 78-154) — ✅ Correcte (mais amélioration possible)

3. **`core/guardrail.py`**
   - Classe `Guardrail` — ✅ Fonctionnelle

4. **`core/file_manager.py`**
   - Classe `FileManager` — ✅ Fonctionnelle

---

## 🛡️ Impact sur la Sécurité

### Aucun Impact Négatif

Les modifications recommandées n'affectent pas la sécurité du système :

1. ✅ Le guardrail continue de fonctionner normalement
2. ✅ Les vérifications de chemin restent en place
3. ✅ Aucun contournement des protections introduit
4. ✅ La logique d'écriture reste inchangée

### Amélioration de la Robustesse

La correction proposée améliore la robustesse en permettant le routage même si le `task_type` est mal défini, à condition que le nom de la tâche soit correct.

---

## ✅ Compatibilité V2

### Analyse de Compatibilité

L'implémentation actuelle de `task_apply_writes` est **déjà compatible V2** :

1. ✅ Utilise `context_bridge` pour les diagnostics
2. ✅ Supporte les variables via `_resolve_placeholders()`
3. ✅ Intègre le guardrail correctement
4. ✅ Génère des rapports structurés

**Aucune modification nécessaire** pour la compatibilité V2.

---

## 📋 Checklist de Validation

- [x] Fonction `task_apply_writes` existe et est complète
- [x] Dispatcher contient une branche pour `task_apply_writes`
- [x] Incohérence identifiée dans la logique de routage
- [x] Workspace correctement géré dans `_build_execution_context()`
- [x] Guardrail fonctionne correctement
- [x] Aucun problème de sécurité identifié
- [x] Compatibilité V2 confirmée

---

## 🎯 Conclusion

### Origine Exacte du Problème

**Problème identifié :** Incohérence dans la logique de dispatch de `TaskLogicHandler.execute()`

**Symptôme :** La tâche `task_apply_writes` peut être exécutée sans logique spécifique si son `task_type` n'est pas exactement `"task_apply_writes"` ou `"apply_writes"`.

**Cause racine :** Le dispatcher vérifie uniquement le `task_type` pour `task_apply_writes`, alors que d'autres tâches (`task_gather_overview`, `task_generate_report`) vérifient à la fois le nom ET le type.

### Modifications Minimales Nécessaires

**Correction requise :** 1 ligne modifiée dans `domain/services/task_logic_handler.py` (ligne 72)

**Code :**
```python
# Avant
elif ttype in {"task_apply_writes", "apply_writes"}:

# Après
elif task_name == "task_apply_writes" or ttype in {"task_apply_writes", "apply_writes"}:
```

### Fonctions Concernées

1. **`TaskLogicHandler.execute()`** — À modifier (ligne 72)
2. **`task_apply_writes()`** — Aucune modification nécessaire (déjà complète)

### État de la Sécurité

✅ **Aucun compromis de sécurité**  
✅ **Le guardrail reste intact**  
✅ **La lecture n'est pas affectée**  
✅ **Le sanctuaire Hive reste protégé**

---

**Fin du rapport d'audit**  
*Rapport généré par Cursor (Agent Pré-Humain) — 2025-11-02*

