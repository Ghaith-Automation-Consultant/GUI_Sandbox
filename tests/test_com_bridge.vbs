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

Set con = app.Children.Item(0)
WScript.Echo "  Connection: " & con.Description

Set session = con.Children.Item(0)
WScript.Echo "  Transaction: " & session.Info.Transaction
WScript.Echo "  User: " & session.Info.User

session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "SFLIGHT"
WScript.Echo "  Set field to SFLIGHT"

Dim fieldText
fieldText = session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text
WScript.Echo "  Field text: " & fieldText

session.findById("wnd[0]").sendVKey 0
WScript.Echo "  sendVKey(0) — OK"

WScript.Echo ""
WScript.Echo "=== ALL TESTS PASSED ==="
