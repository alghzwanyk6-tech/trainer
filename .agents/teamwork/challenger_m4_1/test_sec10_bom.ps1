Write-Host "=== TEST 10.1 ==="
$root = 'c:\Users\96655\Downloads\__VORTX STORE_ نسخة'
$targetDir = (Get-ChildItem -LiteralPath $root -Recurse | Where-Object { $_.Name -eq 'Vortx_buy' -and $_.Attributes -match 'Directory' }).FullName
Write-Host "Resolved Payload Directory: $targetDir"
Get-ChildItem -LiteralPath $targetDir -Directory | Select-Object Name | Out-String | Write-Host

Write-Host "=== TEST 10.2 ==="
$modelsDir = Join-Path $targetDir "models"
Get-ChildItem -LiteralPath $modelsDir -Filter "*.enc" | ForEach-Object {
    $bytes = [System.IO.File]::ReadAllBytes($_.FullName)
    $magic = [System.Text.Encoding]::ASCII.GetString($bytes[0..3])
    [PSCustomObject]@{
        ModelName = $_.Name
        SizeBytes = $_.Length
        Header = $magic
        IsValidLCM1 = ($magic -eq "LCM1")
    }
} | Format-Table | Out-String | Write-Host

Write-Host "=== TEST 10.4 ==="
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipPath = 'c:\Users\96655\Downloads\__VORTX STORE_ نسخة.zip'
[System.IO.Compression.ZipFile]::OpenRead($zipPath).Entries | 
    Where-Object { $_.FullName -match 'Vortx\.exe$' } | 
    Select-Object FullName, Length, CompressedLength | Format-Table | Out-String | Write-Host

Write-Host "=== TEST 10.5 ==="
$streamExe = Join-Path $targetDir "rm_re_fr\Vortx Stream.exe"
$bytes = [System.IO.File]::ReadAllBytes($streamExe)
$ms = New-Object System.IO.MemoryStream(,$bytes)
$pe = New-Object System.Reflection.PortableExecutable.PEReader($ms)
$mr = [System.Reflection.Metadata.PEReaderExtensions]::GetMetadataReader($pe)
$found = @()
foreach ($h in $mr.MemberReferences) {
    $m = $mr.GetMemberReference($h)
    $name = $mr.GetString($m.Name)
    if ($name -match 'AppendExecutionProvider_DML|CreateXbox360Controller|D3D11CreateDevice|SubmitReport') {
        $found += $name
    }
}
$found | Select-Object -Unique | Out-String | Write-Host

Write-Host "=== TEST 10.6 ==="
$asarPath = Join-Path $targetDir "xlu\resources\app.asar"
node -e "
const fs = require('fs');
const fd = fs.openSync('$($asarPath.Replace('\', '/'))', 'r');
const b = Buffer.alloc(16);
fs.readSync(fd, b, 0, 16, 0);
const s = (16 + b.readUInt32LE(12) + 3) & ~3;
const buf = Buffer.alloc(1200);
fs.readSync(fd, buf, 0, 1200, s);
console.log(buf.toString('utf8'));
"
