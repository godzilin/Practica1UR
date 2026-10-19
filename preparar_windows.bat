@echo off
setlocal EnableExtensions

set "BASE=%~dp0"
set "PYTHON_DIR=%BASE%python"
set "PYTHON=%PYTHON_DIR%\python.exe"
set "PYTHON_ZIP=%BASE%python-3.11.9-embed-amd64.zip"
set "PYTHON_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
set "GET_PIP=%BASE%get-pip.py"

if not exist "%PYTHON%" (
    echo Descargando Python portable 3.11.9. Este paso necesita Internet.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_ZIP%'"
    if errorlevel 1 goto error
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%PYTHON_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force"
    if errorlevel 1 goto error
    del /q "%PYTHON_ZIP%"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = '%PYTHON_DIR%\python311._pth'; (Get-Content $p) -replace '#import site', 'import site' | Set-Content $p"
    if errorlevel 1 goto error
)

if not exist "%PYTHON_DIR%\Scripts\pip.exe" (
    echo Preparando pip dentro de Python portable...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%GET_PIP%'"
    if errorlevel 1 goto error
    "%PYTHON%" "%GET_PIP%"
    if errorlevel 1 goto error
    del /q "%GET_PIP%"
)

echo Instalando dependencias en Python portable. Este paso necesita Internet.
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