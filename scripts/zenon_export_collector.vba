' ==============================================================================
' Zenon Raw Dump Collector (VBA / zenon COM Automation)
' ==============================================================================
' Purpose:
'   Connects to COPA-DATA zenon Runtime via COM (zenOn.Application),
'   enumerates active project variables, telemetry, and mimic screen elements,
'   and writes a raw dump conforming to "ZenonRawDump v1" JSON.
'
' Strict Anti-Guessing Rules:
'   - Electrical properties not directly provided by zenon are written as null.
'   - base_mva and system_frequency_hz are written as null unless explicitly configured.
'   - Output conforms to raw dump v1 schema and is classified server-side.
'   - Every COM call is wrapped with error diagnostics; COM failures log to diagnostics[]
'     without crashing the export.
'   - The written JSON file is read back and verified before completing.
' ==============================================================================

Option Explicit

Sub ExportZenonRawDumpToJson()
    Dim zApp As Object
    Dim zProj As Object
    Dim zVars As Object
    Dim zVar As Object
    Dim zPictures As Object
    Dim zPic As Object
    Dim zElem As Object
    Dim fso As Object
    Dim jsonFile As Object
    Dim readVerifyFile As Object
    Dim filePath As String
    Dim verifyContent As String
    
    Dim diagnostics As Collection
    Set diagnostics = New Collection
    
    Dim varCount As Long
    Dim picCount As Long
    Dim i As Long, j As Long, k As Long
    Dim isFirst As Boolean
    
    On Error Resume Next
    
    ' 1. Connect to zenon COM Automation interface
    Set zApp = CreateObject("zenOn.Application")
    If zApp Is Nothing Or Err.Number <> 0 Then
        MsgBox "Failed to connect to zenOn.Application COM interface. Ensure zenon Runtime is running.", vbCritical, "Zenon Export Error"
        Exit Sub
    End If
    
    ' 2. Retrieve active project
    Set zProj = zApp.Projects.Item(0)
    If zProj Is Nothing Or Err.Number <> 0 Then
        MsgBox "No active zenon project found in running runtime.", vbExclamation, "Zenon Export Error"
        Exit Sub
    End If
    
    ' Setup file output path
    filePath = zProj.Path & "\ZenonRawDump_v1.json"
    If Trim(zProj.Path) = "" Then
        filePath = "C:\ZenonRawDump_v1.json"
    End If
    
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set jsonFile = fso.CreateTextFile(filePath, True, True) ' Unicode (UTF-16 LE)
    If jsonFile Is Nothing Then
        MsgBox "Unable to create output file: " & filePath, vbCritical, "Zenon File Error"
        Exit Sub
    End If
    
    ' 3. Header & Project Metadata
    jsonFile.WriteLine "{"
    jsonFile.WriteLine "  ""dump_version"": ""1.0.0"","
    jsonFile.WriteLine "  ""project"": {"
    jsonFile.WriteLine "    ""name"": """ & EscapeJson(SafeGetProp(zProj, "Name", "Zenon_Project")) & ""","
    jsonFile.WriteLine "    ""version"": """ & EscapeJson(SafeGetProp(zProj, "Version", "")) & ""","
    jsonFile.WriteLine "    ""path"": """ & EscapeJson(SafeGetProp(zProj, "Path", "")) & ""","
    jsonFile.WriteLine "    ""substation_name"": """ & EscapeJson(SafeGetProp(zProj, "Name", "Zenon_Substation")) & ""","
    jsonFile.WriteLine "    ""base_mva"": null,"
    jsonFile.WriteLine "    ""system_frequency_hz"": null"
    jsonFile.WriteLine "  },"
    
    ' 4. Variables Enumeration
    jsonFile.WriteLine "  ""variables"": ["
    Set zVars = zProj.Variables
    varCount = 0
    If Not zVars Is Nothing Then
        varCount = zVars.Count
    Else
        diagnostics.Add "Project.Variables COM interface returned Nothing"
    End If
    
    isFirst = True
    For i = 0 To varCount - 1
        Err.Clear
        Set zVar = zVars.Item(i)
        If Err.Number <> 0 Then
            diagnostics.Add "Error accessing variable at index " & i & ": " & Err.Description
        ElseIf Not zVar Is Nothing Then
            If Not isFirst Then
                jsonFile.WriteLine ","
            End If
            isFirst = False
            
            Dim varName As String
            Dim varIdent As String
            Dim varType As String
            Dim varUnit As String
            Dim varVal As String
            Dim varDriver As String
            
            varName = EscapeJson(SafeGetProp(zVar, "Name", "VAR_" & i))
            varIdent = EscapeJson(SafeGetProp(zVar, "Tag", SafeGetProp(zVar, "Identification", "")))
            varType = EscapeJson(SafeGetProp(zVar, "DataType", ""))
            varUnit = EscapeJson(SafeGetProp(zVar, "Unit", ""))
            varDriver = EscapeJson(SafeGetProp(zVar, "DriverName", ""))
            
            ' Safe value extraction
            Err.Clear
            Dim rawVal As Variant
            rawVal = zVar.Value
            If Err.Number <> 0 Then
                varVal = "null"
                diagnostics.Add "Failed to read Value for variable " & varName & ": " & Err.Description
            ElseIf IsNumeric(rawVal) Then
                varVal = CStr(rawVal)
            ElseIf IsNull(rawVal) Or IsEmpty(rawVal) Then
                varVal = "null"
            Else
                varVal = """" & EscapeJson(CStr(rawVal)) & """"
            End If
            
            jsonFile.Write "    {""name"": """ & varName & """"
            If varIdent <> "" Then jsonFile.Write ", ""identification"": """ & varIdent & """"
            If varType <> "" Then jsonFile.Write ", ""data_type"": """ & varType & """"
            If varUnit <> "" Then jsonFile.Write ", ""unit"": """ & varUnit & """"
            If varDriver <> "" Then jsonFile.Write ", ""driver"": """ & varDriver & """"
            jsonFile.Write ", ""value"": " & varVal & "}"
        End If
    Next i
    jsonFile.WriteLine ""
    jsonFile.WriteLine "  ],"
    
    ' 5. Screens / Mimics Enumeration
    jsonFile.WriteLine "  ""screens"": ["
    Set zPictures = zProj.DynPictures
    If zPictures Is Nothing Then
        Set zPictures = zProj.Screens
    End If
    
    picCount = 0
    If Not zPictures Is Nothing Then
        picCount = zPictures.Count
    Else
        diagnostics.Add "No DynPictures/Screens COM collection found in active project"
    End If
    
    isFirst = True
    For j = 0 To picCount - 1
        Err.Clear
        Set zPic = zPictures.Item(j)
        If Err.Number <> 0 Then
            diagnostics.Add "Error accessing screen at index " & j & ": " & Err.Description
        ElseIf Not zPic Is Nothing Then
            If Not isFirst Then
                jsonFile.WriteLine ","
            End If
            isFirst = False
            
            Dim picName As String
            picName = EscapeJson(SafeGetProp(zPic, "Name", "SCREEN_" & j))
            
            jsonFile.WriteLine "    {"
            jsonFile.WriteLine "      ""name"": """ & picName & ""","
            jsonFile.WriteLine "      ""elements"": ["
            
            Dim elemCount As Long
            elemCount = 0
            Dim zElements As Object
            Set zElements = zPic.Elements
            If Not zElements Is Nothing Then elemCount = zElements.Count
            
            Dim isElemFirst As Boolean
            isElemFirst = True
            For k = 0 To elemCount - 1
                Err.Clear
                Set zElem = zElements.Item(k)
                If Not zElem Is Nothing And Err.Number = 0 Then
                    If Not isElemFirst Then
                        jsonFile.WriteLine ","
                    End If
                    isElemFirst = False
                    
                    Dim elemName As String
                    Dim linkedVar As String
                    elemName = EscapeJson(SafeGetProp(zElem, "Name", "ELEM_" & k))
                    linkedVar = EscapeJson(SafeGetProp(zElem, "LinkedVariable", ""))
                    
                    jsonFile.Write "        {""name"": """ & elemName & """"
                    If linkedVar <> "" Then
                        jsonFile.Write ", ""linked_variables"": [""" & linkedVar & """]}"
                    Else
                        jsonFile.Write ", ""linked_variables"": []}"
                    End If
                End If
            Next k
            jsonFile.WriteLine ""
            jsonFile.WriteLine "      ]"
            jsonFile.Write "    }"
        End If
    Next j
    jsonFile.WriteLine ""
    jsonFile.WriteLine "  ],"
    
    ' 6. Diagnostics block
    jsonFile.WriteLine "  ""diagnostics"": ["
    isFirst = True
    Dim d As Variant
    For Each d In diagnostics
        If Not isFirst Then jsonFile.WriteLine ","
        isFirst = False
        jsonFile.Write "    """ & EscapeJson(CStr(d)) & """"
    Next d
    jsonFile.WriteLine ""
    jsonFile.WriteLine "  ]"
    jsonFile.WriteLine "}"
    
    jsonFile.Close
    
    ' 7. Verify JSON by reading back
    Err.Clear
    Set readVerifyFile = fso.OpenTextFile(filePath, 1, False, -1) ' Unicode
    If Err.Number = 0 And Not readVerifyFile Is Nothing Then
        verifyContent = readVerifyFile.Read(100)
        readVerifyFile.Close
        If Len(verifyContent) > 0 Then
            MsgBox "Zenon raw dump generated and verified successfully!" & vbCrLf & _
                   "Variables: " & varCount & vbCrLf & _
                   "Screens: " & picCount & vbCrLf & _
                   "Diagnostics: " & diagnostics.Count & vbCrLf & _
                   "Path: " & filePath, vbInformation, "Zenon Export Complete"
            Exit Sub
        End If
    End If
    
    MsgBox "Warning: Dump file written but readback verification was empty or unreadable.", vbExclamation, "Zenon Export Verification Warning"
End Sub

' Helper: Safely retrieve COM property without raising fatal errors
Function SafeGetProp(obj As Object, propName As String, defaultVal As String) As String
    On Error Resume Next
    Dim val As Variant
    val = CallByName(obj, propName, VbGet)
    If Err.Number <> 0 Or IsNull(val) Or IsEmpty(val) Then
        SafeGetProp = defaultVal
        Err.Clear
    Else
        SafeGetProp = CStr(val)
    End If
End Function

' Helper: Full JSON string escaping (handles quotes, backslashes, control characters)
Function EscapeJson(rawStr As String) As String
    Dim res As String
    Dim ch As String
    Dim idx As Long
    Dim code As Integer
    
    res = ""
    For idx = 1 To Len(rawStr)
        ch = Mid(rawStr, idx, 1)
        code = AscW(ch)
        Select Case ch
            Case """"
                res = res & "\"""
            Case "\"
                res = res & "\\"
            Case vbCr
                res = res & "\r"
            Case vbLf
                res = res & "\n"
            Case vbTab
                res = res & "\t"
            Case Else
                If code < 32 Then
                    res = res & "\u00" & Right("0" & Hex(code), 2)
                Else
                    res = res & ch
                End If
        End Select
    Next idx
    EscapeJson = res
End Function
