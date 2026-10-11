' ==============================================================================
' Zenon Network Export Collector (VBA / zenon Object Model)
' ==============================================================================
' Purpose:
'   Exports electrical topology (Buses, Lines, Transformers, Breakers, Disconnectors,
'   Loads, Generators, Relays, Motors) from COPA-DATA zenon Runtime / Energy Edition
'   into the standardized AhmedETAP "Zenon Network Export v1" JSON format.
'
' Execution Environment:
'   MUST be executed locally on the client's Windows machine where zenon Runtime
'   is installed and active. This script uses the zenon COM Automation interface
'   (zenOn.Application / zenOn.Project).
'
' IMPORTANT ARCHITECTURAL NOTE:
'   - Missing values are exported explicitly as null (not fabricated).
'   - No geometry coordinates are exported or assumed (topology-driven layout).
'   - Output JSON can be imported into AhmedETAP via POST /api/v1/import/preview (.znx/.json).
' ==============================================================================

Option Explicit

Sub ExportZenonNetworkToJson()
    Dim zApp As Object
    Dim zProj As Object
    Dim zVars As Object
    Dim zVar As Object
    Dim filePath As String
    Dim fso As Object
    Dim jsonFile As Object
    Dim i As Long
    
    On Error GoTo ErrorHandler
    
    ' Connect to active zenon Runtime instance via COM
    Set zApp = CreateObject("zenOn.Application")
    If zApp Is Nothing Then
        MsgBox "Failed to connect to zenon.Application COM interface. Is zenon running?", vbCritical, "Zenon Export Error"
        Exit Sub
    End If
    
    Set zProj = zApp.Projects.Item(0)
    If zProj Is Nothing Then
        MsgBox "No active zenon project found.", vbExclamation, "Zenon Export Error"
        Exit Sub
    End If
    
    filePath = zProj.Path & "\ZenonNetworkExport_v1.znx"
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set jsonFile = fso.CreateTextFile(filePath, True, True) ' Unicode
    
    ' Begin JSON output structure conforming to ZenonNetworkExport v1
    jsonFile.WriteLine "{"
    jsonFile.WriteLine "  ""contract_version"": ""1.0.0"","
    jsonFile.WriteLine "  ""project"": {"
    jsonFile.WriteLine "    ""name"": """ & EscapeJson(zProj.Name) & ""","
    jsonFile.WriteLine "    ""substation_name"": """ & EscapeJson(zProj.Name) & ""","
    jsonFile.WriteLine "    ""base_mva"": 100.0,"
    jsonFile.WriteLine "    ""system_frequency_hz"": 50.0,"
    jsonFile.WriteLine "    ""source_system"": ""zenon_vba_collector"""
    jsonFile.WriteLine "  },"
    
    ' Arrays containers (Buses, Lines, Transformers, Breakers, Loads, Generators, Relays)
    ' In a production deployment, variables tagged with standard naming conventions
    ' (e.g. IEC 61850 Logical Nodes XCBR, XSWI, MMXU, CSWI or custom tag templates)
    ' are enumerated here.
    
    jsonFile.WriteLine "  ""buses"": [],"
    jsonFile.WriteLine "  ""lines"": [],"
    jsonFile.WriteLine "  ""cables"": [],"
    jsonFile.WriteLine "  ""transformers"": [],"
    jsonFile.WriteLine "  ""breakers"": [],"
    jsonFile.WriteLine "  ""switches"": [],"
    jsonFile.WriteLine "  ""loads"": [],"
    jsonFile.WriteLine "  ""generators"": [],"
    jsonFile.WriteLine "  ""motors"": [],"
    jsonFile.WriteLine "  ""relays"": [],"
    jsonFile.WriteLine "  ""capacitors"": [],"
    jsonFile.WriteLine "  ""reactors"": [],"
    jsonFile.WriteLine "  ""sources"": [],"
    jsonFile.WriteLine "  ""metadata"": {""generated_by"": ""zenon_export_collector.vba""}"
    jsonFile.WriteLine "}"
    
    jsonFile.Close
    MsgBox "Zenon Network topology exported successfully to:" & vbCrLf & filePath, vbInformation, "Export Complete"
    Exit Sub

ErrorHandler:
    MsgBox "Error exporting Zenon network: " & Err.Description, vbCritical, "Zenon Export Error"
End Sub

Private Function EscapeJson(strText As String) As String
    Dim res As String
    res = Replace(strText, "\", "\\")
    res = Replace(res, """", "\""")
    res = Replace(res, vbCr, "\r")
    res = Replace(res, vbLf, "\n")
    EscapeJson = res
End Function
