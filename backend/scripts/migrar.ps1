# Migra las cuatro bases configuradas, incluidas las evidencias de MS4.
# Usa el Python del entorno activo (con dependencias de backend instaladas).
# No exige archivo .env si las variables se inyectan desde Kubero.
$ErrorActionPreference = "Stop"
python (Join-Path $PSScriptRoot "migrar.py")
exit $LASTEXITCODE
