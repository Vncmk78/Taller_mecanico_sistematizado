# migrar_neon.ps1
# Aplica las migraciones Alembic de MS1, MS2 y MS3 contra las bases que apunten
# las variables MS*_DATABASE_URL de backend/.env (en produccion: Neon).
#
# Uso:
#   PowerShell:  .\scripts\migrar_neon.ps1
#
# Requisitos:
#   1. Crear backend/.env desde .env.example con los DSN de Neon (agregar
#      ?sslmode=require). MS4 aun no tiene migraciones (no hay modelos).
#   2. Correr desde backend/ (o cualquier ubicacion; el script se posiciona).
#   3. Tener instaladas las dependencias de backend/ (alembic incluido).

$ErrorActionPreference = "Stop"

$backendDir = Split-Path -Parent $PSScriptRoot
Set-Location $backendDir

if (-not (Test-Path ".env")) {
    Write-Host "Falta backend/.env. Copialo desde .env.example y ajusta los DSN de Neon." -ForegroundColor Red
    exit 1
}

$servicios = @(
    @{ nombre = "MS1 (auth)";        ini = "services/ms1_auth/alembic.ini" },
    @{ nombre = "MS2 (taller)";      ini = "services/ms2_taller/alembic.ini" },
    @{ nombre = "MS3 (presupuestos)"; ini = "services/ms3_presupuestos/alembic.ini" }
)

foreach ($servicio in $servicios) {
    Write-Host "Migrando $($servicio.nombre) ..." -ForegroundColor Cyan
    alembic -c $servicio.ini upgrade head
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Fallo la migracion de $($servicio.nombre)." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "Migraciones aplicadas correctamente en Neon." -ForegroundColor Green