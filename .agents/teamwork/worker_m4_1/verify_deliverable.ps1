$ErrorActionPreference = "Stop"
$root = (Get-ChildItem -Path "c:\Users\96655\Downloads" -Directory -Filter "*VORTX STORE*")[0].FullName
$targetDir = (Get-ChildItem -LiteralPath $root -Recurse | Where-Object { $_.Name -eq "Vortx_buy" -and $_.Attributes -match "Directory" }).FullName
$report1 = (Get-ChildItem -LiteralPath $root -Filter "TECHNICAL_ANALYSIS_REPORT.md" -Recurse | Where-Object { $_.DirectoryName -notmatch "Vortx_buy" })[0].FullName
$report2 = Join-Path $targetDir "TECHNICAL_ANALYSIS_REPORT.md"
$report3 = "c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\orchestrator\TECHNICAL_ANALYSIS_REPORT.md"

$reports = @($report1, $report2, $report3)
foreach ($r in $reports) {
    if (Test-Path -LiteralPath $r) {
        $sz = (Get-Item -LiteralPath $r).Length
        Write-Host "FOUND: $r ($sz bytes)"
    } else {
        Write-Error "MISSING: $r"
    }
}

$content = Get-Content -LiteralPath $report3 -Raw
$checks = @("LCM1", "DirectML", "ViGEmBus", "HidHide", "ChiakiFrameShare", "Trojan:Win32/Wacatac.B!ml", "TrackedObject", "yolo11m")
foreach ($c in $checks) {
    if ($content -match $c) {
        Write-Host "MATCH: $c present in report"
    } else {
        Write-Error "MISSING: $c"
    }
}
Write-Host "ALL DELIVERABLES VERIFIED SUCCESSFULLY."
