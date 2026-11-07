$file = Get-ChildItem -Path "c:\Users\96655\Downloads" -Filter "Vortx Stream.exe" -Recurse | Select-Object -First 1
$vortxBuyDir = Split-Path (Split-Path $file.FullName -Parent) -Parent

[System.AppDomain]::CurrentDomain.add_AssemblyResolve({
    param($sender, $args)
    $name = $args.Name.Split(',')[0] + '.dll'
    $candidate1 = Join-Path $vortxBuyDir $name
    if (Test-Path $candidate1) { return [System.Reflection.Assembly]::LoadFrom($candidate1) }
    $candidate2 = Join-Path (Split-Path $file.FullName -Parent) $name
    if (Test-Path $candidate2) { return [System.Reflection.Assembly]::LoadFrom($candidate2) }
    return $null
})

$asm = [System.Reflection.Assembly]::LoadFrom($file.FullName)
Write-Host "Assembly FullName: " $asm.FullName
Write-Host "EntryPoint: " $asm.EntryPoint

try {
    $types = $asm.GetTypes()
    Write-Host "Total types: " $types.Count
    $types | ForEach-Object {
        $props = $_.GetProperties().Name -join ', '
        $methods = $_.GetMethods().Name -join ', '
        Write-Host "TYPE: $($_.FullName)"
    }
} catch [System.Reflection.ReflectionTypeLoadException] {
    Write-Host "Loaded types:"
    $_.Exception.Types | Where-Object { $_ -ne $null } | ForEach-Object { Write-Host "  " $_.FullName }
    Write-Host "Loader exceptions:"
    $_.Exception.LoaderExceptions | ForEach-Object { Write-Host "  ! " $_.Message }
}
