# Compatibilidad con instrucciones anteriores. Preferir scripts/migrar.ps1.
$ErrorActionPreference = "Stop"
Write-Warning "migrar_neon.ps1 fue reemplazado por migrar.ps1 (incluye MS1 a MS4)."
& (Join-Path $PSScriptRoot "migrar.ps1")
exit $LASTEXITCODE
