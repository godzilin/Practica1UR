# Práctica visualizador UR3e por TCP/IP

## Estructura

| Carpeta | Contenido |
|---|---|
| `material/` | Enunciados, documentación de UR (primaria, tiempo real, URScript) y wheel del visualizador |
| `visualizador/` | Práctica evaluable: `test_conexion.py`, y por hitos `primaria.py`, `tiempo_real.py`, varios robots y enseñar/reproducir |
| `practica1_hilos/` | Práctica 1 guiada (e1_*, e2_*, e3_*), escritos a mano desde el Anexo A |
| `antiguos/` | Pruebas anteriores (práctica 0, lectura de dos robots, túnel) |
| `venv/` | Entorno Python 3.13 con `ur3e_rg2`, `pybullet` y `numpy` |

## Entorno

```
source venv/bin/activate.fish      # fish; en bash: source venv/bin/activate
```

Recrearlo desde cero:

```
uv venv --python 3.13 venv
uv pip install --python venv/bin/python material/ur3e_rg2-0.1.0-py3-none-any.whl
```

## Red

- URSim (VirtualBox, modo puente): `10.172.18.67`
- UR3e reales (laboratorio de robótica): `10.172.21.203` a `.206`

## Uso

Abrir la carpeta `Practica1UR` en VS Code (usa `venv` automáticamente por `.vscode/settings.json`),
abrir el script, cambiar las constantes de `CONFIGURACIÓN` del principio y pulsar F5 o ▶.

- `visualizador/test_conexion.py`: lee versión, modo y q_actual; con `MOVER = True` gira la base y vuelve
- `visualizador/primaria.py`: visualizador; `MODO` = `"angulos"` (A4/A5), `"bytes"` (A1) o `"mensajes"` (A2/A3)
- `visualizador/tiempo_real.py`: visualizador a 500 Hz; `MODO` = `"angulos"` (B2–B4) o `"paquetes"` (B1); `FPS` de dibujo

## Hitos

- [x] A1–A5 · `primaria.py` (30001)
  - [x] Convenio de ángulos: URSim y URDF coinciden, `SIGNOS`/`OFFSETS` sin cambios
        (posición del TCP con error < 0,1 mm en 4 posturas; orientación con diferencia constante
        que solo es la definición de ejes de `tool0` en el URDF del RG2)
  - [x] Reconexión simulada: socket cerrado (`ss -K`) y red cortada 10 s (iptables) → reconecta solo
  - [ ] Reiniciar URSim de verdad con el programa en marcha (lo que se ve en la defensa)
- [x] B1–B4 · `tiempo_real.py` (30003)
  - URSim 5.25: paquetes de 1220 B, ~480/s (la VM simula un 4 % más lenta que el tiempo real:
    el reloj del robot avanza 2 ms por paquete pero solo 3,83 s cada 4 s reales)
- [ ] C · varios robots, hilo por conexión, configuración en fichero
- [ ] D · enseñar y reproducir (URScript, `movej`)
