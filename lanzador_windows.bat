@echo off
setlocal EnableExtensions

set "BASE=%~dp0"
set "PYTHON=%BASE%python\python.exe"

call :comprobar_entorno
if errorlevel 1 exit /b 1

echo Iniciando el panel web local...
"%PYTHON%" "%BASE%web_dashboard.py"
exit /b %errorlevel%

:comprobar_entorno
if not exist "%PYTHON%" (
    echo No se encuentra Python portable en:
    echo   %BASE%python
    echo Ejecuta preparar_windows.bat una vez en este ordenador.
    pause
    exit /b 1
)

"%PYTHON%" "%BASE%comprobar_dependencias.py"
if errorlevel 1 (
    echo.
    echo El entorno existe, pero no contiene todas las librerias.
    echo Ejecuta preparar_windows.bat para instalarlo o repararlo.
    pause
    exit /b 1
)
exit /b 0
