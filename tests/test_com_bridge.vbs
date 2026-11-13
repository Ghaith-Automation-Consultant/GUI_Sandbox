' COM bridge smoke test (VBScript) — run while main.py is running.
'
' Usage:  cscript tests\test_com_bridge.vbs

On Error Resume Next

Set SapGuiAuto = GetObject("SAPGUI")
If Err.Number <> 0 Then
    WScript.Echo "FAILED — could not connect: " & Err.Description
    WScript.Echo "Make sure main.py is running first."
    WScript.Quit 1
End If
On Error GoTo 0

WScript.Echo "Connected to SAPGUI"
WScript.Echo "  Root ID: " & SapGuiAuto.Id

Set app = SapGuiAuto.GetScriptingEngine
WScript.Echo "  App Type: " & app.Type

If app.Children.Count = 0 Then
    app.OpenConnection "WL - With logon", True
    WScript.Echo "  Opened WL - With logon"
End If

Set con = app.Children.Item(0)
WScript.Echo "  Connection: " & con.Description

Set session = con.Children.Item(0)
WScript.Echo "  Transaction: " & session.Info.Transaction
WScript.Echo "  User: " & session.Info.User

If session.Info.Transaction = "S000" Then
    session.findById("wnd[0]/usr/txtRSYST-MANDT").Text = "000"
    session.findById("wnd[0]/usr/txtRSYST-BNAME").Text = "USER_STANDARD"
    session.findById("wnd[0]/usr/pwdRSYST-BCODE").Text = "sandbox"
    session.findById("wnd[0]").sendVKey 0
    WScript.Echo "  Logged on as: " & session.Info.User
End If

session.StartTransaction "SE16"
session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "SFLIGHT"
WScript.Echo "  Set field to SFLIGHT"

Dim fieldText
fieldText = session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text
WScript.Echo "  Field text: " & fieldText

session.findById("wnd[0]").sendVKey 0
WScript.Echo "  sendVKey(0) — OK"

' ALV grid: rows below the screen read empty until the grid scrolls to them
session.findById("wnd[0]").sendVKey 8
Set grid = session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell")
WScript.Echo "  Grid rows: " & grid.RowCount & ", visible: " & grid.VisibleRowCount
If grid.GetCellValue(100, "CARRID") <> "" Then Fail "row 100 should not be loaded yet"
grid.firstVisibleRow = 96
If grid.GetCellValue(100, "CARRID") = "" Then Fail "row 100 should be loaded after scrolling"
WScript.Echo "  Row 100 after scrolling: " & grid.GetCellValue(100, "CARRID") & " " & grid.GetCellValue(100, "CONNID")

' Table control: page through, finding the table again after each scroll
session.StartTransaction "VA03"
session.findById("wnd[0]").sendVKey 0
tbl = "wnd[0]/usr/tabsTAXI_TABSTRIP/tabpT02/tblITEMS"
Set table = session.findById(tbl)
total = table.RowCount
page = table.VisibleRowCount
items = 0
For first = 0 To total - 1 Step page
    table.VerticalScrollbar.Position = first
    Set table = session.findById(tbl)
    For r = 0 To page - 1
        If first + r < total Then
            lastItem = table.GetCell(r, 0).Text
            items = items + 1
        End If
    Next
Next
WScript.Echo "  VA03 items read: " & items & " of " & total & ", last item " & lastItem
If items <> total Or lastItem <> "250" Then Fail "table paging read the wrong rows"

' A table reference taken before a scroll stops working, as in SAP GUI
Set oldTable = session.findById(tbl)
oldTable.VerticalScrollbar.Position = 0
On Error Resume Next
dummy = oldTable.RowCount
staleError = Err.Number
On Error GoTo 0
If staleError = 0 Then Fail "a stale table reference should raise"
WScript.Echo "  Stale table reference raised, as expected"

WScript.Echo ""
WScript.Echo "=== ALL TESTS PASSED ==="

Sub Fail(message)
    WScript.Echo "FAILED — " & message
    WScript.Quit 1
End Sub
