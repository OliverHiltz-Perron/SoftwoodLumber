# Create a Windows shortcut for easier launching
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$(Get-Location)\SoftwoodLumber.lnk")
$Shortcut.TargetPath = "$(Get-Location)\run-app.bat"
$Shortcut.IconLocation = "$(Get-Location)\src\assets\SLB-LOGO.png,0"
$Shortcut.Description = "Launch Softwood Lumber Board Document Checker"
$Shortcut.WorkingDirectory = "$(Get-Location)"
$Shortcut.Save()

Write-Host "Launcher created! You can now double-click on SoftwoodLumber.lnk to start the application."
