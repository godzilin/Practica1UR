@echo off
setlocal EnableExtensions

set "BASE=%~dp0"
set "PYTHON=%BASE%.venv\Scripts\python.exe"

if exist "%BASE%.venv\pyvenv.cfg" (
    findstr /r /c:"version = 3\.1[0-9]" "%BASE%.venv\pyvenv.cfg" >nul
    if errorlevel 1 (
        echo Eliminando el entorno antiguo de Python 3.7...
        rmdir /s /q "%BASE%.venv"
    )
)

set "CREADOR="
where python3.11 >nul 2>&1
if not errorlevel 1 set "CREADOR=python3.11"

if not defined CREADOR (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3.11 -c "import sys" >nul 2>&1
        if not errorlevel 1 set "CREADOR=py -3.11"
    )
)

if not defined CREADOR (
    echo No se encuentra Python 3.10 o posterior.
    echo El unico Python disponible es demasiado antiguo para pybullet.
    echo Instala Python 3.11 desde https://www.python.org/downloads/windows/
    pause
    exit /b 1
)

%CREADOR% -m venv "%BASE%.venv"
if errorlevel 1 (
    echo No se pudo crear el entorno virtual.
    pause
    exit /b 1
)

echo Instalando dependencias en .venv. Este archivo puede necesitar Internet.
"%PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto error
"%PYTHON%" -m pip install pybullet pybullet-planning numpy matplotlib python-docx
if errorlevel 1 goto error
"%PYTHON%" -m pip install --no-deps "%BASE%material\ur3e_rg2-0.1.0-py3-none-any.whl"
if errorlevel 1 goto error

"%PYTHON%" "%BASE%comprobar_dependencias.py"
if errorlevel 1 goto error
echo.
echo Entorno preparado. Ya puedes ejecutar lanzador_windows.bat sin descargar nada.
pause
exit /b 0

:error
echo.
echo No se pudo preparar el entorno. Revisa el mensaje anterior.
pause
exit /b 1