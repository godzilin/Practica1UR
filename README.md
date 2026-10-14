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

- URSim (VirtualBox, modo puente): `10.172.18.67` y `10.172.18.73`
- UR3e reales (laboratorio de robótica): `10.172.21.203` a `.206`

## Uso

Abrir la carpeta `Practica1UR` en VS Code (usa `venv` automáticamente por `.vscode/settings.json`),
abrir el script, cambiar las constantes de `CONFIGURACIÓN` del principio y pulsar F5 o ▶.

- `visualizador/test_conexion.py`: lee versión, modo y q_actual; con `MOVER = True` gira la base y vuelve
- `visualizador/primaria.py`: visualizador; `MODO` = `"angulos"` (A4/A5), `"bytes"` (A1) o `"mensajes"` (A2/A3)
- `visualizador/tiempo_real.py`: visualizador a 500 Hz; `MODO` = `"angulos"` (B2–B4) o `"paquetes"` (B1); `FPS` de dibujo
- `visualizador/varios_robots.py`: varios robots en la misma ventana; los robots se configuran en `visualizador/robots.json` (nombre, host, puerto, posición `[x, y, z, roll, pitch, yaw]`)

## Entrega y evaluación (apartado 11 del enunciado)

La evaluación es incremental y binaria: cada nivel se supera entero o no se supera, y para
optar a un nivel hay que haber superado todos los anteriores. No hay notas intermedias
dentro de un nivel.

| Nivel | Nota | Requisitos (todos obligatorios) | Qué se comprueba en la defensa |
|---|---|---|---|
| Aprobado | 5 | Dos scripts separados: `primaria.py` (puerto 30001) y `tiempo_real.py` (puerto 30003). Cada uno obtiene los 6 `q_actual` de un robot y mueve con ellos el UR3e de PyBullet. Ambos usan buffer y delimitan los mensajes por su longitud | Se mueve el robot en URSim y el simulado le sigue con los dos scripts. Se reinicia URSim y el programa no se cuelga |
| Notable | 7 | Todo lo anterior, más un único script que visualiza varios robots a la vez (al menos dos) en la misma ventana, cada uno en su posición de la escena. Los robots se configuran sin tocar el código. Un robot que se desconecta no detiene a los demás | Se mueven dos robots a la vez (vuestro URSim y otro) y después se desconecta uno |
| Sobresaliente | 10 | Todo lo anterior, más el envío de órdenes y la mini-aplicación *Enseñar y reproducir* descrita abajo, funcionando contra URSim y validada en un UR3e real con el profesor | Se enseña una secuencia de al menos 4 puntos, se previsualiza y se ejecuta. Se provoca un error y el programa lo muestra y se detiene |

### Mini-aplicación del sobresaliente: Enseñar y reproducir

Es el ciclo básico de cualquier célula robotizada de manipulación: enseñar una tarea,
comprobarla antes de ejecutarla y supervisar su ejecución. El visualizador sirve para ver
qué va a hacer el robot antes de que lo haga.

1. **Enseñar.** El operador lleva el robot a una posición (en URSim desde la pestaña Mover;
   en el robot real en modo de guiado manual) y pulsa una tecla para guardar la
   configuración actual, leída de la interfaz primaria, como punto de la secuencia. También
   se puede definir un punto con los deslizadores de PyBullet.
2. **Ejecutar paso a paso.** El programa envía un `movej` por punto y no envía el siguiente
   hasta comprobar con el estado del robot que el anterior ha terminado
   (`isProgramRunning` falso y `q_actual` cercano al objetivo).
3. **Supervisar.** Si llega un mensaje de error (tipo 20, subtipos 6 o 10) o se activa una parada
   de protección (`isProtectiveStopped`), el programa detiene la secuencia, muestra el
   motivo y espera a que el operador la reanude o la cancele.
4. **Guardar.** La secuencia se puede guardar en un fichero y cargar en otra sesión.

**Límites obligatorios en el robot real:** velocidad articular máxima 0,3 rad/s y aceleración
0,5 rad/s² en las órdenes que enviéis, secuencia probada antes en URSim y profesor
presente con la seta de emergencia al alcance.

### Qué se entrega

- **Código:** los scripts de cada nivel alcanzado y un README con cómo ejecutarlos y
  configurar las IP de los robots.
- **Memoria breve** (máximo 6 páginas) con: una breve explicación del código desarrollado,
  con la estructura y estrategias de lectura utilizadas. La respuesta a las preguntas del
  apartado 12.
- **Defensa en el laboratorio:** demostración de los requisitos del nivel al que optáis.
  Cualquier miembro del grupo debe poder explicar cualquier línea del código entregado;
  si no puede, el nivel no se considera superado. La defensa se hace primero en el aula
  contra URSim y después en el laboratorio de robótica con un UR3e real.

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
- [x] C · `varios_robots.py` + `robots.json`: hilo receptor por robot, `Lock`, un único bucle de dibujo
  - Probado con las dos VMs: ambos siguen a su URSim; red a `.73` cortada 10 s → su etiqueta pasa a
    roja "SIN DATOS" y se congela, `URSim_1` sigue moviéndose; al volver la red reconecta solo
- [ ] D · enseñar y reproducir (URScript, `movej`)
