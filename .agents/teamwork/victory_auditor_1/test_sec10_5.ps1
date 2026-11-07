$root = 'c:\Users\96655\Downloads\__VORTX STORE_ نسخة'
$targetDir = (Get-ChildItem -LiteralPath $root -Recurse | Where-Object { $_.Name -eq 'Vortx_buy' -and $_.Attributes -match 'Directory' }).FullName
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
$found | Select-Object -Unique
