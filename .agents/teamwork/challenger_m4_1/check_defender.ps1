$detection = Get-MpThreatDetection | Where-Object { $_.Resources -match 'Vortx.exe' }
$detection | Format-List *

if ($detection.ThreatID) {
    $threat = Get-MpThreat | Where-Object { $_.ThreatID -eq $detection.ThreatID }
    $threat | Format-List *
}
