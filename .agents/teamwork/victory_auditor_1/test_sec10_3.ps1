Get-MpThreatDetection | Where-Object { $_.Resources -match 'Vortx.exe' } | Select-Object ThreatName, SeverityID, InitialDetectionTime, Resources
