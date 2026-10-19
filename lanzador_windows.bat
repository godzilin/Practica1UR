@echo off
setlocal EnableExtensions

set "BASE=%~dp0"
set "PYTHON=%BASE%.venv\Scripts\python.exe"

call :preparar_entorno
if errorlevel 1 exit /b 1

:menu
cls
echo ========================================
echo        Visualizador UR3e - Windows
echo ========================================
echo   1^) Primaria ^(puerto 30001^)
echo   2^) Varios robots
echo   3^) Tiempo real ^(puerto 30003^)
echo   4^) Ensenar y reproducir
echo   5^) Probar conexion
echo   6^) Prueba de robustez
echo   7^) Configurar robots
echo   0^) Salir
echo ========================================
set /p "opcion=Elige una opcion: "

if "%opcion%"=="1" call :ejecutar primaria.py
if "%opcion%"=="2" call :ejecutar varios_robots.py
if "%opcion%"=="3" call :ejecutar tiempo_real.py
if "%opcion%"=="4" call :ejecutar ensenar_reproducir.py
if "%opcion%"=="5" call :ejecutar test_conexion.py
if "%opcion%"=="6" call :ejecutar prueba_robustez.py
if "%opcion%"=="7" call :ejecutar configurar_robots.py
if "%opcion%"=="0" exit /b 0
if not "%opcion%"=="0" if not "%opcion%"=="1" if not "%opcion%"=="2" if not "%opcion%"=="3" if not "%opcion%"=="4" if not "%opcion%"=="5" if not "%opcion%"=="6" if not "%opcion%"=="7" (
    echo Opcion no valida.
    pause
)
goto menu

:ejecutar
set "SCRIPT=%~1"
start "UR3e - %SCRIPT%" /D "%BASE%" cmd /k ""%PYTHON%" "%BASE%visualizador\%SCRIPT%""
echo Se ha abierto una ventana nueva para %SCRIPT%.
pause
exit /b 0

:preparar_entorno
if exist "%PYTHON%" if exist "%BASE%.venv\.preparado" exit /b 0

if not exist "%PYTHON%" (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv "%BASE%.venv"
        if errorlevel 1 goto error_entorno
        goto instalar_dependencias
    )

    where python >nul 2>&1
    if not errorlevel 1 (
        python -m venv "%BASE%.venv"
        if errorlevel 1 goto error_entorno
        goto instalar_dependencias
    )

    echo No se encuentra Python instalado en Windows.
    echo Instala Python 3 desde https://www.python.org/downloads/windows/ y vuelve a ejecutar este archivo.
    pause
    exit /b 1
)

:instalar_dependencias
echo Preparando el entorno Python. La primera vez se instalaran las librerias...
"%PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto error_dependencias
"%PYTHON%" -m pip install pybullet numpy matplotlib python-docx "%BASE%material\ur3e_rg2-0.1.0-py3-none-any.whl"
if errorlevel 1 goto error_dependencias
type nul > "%BASE%.venv\.preparado"
echo Entorno preparado correctamente.
exit /b 0

:error_entorno
echo No se pudo crear el entorno virtual.
pause
exit /b 1

:error_dependencias
echo No se pudieron instalar las librerias.
echo Comprueba la conexion a Internet y vuelve a ejecutar este archivo.
pause
exit /b 1
