@echo off
rem Prepara el entorno la primera vez (o si esta roto) y abre el panel web.
rem Uso: doble clic. Necesita Python 3 instalado (comando py) y, la primera vez, Internet.
cd /d "%~dp0.."
.venv\Scripts\python -c "import UR3e_rg2" 2>nul
if errorlevel 1 (
    py -m venv .venv || goto error
    .venv\Scripts\python -m pip install material\ur3e_rg2-0.1.0-py3-none-any.whl || goto error
)
.venv\Scripts\python entrega\panel_web.py
exit /b
:error
echo No se pudo preparar el entorno. Revisa el mensaje de arriba.
pause
