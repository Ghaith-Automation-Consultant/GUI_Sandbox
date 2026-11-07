# GUI Sandbox — Guide Utilisateur

## 1. Présentation

Le GUI Sandbox est une application Windows qui reproduit fidèlement l'interface SAP GUI et son arbre de contrôles COM, **sans nécessiter de connexion à un système SAP réel**.

Il permet de :

- **Développer des scripts RPA** (Python, VBScript, UiPath) contre des écrans SAP réalistes, hors ligne.
- **Rejouer des captures d'écrans** issues de sessions SAP réelles (fichiers JSON).
- **Tester l'automatisation** avec la même API COM que le vrai SAP (`GetObject("SAPGUI")`).
- **Former** des développeurs et consultants SAP sans risque sur les données de production.

L'application expose trois interfaces d'automatisation : API Python in-process, API HTTP JSON, et pont COM/ROT Windows.

---

## 2. Prérequis

| Composant | Version minimale |
|-----------|-----------------|
| Système d'exploitation | Windows 10 ou supérieur |
| Python | 3.10+ (testé avec 3.13) |
| pip | Inclus avec Python |

Bibliothèques Python requises (installées automatiquement) :

- **PySide6** — interface graphique Qt
- **pywin32** — pont COM Windows
- **pandas** — manipulation de données tabulaires

---

## 3. Installation

```bash
# Cloner le dépôt
git clone <url-du-depot> gui_sandbox
cd gui_sandbox

# Créer un environnement virtuel (recommandé)
python -m venv .venv
.venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt
```

> **Note :** Sur certaines machines, `pywin32` nécessite d'exécuter `python Scripts/pywin32_postinstall.py -install` après l'installation.

---

## 4. Lancement

### Avec Python directement

```bash
python main.py
```

### Avec le script batch

```bash
run_sandbox.bat
```

Au démarrage, l'application :

1. Affiche l'écran de connexion (`screens/00_LOGON.json`, transaction `S000`). Connectez-vous avec le mandant `000`, l'utilisateur `USER_STANDARD` et le mot de passe `sandbox` (définis dans `engine/logon.py`), puis appuyez sur Entrée. `python main.py --no-logon` ouvre directement l'écran Easy Access, et `/nend` dans la zone de commande vous déconnecte.
2. Affiche la fenêtre SAP GUI avec menus, barres d'outils, arbre de navigation et zone de contenu.
3. Enregistre le pont COM dans la Running Object Table (ROT) Windows — le message `COM bridge started` apparaît dans le terminal.
4. Les scripts externes peuvent alors se connecter via `GetObject("SAPGUI")`.

---

## 5. Navigation dans l'interface

### Zone de commande (Command Field)

Le champ de commande se trouve dans la barre d'outils principale. Pour naviguer vers une transaction :

1. Cliquez dans le champ de commande (ou utilisez le raccourci clavier).
2. Tapez le code transaction (ex : `SE16`, `SM37`, `SU01`).
3. Appuyez sur **Entrée**.

L'écran correspondant est chargé automatiquement si un fichier JSON existe pour cette transaction.

### Menu Favoris

L'arbre de navigation à gauche contient :

- **Favoris** — raccourcis personnalisés vers les transactions fréquentes.
- **Menu SAP** — arborescence complète des modules SAP.

Double-cliquez sur un élément pour ouvrir la transaction correspondante.

### Barre d'outils principale

| Bouton | Action | Équivalent clavier |
|--------|--------|-------------------|
| Entrée (coche verte) | Valider la saisie | Entrée |
| Sauvegarder | Enregistrer | Ctrl+S |
| Retour | Écran précédent | F3 |
| Quitter | Fermer la transaction | Shift+F3 |
| Annuler | Annuler l'opération | F12 |

### Barre de statut

En bas de la fenêtre, la barre de statut affiche les messages système (succès, avertissements, erreurs) ainsi que les informations de la session en cours (système, mandant, utilisateur).

---

## 6. Transactions disponibles

Le sandbox inclut 15 écrans d'exemple générés par `tools/generate_screens.py`, avec des données fictives :

### S000 — Écran de connexion

Mandant, utilisateur, mot de passe et langue de connexion, avec les mêmes ID de champs que l'écran de connexion SAP GUI (`txtRSYST-MANDT`, `txtRSYST-BNAME`, `pwdRSYST-BCODE`, `txtRSYST-LANGU`). Un script peut donc s'y connecter comme sur un vrai système.

- `00_LOGON.json` — écran de connexion

### SESSION_MANAGER — Easy Access

L'écran principal SAP avec l'arbre de navigation (Favoris + Menu SAP). C'est l'écran affiché après la connexion.

- `01_SESSION_MANAGER.json` — écran initial

### SE16 — Data Browser

Navigation dans les tables. Trois étapes : saisie du nom de table, écran de sélection (filtres), affichage des résultats.

| Fichier | Description |
|---------|-------------|
| `02_SE16_initial.json` | Saisie du nom de table |
| `03_SE16_SFLIGHT_selection_screen.json` | Filtres pour SFLIGHT |
| `04_SE16_SFLIGHT_results.json` | Résultats SFLIGHT (GridView ALV) |

### SE16N — General Table Display

- `05_SE16N_initial.json` — écran initial
- `06_SE16N_SFLIGHT_selection.json` — sélection pour la table SFLIGHT

### SE38 — Éditeur ABAP

- `07_SE38_initial.json` — écran initial
- `08_SE38_source_ZSBX_DEMO.json` — code source du programme ZSBX_DEMO
- `09_SE38_attributes_ZSBX_DEMO.json` — attributs du programme ZSBX_DEMO

### SM37 — Suivi des jobs

- `10_SM37_initial.json` — écran de sélection des jobs

### SU01 — Gestion des utilisateurs

- `11_SU01_initial.json` — écran initial

### VA03 — Affichage de commande client

- `12_VA03_initial.json` — écran initial
- `13_VA03_overview.json` — vue d'ensemble de la commande

### MM03 — Affichage d'article

- `14_MM03_initial.json` — écran initial

---

## 7. Utilisation avec des scripts d'automatisation

Le sandbox expose quatre interfaces d'automatisation. Toutes partagent la même arborescence de contrôles sous-jacente.

### 7.1 Python in-process

Pour les scripts exécutés dans le même processus que le sandbox :

```python
from bridge import SandboxSession
from engine import load_screen

session = SandboxSession(load_screen("screens/02_SE16_initial.json"))

# Syntaxe identique au SAP GUI Scripting
session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "SFLIGHT"
session.findById("wnd[0]").sendVKey(0)

# Lire les informations de session
print(session.Info.Transaction)  # "SE16"
print(session.Info.User)         # "USER_STANDARD"

# Consulter le journal d'actions
for entry in session.recorder.entries():
    print(entry)
```

### 7.2 Python COM (processus externe)

Pour les scripts exécutés dans un processus séparé. Le sandbox s'enregistre dans la ROT sous le moniker `SAPGUI` — **identique au vrai SAP GUI** :

```python
import win32com.client

sap = win32com.client.GetObject("SAPGUI")
app = sap.GetScriptingEngine
session = app.Children(0).Children(0)

# Lire un champ
field = session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME")
print(field.Text)

# Écrire dans un champ
field.Text = "SFLIGHT"

# Appuyer sur Entrée
session.findById("wnd[0]").sendVKey(0)

# Informations de session
print(session.Info.Transaction)  # "SE16"
print(session.Info.User)         # "USER_STANDARD"
```

> **Important :** Si SAP Logon est déjà en cours d'exécution, ses entrées ROT masquent celles du sandbox. Fermez SAP Logon avant de tester, ou utilisez un moniker différent.

### 7.3 VBScript

```vbs
Set sap = GetObject("SAPGUI")
Set app = sap.GetScriptingEngine
Set session = app.Children(0).Children(0)

session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "SFLIGHT"
session.findById("wnd[0]").sendVKey 0

MsgBox session.Info.Transaction  ' Affiche "SE16"
```

Exécution : `cscript tests\test_com_bridge.vbs`

### 7.4 API HTTP JSON

Pour l'accès depuis n'importe quel langage (UiPath, JavaScript, curl, etc.) :

```python
# === Côté serveur (dans le sandbox) ===
from bridge import start_server
from engine import load_screen

server = start_server(load_screen("screens/02_SE16_initial.json"), port=7654)

# === Côté client (script externe) ===
from bridge import RemoteSession

session = RemoteSession("http://127.0.0.1:7654")
session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "SFLIGHT"
session.findById("wnd[0]").sendVKey(0)
```

**Endpoints disponibles :**

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/info` | GET | Métadonnées de session (transaction, utilisateur, écran) |
| `/tree` | GET | Arbre de contrôles complet (JSON imbriqué) |
| `/controls` | GET | Liste plate de tous les contrôles |
| `/log` | GET | Journal des actions enregistrées |
| `/findById` | POST | `{"path": "wnd[0]/usr/ctxtFOO"}` — recherche un contrôle |
| `/action` | POST | `{"path": "...", "action": "setText", "value": "X"}` — exécute une action |
| `/loadScreen` | POST | `{"file": "screens/02_SE16_initial.json"}` — charge un écran |

---

## 8. Capture de nouveaux écrans

Pour enrichir le sandbox avec de nouveaux écrans SAP, vous devez disposer d'un accès à un vrai système SAP avec le scripting activé.

### Capture manuelle d'un écran

```bash
python tools/sap_inspect.py --out screens/mon_ecran.json
```

Ce script :
1. Se connecte à la session SAP GUI active via `GetObject("SAPGUI")`.
2. Parcourt l'arbre de contrôles complet de l'écran courant.
3. Exporte toutes les propriétés (ID, type, texte, état, position, taille) en JSON.

### Capture automatisée multi-écrans

```bash
python tools/sap_scenarios.py all
python tools/sap_scenarios.py SE16 --table MARA
```

Le script `sap_scenarios.py` automatise la navigation entre transactions et capture chaque écran rencontré. Il met à jour le manifeste `screens/_manifest.json`.

### Connexion à SAP

```bash
python tools/sap_connect.py
```

Fonctions utilitaires :
- `get_session()` — se connecte à une session SAP GUI active.
- `launch_and_login()` — lance SAP Logon et remplit l'écran de connexion automatiquement.

---

## 9. Diagnostics

### Vérification de la ROT (Running Object Table)

```bash
python tools/diag_rot.py
```

Ce script affiche les entrées ROT enregistrées par le sandbox et vérifie que `GetObject("SAPGUI")` peut les atteindre. Utile pour diagnostiquer les problèmes de connexion COM.

### Problèmes courants

| Symptôme | Cause probable | Solution |
|----------|---------------|----------|
| `GetObject("SAPGUI")` échoue | Le sandbox n'est pas lancé, ou SAP Logon masque les entrées | Lancez le sandbox ; fermez SAP Logon |
| `Membre introuvable` sur `coll(0)` | Version obsolète de `com_server.py` | Vérifiez que `ComCollection` a la méthode `_value_` |
| `Count()` renvoie `int is not callable` | `Count` est une propriété, pas une méthode | Utilisez `children.Count` sans parenthèses |
| L'interface ne s'affiche pas correctement | Style Fusion non appliqué | Vérifiez que `app.setStyle("Fusion")` est appelé |

### Exécution des tests

```bash
python -m pytest tests/ -q
```

La suite de tests couvre le moteur de contrôles, l'interface graphique, les tests end-to-end et le pont COM.

---

## 10. Limitations connues

- **Écrans statiques** — Le sandbox charge des captures JSON figées. Il ne simule pas la logique métier SAP (pas de navigation dynamique entre écrans basée sur les données saisies).
- **Pas de BAPI/RFC** — Aucune communication avec un backend SAP. Les appels de fonctions distantes ne sont pas supportés.
- **Pas de persistance** — Les modifications faites via les scripts (setText, etc.) sont en mémoire uniquement et perdues à la fermeture.
- **Session unique** — Le sandbox expose une seule connexion avec une seule session (con[0]/ses[0]).
- **Pas de popups modales** — Les fenêtres `wnd[1]`, `wnd[2]` ne sont pas encore gérées.
- **Pas de gestion du focus clavier** — La navigation par tabulation entre champs n'est pas implémentée.
- **Données figées** — Les résultats de tables (SE16, SE16N) sont ceux capturés au moment de la capture, pas des données live.

---

## Annexe — Structure des fichiers écran (JSON)

Chaque fichier JSON dans `screens/` suit cette structure :

```json
{
  "metadata": {
    "transaction": "SE16",
    "program": "SAPLSE16",
    "screen": 100,
    "system": "SBX",
    "user": "USER_STANDARD",
    "client": "200"
  },
  "controls": {
    "id": "/app/con[0]/ses[0]/wnd[0]",
    "type": "GuiMainWindow",
    "name": "wnd[0]",
    "text": "Data Browser: Table ...",
    "children": [
      {
        "id": "/app/con[0]/ses[0]/wnd[0]/usr",
        "type": "GuiUserArea",
        "children": [ ... ]
      }
    ]
  }
}
```

Les champs principaux de chaque contrôle :

| Champ | Description |
|-------|-------------|
| `id` | Chemin SAP complet (ex : `/app/con[0]/ses[0]/wnd[0]/usr/ctxtFOO`) |
| `type` | Type COM SAP (ex : `GuiTextField`, `GuiButton`, `GuiGridView`) |
| `name` | Nom court du contrôle |
| `text` | Texte affiché / valeur courante |
| `enabled` | Contrôle actif ou grisé |
| `changeable` | Contrôle modifiable |
| `children` | Liste des contrôles enfants |
