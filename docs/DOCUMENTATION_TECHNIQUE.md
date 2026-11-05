# Documentation Technique — GUI Sandbox

## 1. Vue d'ensemble

Le GUI Sandbox est une application Windows qui reproduit l'interface SAP GUI et son modele de controles COM. Il permet de developper, tester et former a l'automatisation SAP sans connexion a un systeme SAP reel.

L'architecture repose sur trois couches independantes :

```
Layer A — Visual Shell      main.py, ui/         Interface PySide6/Qt
Layer B — Control Tree       engine/              Modele logique (source de verite)
Layer C — Scripting Bridge   bridge/              Pont COM + API Python + API HTTP
```

**Layer B est la source de verite.** Layer A la rend visible. Layer C l'expose aux scripts.

---

## 2. Architecture detaillee

### 2.1 Layer A — Visual Shell

**Fichiers :** `main.py`, `ui/styles.py`, `ui/screen_renderer.py`, `ui/widget_factory.py`, `ui/transaction_router.py`

`MainWindow` (QMainWindow) construit le chrome SAP :
- Barre de menus, barre d'outils principale (champ de commande), bandeau titre, barre d'outils contextuelle, panneau workspace, barre de statut.
- Les toolbars sont retirees du systeme natif Qt et re-parentees dans un `QVBoxLayout` pour forcer l'ordre d'empilage SAP.
- `app.setStyle("Fusion")` est obligatoire pour le rendu SAP.

**ScreenRenderer** recoit un objet `Session` (Layer B), parcourt l'arbre de controles et cree les widgets Qt correspondants via `WidgetFactory`.

**TransactionRouter** gere la navigation entre transactions : il recoit un code transaction, charge l'ecran JSON correspondant, construit la Session et la transmet au renderer.

**Palette de couleurs :**

| Element | Couleur |
|---------|---------|
| Fond fenetre/menus | `#E6EEF7` |
| Fond barres d'outils | `#D5DEE8` |
| Degradé bandeau | `#DCE6F2` -> `#B7C9DC` |
| Fond panneau | `#F4F6F9` |
| Selection | `#C7D6EA` |
| Bordures | `#9FB2C6` |

**Police :** Segoe UI / Arial, 12px pour le chrome, 14px bold italic pour le bandeau titre.

---

### 2.2 Layer B — Control Tree Engine

**Fichiers :** `engine/control.py`, `engine/session.py`, `engine/loader.py`, `engine/transactions/`

#### Hierarchie des classes de controles

```
Control (base)
  |-- Container
  |     |-- UserArea (GuiUserArea)
  |     |-- Menubar (GuiMenubar)
  |     |-- Menu (GuiMenu)
  |     |-- Toolbar (GuiToolbar)
  |     |-- TabStrip (GuiTabStrip)
  |     |-- Tab (GuiTab)
  |     |-- Shell (GuiShell)
  |     |-- Splitter (GuiSplitterContainer)
  |     |-- ScrollContainer (GuiScrollContainer)
  |     |-- SimpleContainer (GuiSimpleContainer)
  |     |-- Box (GuiBox)
  |     |-- TableRow (TableRow)
  |     |-- TableControl (GuiTableControl)
  |     |-- GridView (GuiGridView)
  |     |-- Window (GuiMainWindow)
  |     '-- Session (GuiSession)
  |-- TextField (GuiTextField)
  |-- ComboTextField (GuiCTextField)
  |-- PasswordField (GuiPasswordField)
  |-- Label (GuiLabel)
  |-- Button (GuiButton)
  |-- RadioButton (GuiRadioButton)
  |-- CheckBox (GuiCheckBox)
  |-- ComboBox (GuiComboBox)
  |-- CommandField (GuiOkCodeField)
  |-- StatusBar (GuiStatusbar)
  |-- MenuItem (GuiMenuItem)
  |-- Titlebar (GuiTitlebar)
  |-- Tree (GuiTree)
  |-- Chart (GuiSAPChart)
  '-- TableCell (TableCell)
```

#### Classe Control (base)

Attributs principaux :
- `id` (str) — chemin SAP complet, ex : `/app/con[0]/ses[0]/wnd[0]/usr/ctxtFOO`
- `name` (str) — nom court
- `text` (str) — texte affiche / valeur courante
- `tooltip`, `enabled`, `changeable`, `visible`, `required` — etats
- `max_length`, `left`, `top`, `width`, `height` — dimensions
- `parent` (Control | None) — parent dans l'arbre
- `children` (list[Control]) — enfants
- `events` (dict[str, Callable]) — gestionnaires d'evenements

Methodes :
- `add_child(child)` / `remove_child(child)` — gestion de l'arbre
- `find_control(id)` — recherche en profondeur par ID
- `all_controls()` — self + tous les descendants
- `on(event, handler)` / `trigger(event, *args)` — systeme d'evenements
- `value` (property r/w) — alias vers `text` avec declenchement de l'evenement `change`
- `press()` / `select()` — raccourcis d'action

#### Classe Session

Objet racine du modele logique. Attributs specifiques :
- `info` (SessionInfo) — metadata : `system_name`, `client`, `user`, `transaction`, `program`, `screen_number`
- `_registry` (dict[str, Control]) — index plat pour lookup `findById()` en O(1)

Methodes :
- `findById(path)` — API principale. Accepte les chemins complets (`/app/con[0]/ses[0]/wnd[0]/...`) et courts (`wnd[0]/...`). Consulte d'abord le `_registry`, puis fait un tree-walk en fallback. Leve `RuntimeError` si le controle n'est pas trouve.
- `add_window(window)` / `get_window(index)` / `close_window(index)` — gestion des fenetres
- `rebuild_registry()` — reconstruit l'index complet
- `start_transaction(tcode)` — change le code transaction et declenche l'evenement `transaction_change`
- `send_vkey(key, window_index)` — envoie une touche virtuelle
- `set_status(message, type)` — ecrit dans la barre de statut
- `active_window` (property) — fenetre avec l'index le plus eleve

#### Classe Window

Represente une fenetre SAP (`wnd[0]` = principale, `wnd[1+]` = modales).
- `send_vkey(key)` — declenche l'evenement `vkey`
- `command_field` / `status_bar` / `user_area` — acces rapide aux zones standard

#### Chargement des ecrans JSON (loader.py)

`load_screen(path)` :
1. Lit le fichier JSON
2. Extrait les metadata (transaction, systeme, client, utilisateur)
3. Construit recursivement l'arbre de controles via `build_tree()`
4. Utilise `_TYPE_MAP` pour instancier la classe Python correspondant a chaque type SAP COM
5. Retourne un objet `Session` pret a l'emploi

`_TYPE_MAP` mappe les noms de types SAP COM vers les classes Python :

| Type SAP | Classe Python |
|----------|--------------|
| `GuiTextField` | `TextField` |
| `GuiCTextField` | `ComboTextField` |
| `GuiButton` | `Button` |
| `GuiLabel` | `Label` |
| `GuiMainWindow` | `Window` |
| `GuiSession` | `Session` |
| `GuiGridView` | `GridView` |
| `GuiTableControl` | `TableControl` |
| ... | (30+ mappings au total) |

#### Transactions programmatiques

`engine/transactions/base.py` definit `BaseTransaction` :
- Cree automatiquement une Session avec Window, Toolbar (+ CommandField), StatusBar, UserArea
- La sous-classe implemente `_build()` pour peupler le UserArea

Sous-classes :
- `SessionManagerScreen` — ecran d'accueil Easy Access avec arbre de navigation
- `SE16InitialScreen` — ecran initial du Data Browser

---

### 2.3 Layer C — Scripting Bridge

**Fichiers :** `bridge/com_server.py`, `bridge/com_thread.py`, `bridge/proxy.py`, `bridge/server.py`, `bridge/client.py`, `bridge/recorder.py`

Le pont offre trois mecanismes d'acces a la meme Session (Layer B) :

#### 2.3.1 Pont COM/ROT (com_server.py + com_thread.py)

Enregistre des objets COM dans la Running Object Table (ROT) de Windows. Les scripts externes accedent a la sandbox via `GetObject("SAPGUI")`, exactement comme avec le vrai SAP GUI.

**Hierarchie COM :**

```
GetObject("SAPGUI")          ->  ComSapGui
  .GetScriptingEngine         ->  ComApplication
    .Children(0)              ->  ComConnection
      .Children(0)            ->  ComSession
        .findById(path)       ->  ComControl
        .Info                 ->  ComSessionInfo
        .Children             ->  ComCollection
```

**Classes COM et leur role :**

| Classe | Interface SAP | Proprietes / Methodes |
|--------|--------------|----------------------|
| `ComSapGui` | Point d'entree ROT | `GetScriptingEngine`, `Id` |
| `ComApplication` | GuiApplication | `Children`, `Connections`, `MajorVersion`, `MinorVersion`, `HistoryEnabled` |
| `ComConnection` | GuiConnection | `Children`, `Sessions`, `Description`, `DisabledByServer` |
| `ComSession` | GuiSession | `findById()`, `StartTransaction()`, `sendVKey()`, `Info`, `ActiveWindow`, `Children`, `Busy` |
| `ComSessionInfo` | GuiSessionInfo | `Transaction`, `Program`, `ScreenNumber`, `SystemName`, `Client`, `User`, `Language` |
| `ComControl` | Tout controle | `Id`, `Type`, `TypeAsNumber`, `Name`, `Text`, `Enabled`, `Changeable`, `Visible`, `Children`, `findById()`, `Press()`, `Select()`, `sendVKey()`, `GetCellValue()`, `RowCount`, `ColumnCount` |
| `ComCollection` | Collection indexee | `Count` (property), `Item(i)`, `_value_(i)` pour `coll(i)` |

**Details d'implementation pywin32 :**

Chaque classe COM declare :
- `_public_methods_` — methodes appelables via COM
- `_public_attrs_` — proprietes lisibles via COM
- `_readonly_attrs_` — proprietes en lecture seule

Points critiques :
- `ComCollection.Count` est une `@property`, pas une methode. Si `Count` est dans `_public_methods_` ET `_public_attrs_`, pywin32 (CDispatch) auto-evalue la methode a l'acces property, retournant un int ; l'appel `Count()` echoue alors avec `TypeError: 'int' object is not callable`.
- `ComCollection._value_()` mappe vers `DISPID_VALUE` (0) via `DesignatedWrapPolicy._dispid_to_get_`. C'est ce qui permet la syntaxe `coll(i)` depuis les clients COM. La directive `_com_default_method_` n'est **pas** supportee par pywin32.
- `SessionHolder` utilise un `threading.Lock` pour les echanges de session entre le thread principal (Qt) et le thread STA (COM).

**Thread STA (com_thread.py) :**

Le pont COM tourne dans un thread STA (Single-Threaded Apartment) dedie :

1. `pythoncom.CoInitialize()` — initialise le thread comme STA
2. Cree `ComSapGui`, le wrappe via `win32com.server.util.wrap()`
3. Enregistre dans la ROT sous deux monikers : `"SAPGUI"` et `"SAPGUISERVER"` (compatibilite avec differents outils de scripting)
4. Boucle de pompage de messages :
   ```python
   while WaitForSingleObject(stop_handle, 0) != WAIT_OBJECT_0:
       PumpWaitingMessages()
       MsgWaitForMultipleObjects([stop_handle], False, 50, QS_ALLINPUT)
   ```
5. A l'arret : revoque les entrees ROT, `CoUninitialize()`

La classe `ComBridge` encapsule le cycle de vie :
- `start()` — lance le thread STA, attend que l'enregistrement ROT soit termine
- `stop()` — signale l'arret via `SetEvent(stop_handle)`, join le thread
- `update_session(session)` — echange la session exposee aux clients COM (thread-safe)
- `is_running` — etat du thread

**Conflit ROT avec SAP Logon :** Si le vrai SAP Logon est en cours d'execution, il enregistre ses propres monikers `SAPGUI` / `SAPGUISERVER` qui masquent ceux de la sandbox. Solution : fermer SAP Logon avant de lancer la sandbox.

#### 2.3.2 API Python in-process (proxy.py)

`SandboxSession` enveloppe un objet `engine.Session` et expose la meme API que le COM SAP GUI Scripting, avec support PascalCase et snake_case :

```python
from bridge import SandboxSession
from engine import load_screen

session = SandboxSession(load_screen("screens/02_SE16_initial.json"))
session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "SFLIGHT"
session.findById("wnd[0]").sendVKey(0)
```

Classes :
- `SandboxSession` (alias `SessionProxy`) — racine
- `ControlProxy` — enveloppe un Control
- `ChildrenCollection`, `ColumnsCollection`, `ColumnTitlesCollection` — collections
- `SessionInfoProxy` — metadata
- `ActionRecorder` — journal d'actions horodaté

#### 2.3.3 API HTTP JSON (server.py + client.py)

Pont REST pour l'automatisation cross-process / cross-langage :

- `SandboxServer` — serveur HTTP local
- `RemoteSession` — client avec la meme API que SandboxSession

Endpoints : `/info`, `/tree`, `/controls`, `/log`, `/findById`, `/action`, `/loadScreen`

---

## 3. Format des fichiers JSON de screens

Chaque fichier dans `screens/` represente un ecran SAP capture. Structure :

```json
{
  "_label": "02_SE16_initial",
  "system": "SBX",
  "client": "000",
  "user": "USER_STANDARD",
  "transaction": "SE16",
  "program": "SAPLSETB",
  "screen": 230,
  "status": "",
  "tree": {
    "id": "/app/con[0]/ses[0]",
    "type": "GuiSession",
    "name": "ses[0]",
    "children": [
      {
        "id": "/app/con[0]/ses[0]/wnd[0]",
        "type": "GuiMainWindow",
        "name": "wnd[0]",
        "text": "Data Browser : ecran initial",
        "children": [...]
      }
    ]
  }
}
```

**Champs de metadata (niveau racine) :**

| Champ | Description |
|-------|-------------|
| `_label` | Identifiant du fichier |
| `system` | Code systeme SAP (ex : SBX) |
| `client` | Mandant SAP (ex : 000) |
| `user` | Utilisateur SAP (ex : USER_STANDARD) |
| `transaction` | Code transaction (ex : SE16) |
| `program` | Programme ABAP (ex : SAPLSETB) |
| `screen` | Numero d'ecran Dynpro |
| `status` | Message de la barre de statut |

**Champs de chaque noeud de l'arbre :**

| Champ | Type | Description |
|-------|------|-------------|
| `id` | str | Chemin SAP complet |
| `type` | str | Type COM SAP (ex : GuiTextField) |
| `name` | str | Nom court du controle |
| `text` | str | Texte affiche / valeur |
| `tooltip` | str | Info-bulle |
| `changeable` | bool | Modifiable |
| `enabled` | bool | Actif |
| `visible` | bool | Visible |
| `left`, `top`, `width`, `height` | int | Position et dimensions en pixels |
| `children` | array | Controles enfants |

---

## 4. Table de mapping des types SAP

Table complete des codes numeriques de type SAP, utilisee par `ComControl.TypeAsNumber` :

| Type SAP | Code | Classe Python |
|----------|------|--------------|
| GuiApplication | 10 | — |
| GuiConnection | 11 | — |
| GuiSession | 12 | Session |
| GuiMainWindow | 21 | Window |
| GuiModalWindow | 22 | — |
| GuiLabel | 30 | Label |
| GuiTextField | 31 | TextField |
| GuiCTextField | 32 | ComboTextField |
| GuiPasswordField | 33 | PasswordField |
| GuiComboBox | 34 | ComboBox |
| GuiOkCodeField | 35 | CommandField |
| GuiButton | 40 | Button |
| GuiCheckBox | 42 | CheckBox |
| GuiRadioButton | 43 | RadioButton |
| GuiBox | 62 | Box |
| GuiSimpleContainer | 71 | SimpleContainer |
| GuiScrollContainer | 72 | ScrollContainer |
| GuiUserArea | 74 | UserArea |
| GuiSplitterContainer | 75 | Splitter |
| GuiTableControl | 80 | TableControl |
| GuiTabStrip | 90 | TabStrip |
| GuiTab | 91 | Tab |
| GuiToolbar | 101 | Toolbar |
| GuiTitlebar | 102 | Titlebar |
| GuiStatusbar | 103 | StatusBar |
| GuiMenubar | 110 | Menubar |
| GuiMenu | 111 | Menu |
| GuiMenuItem | 112 | MenuItem |
| GuiShell | 122 | Shell |
| GuiTree | 200 | Tree |
| GuiGridView | 201 | GridView |
| GuiControl | 0 | Control |

---

## 5. Ajouter un nouvel ecran

### Capture depuis le vrai SAP

Pre-requis : acces a un systeme SAP avec le scripting active (`sapgui/user_scripting` = TRUE dans le profil).

```bash
# Capture de l'ecran courant
run_sandbox.bat inspect --out screens/25_TCODE_description.json

# Capture automatisee de plusieurs ecrans
run_sandbox.bat scenarios SE16 --table MARA
run_sandbox.bat scenarios all
```

Le script `tools/sap_inspect.py` se connecte via `GetObject("SAPGUI")`, parcourt l'arbre de controles et exporte toutes les proprietes en JSON.

### Creation manuelle

1. Creer un fichier JSON dans `screens/` en suivant le format decrit en section 3.
2. Le nom doit suivre la convention : `NN_TCODE_description.json` (NN = numero d'ordre).
3. Les types (`type`) doivent correspondre aux noms COM SAP exacts (voir section 4).
4. Les IDs (`id`) doivent suivre le format SAP : `/app/con[0]/ses[0]/wnd[0]/usr/...`.

### Creation d'une transaction programmatique

Pour un ecran avec une logique specifique (pas juste une capture statique) :

1. Creer une classe dans `engine/transactions/` qui herite de `BaseTransaction` :

```python
from .base import BaseTransaction, _WND0_ID
from engine.control import TextField, Label

class MonTransaction(BaseTransaction):
    tcode = "ZMON"
    title = "Ma Transaction Custom"

    def _build(self):
        usr_id = f"{_WND0_ID}/usr"
        lbl = Label(f"{usr_id}/lblCHAMP", name="lblCHAMP", text="Mon champ :")
        txt = TextField(f"{usr_id}/txtCHAMP", name="txtCHAMP", changeable=True)
        self.usr.add_child(lbl)
        self.usr.add_child(txt)
```

2. Exporter dans `engine/transactions/__init__.py`.
3. Ajouter le routage dans `ui/transaction_router.py`.

---

## 6. Format des identifiants SAP

Les IDs suivent le format hierarchique SAP GUI Scripting :

```
/app/con[0]/ses[0]/wnd[0]/usr/ctxtDATABROWSE-TABLENAME
|    |      |      |      |   |
|    |      |      |      |   '-- controle (prefixe + nom technique)
|    |      |      |      '------ zone : usr, tbar[N], mbar, sbar
|    |      |      '------------- fenetre (0=principale, 1+=modale)
|    |      '--------------------- session
|    '----------------------------- connexion
'---------------------------------- application
```

**Prefixes de type dans les IDs :**

| Prefixe | Type SAP |
|---------|----------|
| `ctxt` | GuiCTextField (champ avec aide a la saisie F4) |
| `txt` | GuiTextField (champ texte simple) |
| `btn` | GuiButton |
| `lbl` | GuiLabel |
| `chk` | GuiCheckBox |
| `rad` | GuiRadioButton |
| `cbo` | GuiComboBox |
| `shell` | GuiShell / GuiGridView / GuiTree |
| `sub` | Sous-ecran (GuiSimpleContainer) |
| `tab` | GuiTab / GuiTabStrip |
| `ssub` | Sous-sous-ecran |

**Zones standard d'une fenetre :**

| Zone | Description |
|------|-------------|
| `mbar` | Barre de menus |
| `tbar[0]` | Barre d'outils principale (contient `okcd` = champ de commande) |
| `tbar[1]` | Barre d'outils contextuelle |
| `titl` | Barre de titre |
| `usr` | Zone utilisateur (contenu principal) |
| `sbar` | Barre de statut |

---

## 7. Outils de developpement

Le repertoire `tools/` contient les scripts utilitaires :

| Script | Description |
|--------|-------------|
| `sap_inspect.py` | Inspecte la session SAP GUI active et exporte l'arbre en JSON |
| `sap_scenarios.py` | Automatise la capture de plusieurs ecrans en sequence |
| `sap_launch.py` | Lance SAP GUI et attend la connexion |
| `sap_connect.py` | Se connecte a une session SAP GUI existante |
| `capture_live.py` | Capture en continu |
| `generate_screens.py` | Genere les ecrans d'exemple de `screens/` |
| `capture_flows.py` | Capture chaque etape des enchainements de transactions |
| `diag_rot.py` | Diagnostic de la Running Object Table (ROT) |

---

## 8. Suite de tests

```bash
python -m pytest tests/ -q
```

| Fichier | Couverture |
|---------|-----------|
| `tests/test_engine.py` | Arbre de controles, Session, findById, load_screen, transactions |
| `tests/test_ui.py` | Rendu Qt, ScreenRenderer, TransactionRouter |
| `tests/test_e2e.py` | Tests complets : charge ecran -> rendu -> interaction -> verification |
| `tests/test_com_bridge.py` | Chaine COM, acces proprietes, findById via COM |
| `tests/conftest.py` | Fixtures partagees : `qapp` (QApplication session-scoped), `main_window` |

---

## 9. Arborescence du projet

```
gui_sandbox/
  main.py                      Point d'entree + fenetre Qt
  run_sandbox.bat                  Lanceur batch multi-commandes
  requirements.txt             Dependances (PySide6, pywin32, pandas)
  CLAUDE.md                    Instructions pour Claude Code
  engine/
    __init__.py                Exports publics Layer B
    control.py                 30+ classes de controles
    session.py                 Session, Window, SessionInfo
    loader.py                  Chargement JSON -> Session
    transactions/
      __init__.py
      base.py                  BaseTransaction
      se16.py                  SE16InitialScreen
      session_manager.py       SessionManagerScreen
  bridge/
    __init__.py                Exports publics Layer C
    com_server.py              7 classes COM (ComSapGui...ComControl)
    com_thread.py              Thread STA + ROT lifecycle
    proxy.py                   API Python in-process
    server.py                  Serveur HTTP/JSON
    client.py                  Client HTTP (RemoteSession)
    recorder.py                Journal d'actions
  ui/
    __init__.py
    styles.py                  Constantes visuelles SAP
    screen_renderer.py         Rendu ecrans JSON -> widgets Qt
    widget_factory.py          Fabrique de widgets Qt par type
    transaction_router.py      Routage tcode -> ecran
  screens/
    _manifest.json             Index des ecrans
    01_SESSION_MANAGER.json    Ecran d'accueil Easy Access
    02_SE16_initial.json       Data Browser : ecran initial
    ...                        (24 fichiers JSON au total)
  tools/
    sap_inspect.py             Inspection de sessions SAP
    sap_scenarios.py           Capture automatisee
    sap_launch.py              Lancement SAP GUI
    sap_connect.py             Connexion a SAP GUI
    diag_rot.py                Diagnostic ROT
    ...
  tests/
    conftest.py                Fixtures pytest
    test_engine.py             Tests Layer B
    test_ui.py                 Tests Layer A
    test_e2e.py                Tests end-to-end
    test_com_bridge.py         Tests Layer C (COM)
  docs/
    user_guide.md              Mode operatoire utilisateur
    DOCUMENTATION_TECHNIQUE.md Ce document
    project_documentation.html Documentation HTML complete
```
