@echo off
setlocal EnableExtensions

set "BASE=%~dp0"
set "PYTHON=%BASE%.venv\Scripts\python.exe"

call :comprobar_entorno
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

:comprobar_entorno
if not exist "%PYTHON%" (
    echo No se encuentra el entorno virtual en:
    echo   %BASE%.venv
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
