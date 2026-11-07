Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strDesktop = WshShell.SpecialFolders("Desktop")
strCurrentDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set oShortcut = WshShell.CreateShortcut(strDesktop & "\Aim Bot AI.lnk")
oShortcut.TargetPath = strCurrentDir & "\Start_AimBot.bat"
oShortcut.WorkingDirectory = strCurrentDir
oShortcut.Description = "Aim Bot AI Assistant - تطبيق مساعد التصويب"
oShortcut.Save
