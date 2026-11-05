📘 SAP GUI – Menu Bar & System Toolbar Specification
1. Overview

This document specifies the functional and visual behavior of:

Menu Bar

System Toolbar (Standard Toolbar)

Theme-dependent behavior (Belize / Quartz)

Interaction rules

Keyboard bindings

UI layout constraints

The objective is to reproduce SAP GUI behavior with maximum fidelity for automation compatibility.

2. Menu Bar Specification
2.1 Layout & Positioning

Located at the top of the main window

Horizontally aligned

Contains:

Window Menu Icon (far left)

SAP Screen Personas Icon (conditional)

Standard Menus (System, Help, etc.)

Overflow pushbutton (conditional)

Personas status icon (far right in Fiori-adjusted themes)

2.2 Window Menu
Position:

Always at the far left of the Menu Bar

Content:

Contains:

Standard Microsoft Windows functions:

Minimize

Maximize

Close

SAP-specific entries:

Create New Session

Cancel Transaction

Behavior:

Opens dropdown on click

Must respond to Alt + Space (Windows standard behavior)

2.3 SAP Screen Personas Icon
Visibility Condition:

Displayed only if:

A Personas flavor is available for the current session

Default Position:

Immediately next to Window Menu Icon

Fiori Adjustment:

In Fiori-aligned themes (Belize / Quartz), the Personas status icon is moved to far right

Action:

On click:

Opens Personas Selector

Opens Flavor Gallery

2.4 Overflow Handling (Menu Wrapping)
Condition:

If all menus cannot fit in a single horizontal row:

Behavior:

A pushbutton appears on the far right

Clicking opens a context menu

Contains hidden menu entries

Requirements:

Dynamic calculation of available width

Menus must not wrap to second line

Overflow must preserve menu order

2.5 Theme Behavior (Belize / Quartz)
Option:

Main menu entries may be moved into a:

More Menu Button

Configuration:

Controlled via:

Theme Settings

Options dialog

Requirement:

Theme system must:

Dynamically relocate menus

Preserve functionality

Maintain keyboard access

3. Standard Menus
3.1 Always Present Menus
3.1.1 System

Scope: Global system actions

Must contain:

Create Session

User Profile

Log Off

Optional (if implemented in app):

Hold Data

Set Data

Delete Data

Behavior:

Affects entire session

Data hold applies only within same session

3.1.2 Help

Scope: Contextual and system help

Must provide:

Field help

Application help

SAP library/help portal access

3.2 Common Menus (Most Applications)
3.2.1 <Object Menu>

Name:

Dynamic (e.g., “Material”, “Sales Order”)

Scope:

Whole object lifecycle

Typical functions:

Display

Change

Print

Exit

3.2.2 Edit

Scope:

Modify object components

Functions:

Select

Edit

Copy

Cancel (Exit without saving)

3.2.3 Goto

Scope:

Navigation within transaction

Functions:

Navigate to other screens

Back (one level in session hierarchy)

Behavior:

Before navigating back:

System validates screen data

Displays error dialog if invalid

3.3 Optional Menus

May appear contextually:

Menu	Purpose
Extras	Rarely used additional object functions
Environment	Display additional object information
View	Switch visual representation
Settings	User-specific transaction parameters
Utilities	Object-independent operations
4. Standard Toolbar (System Toolbar)
4.1 Availability
Classic Theme:

Appears below Menu Bar

Belize / Quartz:

Merged with Application Toolbar

No separate standard toolbar

4.2 Layout

Horizontal icon bar containing:

System function icons

Command Field

Layout customization icon (far right)

4.3 Command Field
Position:

Left area of toolbar

Shortcut:

Ctrl + /

Purpose:

Enter transaction codes

Enter system commands

Behavior:

On Enter:

Execute transaction

Replace current screen

5. Toolbar Buttons – Functional Specification

Each icon must support:

Click event

Keyboard shortcut

Tooltip (Quick Info Text)

Disabled state (context-aware)

5.1 Core System Actions
Function	Shortcut	Behavior
Enter	Enter	Confirm screen input (no save)
Save	Ctrl + S	Persist data
Back	F3	Previous screen (no save)
Exit	Shift + F3	Return to main screen
Cancel	F12	Abort transaction
Print	Ctrl + P	Print current screen
Help	F1	Context help
5.2 Navigation Functions
Function	Shortcut	Behavior
First Page	Ctrl + PgUp	Scroll to start
Previous Page	PgUp	Scroll up
Next Page	PgDn	Scroll down
Last Page	Ctrl + PgDn	Scroll to end
5.3 Search Functions
Function	Shortcut	Behavior
Search	Ctrl + F	Find in screen
Find Next	Ctrl + G	Next match
5.4 Session Management
Function	Shortcut	Behavior
Create New Session	Ctrl + N or Ctrl + +	Open new SAP session
5.5 Shortcuts
Function	Shortcut	Behavior
Create Desktop Shortcut	Ctrl + ;	Create SAP shortcut file
5.6 Local Layout Customization
Icon:

Located far right

Shortcut:

Alt + F12

Opens:

Local Layout Settings dialog

Customizable:

Cursor behavior

TAB behavior

Visual options

6. Behavioral Rules
6.1 Save vs Enter

Enter does NOT persist data

Save must explicitly write changes

6.2 Validation Rules

Before:

Back

Exit

Goto

System must:

Validate mandatory fields

Display blocking dialog if invalid

6.3 State Awareness

Toolbar buttons must dynamically enable/disable depending on:

Transaction state

Screen context

Edit mode

7. Accessibility & Automation Requirements

To ensure compatibility with SAP GUI automation:

7.1 Each Menu Item Must Have:

Unique technical ID

Stable hierarchical path

Keyboard access (Alt navigation)

Example:

menu.system.createSession
menu.edit.copy
toolbar.save
7.2 Keyboard Priority

All functions must be triggerable via:

Keyboard shortcut

Alt + mnemonic navigation

Command field

7.3 Event Model

Each action must expose:

BeforeExecute event

AfterExecute event

Cancelable execution

Error state

8. Theme Compatibility Layer

The system must support:

Theme	Toolbar	Menu Handling
Classic	Separate standard toolbar	Normal menu
Belize	Merged toolbar	Possible More button
Quartz	Merged toolbar	Possible More button
9. UI Fidelity Requirements (For Sandbox)

To be “SAP-identical”:

Pixel-aligned icon spacing

Same tooltip timing delay

Same icon states (pressed, hover, disabled)

Same menu drop animation

Same keyboard responsiveness

10. Non-Functional Requirements

No multi-line menu wrapping

Dynamic width recalculation

Must support multiple sessions

Stateless rendering (for automation testing)

Deterministic focus management