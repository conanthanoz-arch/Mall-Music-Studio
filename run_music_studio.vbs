' Launch Mall Music Studio with no command window.
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
exe = dir & "\dist\MallMusicStudio.exe"

If Not fso.FileExists(exe) Then
    sh.Run "cmd /c """ & dir & "\build_music_studio.bat""", 1, True
End If

If fso.FileExists(exe) Then
    sh.Run """" & exe & """", 1, False
End If
