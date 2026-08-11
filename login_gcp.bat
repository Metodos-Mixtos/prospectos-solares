@echo off
REM ---------------------------------------------------------------------------
REM Inicia sesion en Google Cloud para acceder a los buckets del proyecto.
REM
REM Se abre el navegador y apruebas con tu cuenta. No se descarga ninguna clave:
REM se crean credenciales de aplicacion por defecto (ADC) ligadas a tu usuario.
REM
REM Uso: doble clic sobre este archivo.
REM
REM Existe porque tras instalar el SDK con winget, las terminales y programas que
REM ya estaban abiertos conservan el PATH anterior y no encuentran "gcloud".
REM Este script lo busca por ruta.
REM ---------------------------------------------------------------------------

setlocal

echo ===========================================================
echo   Acceso a Google Cloud - proyecto mmc-general
echo ===========================================================
echo.

set "GC="
set "P1=%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
set "P2=%ProgramFiles(x86)%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
set "P3=%ProgramFiles%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"

if exist "%P1%" set "GC=%P1%"
if not defined GC if exist "%P2%" set "GC=%P2%"
if not defined GC if exist "%P3%" set "GC=%P3%"
if not defined GC where gcloud >nul 2>&1 && set "GC=gcloud"

if not defined GC (
    echo No se encontro el SDK de Google Cloud.
    echo.
    echo Instalalo con:
    echo     winget install Google.CloudSDK
    echo.
    pause
    exit /b 1
)

echo Usando: %GC%
echo.
echo Se va a abrir el navegador. Aprueba con tu cuenta de Google
echo (la misma con la que ves la consola de mmc-general).
echo.

call "%GC%" auth application-default login

echo.
echo ===========================================================
if errorlevel 1 (
    echo   El login no se completo.
) else (
    echo   Listo. Ya puedes volver a Claude y pedir el listado.
)
echo ===========================================================
echo.
pause
