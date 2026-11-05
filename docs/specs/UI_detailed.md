🧱 1. GLOBAL WINDOW LAYOUT

This screen is composed of 6 horizontal zones:

[ A ] Top Menu Bar
[ B ] Standard Toolbar Row
[ C ] Title Banner (blue gradient)
[ D ] Secondary Toolbar (small icons)
[ E ] Main Content Split Area
[ F ] Status Bar (not visible here but must exist)

Use a vertical layout container:

QVBoxLayout
 ├── MenuBar
 ├── Toolbar_Main
 ├── Banner_Header
 ├── Toolbar_Context
 ├── Central_Splitter
 └── StatusBar
🧭 2. EXACT WIDGET TREE
🟦 A. MENU BAR

Menus:

Menu   Traiter   Favoris   Autres fonctions   Système   Aide
Qt mapping

Use QMenuBar

Each menu must be a QMenu with:

hover highlight

thin underline when selected

classic Windows style spacing

Control IDs
menu_bar
menu_system
menu_edit
menu_favorites
menu_extras
menu_help
🟦 B. MAIN TOOLBAR ROW

Contains:

Left side

Green check icon (Enter)

Command field input box

Dropdown arrow on right of field

Right side

Standard SAP icons row:

Save
Back
Exit
Cancel
Print
Find
First page
Previous page
Next page
Last page
Create session
Help
Customize layout
Qt structure
QToolBar (iconSize=16x16)

 ├── QPushButton (enter)
 ├── QLineEdit (command field)
 ├── QToolButton (dropdown)
 ├── Spacer
 ├── QPushButton group (icons...)
Control IDs
toolbar_main
cmd_field
btn_enter
btn_save
btn_back
btn_exit
btn_cancel
btn_print
btn_find
btn_first
btn_prev
btn_next
btn_last
btn_new_session
btn_help
btn_customize
🟦 C. TITLE BANNER

Text:

Easy Access  -  Menu for USER_STANDARD
Style

Height: 48px

Gradient background:

top: #DCE6F2

bottom: #B7C9DC

Border bottom: 1px solid #9FB2C6

Font:

Segoe UI / Arial

size: 13–14px

weight: bold

color: #000000

Layout
QFrame (banner_header)
 └── QLabel (title_text)
ID
header_banner
header_title
🟦 D. SECONDARY TOOLBAR (CONTEXT ICONS)

Icons visible:

Open folder
Create folder
Delete
Display
Change
Collapse
Expand
Style

Height: 32px

Background: #D5DEE8

Top border: 1px solid #B3C0CF

Bottom border: 1px solid #A0B0C2

Qt
QToolBar (toolbar_context)
IDs
toolbar_context
btn_open
btn_create
btn_delete
btn_display
btn_change
btn_collapse
btn_expand
🟦 E. MAIN CONTENT AREA

This is a split screen.

Left side: navigation tree
Right side: empty workspace

Qt
QSplitter(horizontal)
 ├── QTreeWidget (navigation_tree)
 └── QWidget (workspace_panel)
🌳 3. TREE PANEL SPEC

Tree items:

📁 Favoris
📁 Menu for USER_STANDARD
Tree Style

Background: #F4F6F9

Row height: 20px

Indent: 18px

Selected color:

bg: #C7D6EA

border dotted: #6F8DB3

Expand icon: small triangle

Folder icon: classic yellow SAP style

IDs
nav_tree
tree_favorites
tree_user_menu
🎨 4. GLOBAL COLORS
Element	Color
Menu background	#E6EEF7
Toolbar bg	#D5DEE8
Banner gradient	#DCE6F2 → #B7C9DC
Panel bg	#F4F6F9
Borders	#9FB2C6
Text	#000000
🔤 5. FONT SPEC

Primary font stack:

"Segoe UI", "Arial", sans-serif

Sizes:

Element	Size
Menus	12px
Toolbar	12px
Tree	12px
Banner	14px bold
🧠 6. BEHAVIOR RULES (IMPORTANT)
Command field

pressing Enter triggers transaction load

supports /nXXXX

supports /oXXXX

dropdown shows last transactions

Tree

double click → open transaction

right click → context menu

expand/collapse animation disabled (SAP style instant)

Toolbar buttons

Must emit logical events, not UI-only signals:

on_enter_pressed
on_save_pressed
on_back_pressed

These must connect to Control Tree Engine events.

⚙️ 7. QT IMPLEMENTATION HINTS
Use:
QMainWindow
QMenuBar
QToolBar
QFrame
QSplitter
QTreeWidget
QStatusBar
Important Qt settings to mimic SAP
setUnifiedTitleAndToolBarOnMac(False)
setIconSize(QSize(16,16))
setToolButtonStyle(Qt.ToolButtonIconOnly)
setContentsMargins(0,0,0,0)
setSpacing(0)
Disable modern styling

SAP look requires:

app.setStyle("Fusion")

Then override with custom palette.

🧩 8. AUTOMATION IDENTIFIERS (CRITICAL FOR RPA)

Every widget must expose:

objectName = stable SAP-like ID
accessibleName = same ID

Example:

cmd_field.setObjectName("wnd[0]/tbar[0]/okcd")

This allows:

SAPscript-style targeting

UiPath selector compatibility

deterministic automation