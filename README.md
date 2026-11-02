# Visualizador de un UR3e por TCP/IP

## Qué hace

Cuatro programas en Python que leen por la red el estado de un brazo UR3e (real o URSim) y lo muestran en 3D con PyBullet. Van de menos a más, uno por nivel del enunciado:

| Script | Nivel | Qué hace |
|---|---|---|
| `primaria.py` | Aprobado (A) | Lee el puerto 30001 (10 mensajes/s) y mueve el robot de la pantalla |
| `tiempo_real.py` | Aprobado (B) | Lo mismo por el puerto 30003 (500 paquetes/s) |
| `varios_robots.py` | Notable (C) | Varios robots en la misma ventana, un hilo por robot |
| `ensenar_reproducir.py` | Sobresaliente (D) | Enseña una secuencia de puntos, la previsualiza y la ejecuta con `movej`, confirmando cada punto |

**Cada script es un único fichero que no importa a ningún otro.** Se puede leer, explicar y entregar por separado. Por eso algunas funciones (`leer_robot`, `cortar_mensajes`…) aparecen copiadas en varios ficheros.

```
entrega/                 lo que pide el enunciado
  primaria.py
  tiempo_real.py
  varios_robots.py
  ensenar_reproducir.py
  robots.json            IP y posición de cada robot
  secuencia.json         secuencia de ejemplo de ensenar_reproducir.py
  panel_web.py           editar robots.json y lanzar los scripts desde el navegador
  visualizador_ur3e      panel_web.py empaquetado para Linux (se descarga de Releases, no está en git)
extras/
  prueba_robustez.py     prueba los parsers y la máquina de estados sin robot
  linux.sh, windows.bat  preparan el entorno la primera vez y abren el panel
  compilar_linux.sh      compila entrega/visualizador_ur3e, el ejecutable de Linux
material/
  ur3e_rg2-0.1.0-py3-none-any.whl   el visualizador que da la asignatura
```

## Instalación

Como dice el enunciado (apartado 9), con Python 3.9 o posterior:

```
python -m venv .venv
.venv/bin/pip install material/ur3e_rg2-0.1.0-py3-none-any.whl       (Linux)
.venv\Scripts\pip install material\ur3e_rg2-0.1.0-py3-none-any.whl   (Windows)
```

La wheel instala también `pybullet`, `pybullet_planning` y `numpy`. VS Code detecta solo el entorno `.venv`.

Otra opción es `extras/linux.sh` (o doble clic en `extras/windows.bat`), que hace esto mismo la primera vez y después abre el panel web.

## Configurar los robots

Los robots están en `entrega/robots.json`, y se cambian ahí sin tocar el código:

```json
[
    {"nombre": "URSim_1", "host": "10.172.18.73", "posicion": [0.0, 0.0, 0.0]},
    {"nombre": "URSim_2", "host": "10.172.18.67", "posicion": [1.0, 0.0, 0.0]}
]
```

- `host`: la IP del robot. En el aula, la VM de URSim (red `10.172.18.x`). En el laboratorio, el UR3e real (`10.172.21.203` a `.206`).
- `posicion`: dónde se dibuja la base del robot en la escena, en metros. Solo la usa `varios_robots.py`.
- `primaria.py`, `tiempo_real.py` y `ensenar_reproducir.py` usan **solo el primer robot** de la lista.

El puerto no va en `robots.json`, porque es de la interfaz y no del robot: cada script lleva el suyo.

## Uso

Abre el script en VS Code y pulsa **F5**. Cada uno tiene arriba un bloque `CONFIGURACIÓN` con las constantes que se pueden cambiar. Se para con Ctrl+C o cerrando la ventana de PyBullet.

`MODO` muestra en la consola lo que pide cada hito del enunciado:

| Script | `MODO` | Hito | Qué escribe |
|---|---|---|---|
| `primaria.py` | `"bytes"` | A1 | Cuántos bytes devuelve cada `recv()` |
| | `"mensajes"` | A2, A3 | Longitud y tipo de cada mensaje y de sus subpaquetes |
| | `"angulos"` | A4, A5 | Los 6 `q_actual` en grados, una vez por segundo |
| `tiempo_real.py` | `"paquetes"` | B1 | Bytes de cada `recv()` y longitud de cada paquete |
| | `"angulos"` | B2, B3 | Paquetes por segundo y `q_actual` |

### Enseñar y reproducir

Las teclas se pulsan con la ventana de PyBullet activa:

| Tecla | Qué hace |
|---|---|
| Espacio | Guarda la postura actual del robot como punto |
| B | Borra el último punto |
| P | Previsualiza: el robot fantasma (azul) recorre la secuencia sin mover el real |
| Enter | Ejecuta la secuencia, o la reanuda tras un error |
| Esc | Para el robot (`stopj`) y cancela |
| G / C | Guarda / carga `secuencia.json` |
| E | Provoca una parada de protección (`protective_stop()`) para la demostración |

Encima del robot se ven el modo, el último aviso, el número de puntos y las teclas que sirven en ese modo. Todo lo que pasa se escribe también en la consola.

Requisitos en el robot: encendido, con los frenos sueltos (`robotMode` = 7, RUNNING) y, en PolyScope 5, en modo **Remoto** si el control remoto está activado. Para enseñar puntos desde la pestaña Mover hay que estar en Local, y después pasar a Remoto para ejecutar.

En el robot real, las órdenes van como máximo a 0,3 rad/s y 0,5 rad/s². `V` y `A` no pueden pasar de esos valores: si los pasan, el script no arranca. La secuencia se prueba antes en URSim, y el profesor tiene que estar presente con la seta al alcance.

### Panel web

`panel_web.py` (F5 o `python entrega/panel_web.py`) abre el navegador con una página que permite:

- editar `robots.json` (para borrar un robot se vacía su nombre; para añadir uno se rellena la última fila);
- iniciar y detener cada script;
- ver lo que escribe cada script en la consola, actualizado cada segundo.

**Salir** detiene los scripts en marcha y cierra el panel.

### Ejecutable de Linux

`entrega/visualizador_ur3e` es el panel web empaquetado en un único ejecutable para Linux x86-64. Lleva dentro Python, PyBullet y el visualizador, así que no hay que instalar nada. Se compila sobre Debian 11 (glibc 2.31) y funciona en Ubuntu 20.04 o posterior.

1. Descárgalo de [Releases](../../releases/latest) y déjalo en `entrega/`, junto a los `.py` y `robots.json`.
2. Ábrelo con doble clic o con `chmod +x visualizador_ur3e && ./visualizador_ur3e`.
3. Se abre el panel en el navegador, igual que con `panel_web.py`.

Los scripts no van dentro del ejecutable: los lee de su carpeta. Por eso se pueden cambiar los `.py` o `robots.json` sin volver a compilar. Para lanzar un script, el ejecutable se llama a sí mismo con el nombre del script y hace de `python`. Cada script tarda unos segundos más en arrancar que con Python, porque el ejecutable se descomprime cada vez.

El ejecutable no está en el repositorio, porque ocupa unos 95 MB: se sube como descarga en Releases. Para volver a compilarlo hace falta podman y ejecutar `extras/compilar_linux.sh`. Antes, cierra con **Salir** cualquier `visualizador_ur3e` abierto: si está en marcha, el fichero no se puede sobrescribir (`Text file busy`).

Al compilar se dejan fuera `libstdc++` y `libgcc_s`. Las de Debian 11 son demasiado viejas para el driver gráfico (Mesa) de un Linux actual, y PyBullet fallaba con `Failed to retrieve a framebuffer config`. Así el ejecutable usa las del sistema, que cualquier Linux con escritorio trae.

## Cómo funciona

### TCP no respeta los mensajes

TCP entrega un flujo de bytes: un `recv()` puede devolver medio mensaje, uno entero o varios juntos. Por eso ningún script trata un `recv()` como un mensaje. Todos siguen el algoritmo del apartado 8:

1. `recv()` y añadir lo recibido al final de un `bytearray`. Si devuelve 0 bytes, el robot ha cerrado la conexión.
2. Mientras el buffer tenga una cabecera, leer sin quitarla la longitud L (int de 4 bytes, big-endian).
3. Si el buffer tiene menos de L bytes, el mensaje aún no ha llegado entero: volver a `recv()`.
4. Si tiene L o más, cortar los primeros L bytes (el mensaje) y quitarlos del buffer. Volver al paso 2.

Es la función `cortar_mensajes` (en `tiempo_real.py`, `cortar_paquetes`). Una L menor que la cabecera o mayor que 64 KiB significa que el buffer está desalineado: se lanza `ConnectionError` y el script reconecta.

### Interfaz primaria (30001)

```
mensaje   [longitud 4 B][tipo 1 B = 16][subpaquete][subpaquete]...
subpaquete       [tamaño 4 B][tipo 1 B][datos]
Joint data (tipo 1)  6 × [q_actual d][q_target d][qd_actual d][I f][V f][T f][T_micro f][modo B] = 6 × 41 B
```

- Solo interesan los mensajes de tipo 16 (estado). Los demás se saltan, salvo el de versión (tipo 20, subtipo 3), que se escribe en la consola.
- Dentro del mensaje, cada subpaquete se salta sumando su tamaño hasta llegar al tipo 1. Si un subpaquete se sale del mensaje, el mensaje está corrupto y se deja de leer.
- El subpaquete de articulaciones mide 5 + 6 × 41 = 251 B. Si mide otra cosa, se avisa y no se lee.
- `q_actual` de la articulación j es el `double` en el byte `5 + 41·j` del subpaquete.

### Interfaz de tiempo real (30003)

Un solo tipo de paquete, de estructura fija: la cabecera es solo la longitud (no hay tipo) y los 6 `q_actual` empiezan siempre en el byte 252. La longitud cambia con la versión del robot (URSim 5.25 envía 1220 B), así que se lee de cada paquete.

Llegan unos 500 paquetes por segundo. `tiempo_real.py` lee todos los que trae cada `recv()`, se queda con el último y dibuja como mucho `FPS` (30) veces por segundo. Si dibujara cada paquete, se quedaría atrás y el robot de la pantalla iría cada vez con más retraso.

### Varios robots: hilos y Lock

```
hilo receptor robot 1 ─┐
hilo receptor robot 2 ─┼─> robot["q"] (protegido con lock) ─> bucle de dibujo ─> PyBullet
```

- Cada robot tiene su hilo, con su socket y su buffer. Si un robot se cuelga, solo se bloquea su hilo.
- El hilo solo guarda el último `q` y la hora de llegada en el diccionario de su robot. Lo hace dentro de `with lock:` para que el dibujo nunca lea un `q` de un instante con la hora de otro.
- Solo el bucle principal llama a PyBullet, 30 veces por segundo.
- Si un robot lleva más de 1 s sin datos, su nombre pasa a rojo «SIN DATOS» y se queda quieto. Los demás siguen.

### Enviar órdenes y confirmarlas

Las órdenes son texto URScript terminado en `\n`, enviado con `sendall()` por el mismo socket del 30001 del que se lee. El hilo receptor lee y el bucle principal escribe: una conexión TCP va en los dos sentidos.

```
movej([q0, q1, q2, q3, q4, q5], a=0.5, v=0.3)
```

El robot no contesta a las órdenes, así que el cumplimiento se deduce de su estado (subpaquete 0, Robot mode data):

1. Tras enviar, `isProgramRunning` (byte 13) tiene que pasar a verdadero en menos de 2 s. Si no pasa, la orden se ha rechazado.
2. Mientras sea verdadero, el robot se mueve. No se envía otra orden, porque abortaría la que está en marcha.
3. Cuando vuelve a falso, cada `q_actual` tiene que estar a menos de 0,01 rad del objetivo. Solo entonces se envía el punto siguiente.

### Máquina de estados

`Aplicacion.actualizar()` se ejecuta en cada fotograma, mira el estado y decide. Nunca se queda esperando al robot, así que la ventana no se congela.

```
REPOSO ──Enter──> ENVIANDO ──programa en marcha──> MOVIENDO ──ha llegado──> ENVIANDO (siguiente)
  │                  │                               │                       o REPOSO (último)
  │ P                └──────── error o parada ───────┴──> DETENIDO ──Enter──> REANUDANDO ──> ENVIANDO
  v
PREVISUALIZANDO ──fin──> REPOSO               Esc (en cualquier modo) ──> REPOSO
```

La secuencia pasa a DETENIDO y muestra el motivo si pasa cualquiera de estas cosas:

| Fallo | Cómo se ve |
|---|---|
| Error del robot o excepción del programa | Mensaje tipo 20, subtipo 6 (código `C209A0`…) o 10 (línea y columna) |
| Parada de protección o de emergencia | `isProtectiveStopped` / `isEmergencyStopped` en el subpaquete 0 |
| Robot apagado o con frenos | `robotMode` distinto de 7 |
| Orden rechazada (modo local, URScript erróneo) | El programa no arranca en 2 s |
| Parada desde PolyScope o `stopj` | El programa termina lejos del objetivo |
| Red perdida | Más de 1 s sin estado |

Al reanudar con Enter tras una parada de protección, se desbloquea con el dashboard server (puerto 29999, `unlock protective stop`) y se reenvía el punto pendiente. Una parada de emergencia no se desbloquea nunca por red: la tiene que rearmar una persona en el robot.

## Robustez

| Situación | Qué hace |
|---|---|
| `robots.json` no existe o está mal escrito | Termina con un mensaje que dice qué falla, sin traceback |
| Robot apagado, URSim reiniciado o cable cortado | Lo avisa y reconecta cada 2 s. Si el robot deja de enviar sin cerrar la conexión, se da por perdida a los 5 s (`TIMEOUT`) |
| Mensaje truncado o con bytes erróneos | Se descarta o se reconecta. Nunca deja el programa colgado |
| Ángulo NaN | No se dibuja ni se envía |
| Ventana de PyBullet cerrada | El script termina |
| Ctrl+C, ventana cerrada o fallo con el robot en marcha | `ensenar_reproducir.py` envía `stopj(2)` antes de salir |
| Punto fuera de ±2π (por ejemplo, en grados) | Nunca se envía. `secuencia.json` con puntos no válidos no se carga |

## Pruebas

```
.venv/bin/python extras/prueba_robustez.py
```

Funciona sin robot y debe terminar en `TODO OK`. Mete 20 000 mensajes truncados, cambiados o aleatorios en los parsers de cada script y comprueba que solo fallan con `OSError` (el error que hace reconectar). También comprueba la máquina de estados con un robot falso: confirmación de cada punto, parada por error, reanudación, `stopj` con Esc, que no se mueve en parada de protección y que un punto en grados no se envía. Es el único `.py` que importa a los demás, porque es su prueba.

Probado el 2026-11-02 contra URSim 5.25 (`10.172.18.73`):

- `primaria.py`: versión `URControl 5.25`, ángulos iguales a los de PolyScope, subpaquetes que suman la longitud del mensaje menos 5.
- `tiempo_real.py`: unos 480 paquetes/s de 1220 B, con los mismos ángulos que la primaria.
- `varios_robots.py`: un URSim en verde moviéndose y otro apagado (`10.172.18.67`) en rojo «SIN DATOS», sin frenar al primero.
- `ensenar_reproducir.py`, con teclas reales en la ventana: cargar, previsualizar, ejecutar 4 puntos, provocar una parada con E (`C209A0`), reanudar con Enter y terminar la secuencia. Ctrl+C a mitad de un movimiento envía `stopj` y el robot se para.
- Reconexión de `primaria.py` y `tiempo_real.py` con un robot falso que corta la conexión, que se cuelga sin enviar nada (timeout a los 5 s) y que rechaza la conexión.
- `panel_web.py`: guardar robots (y rechazar una fila mal escrita), iniciar, ver la salida y detener los cuatro scripts con un final limpio (`Fin`, código 0).

## Decisiones y por qué

- **Cada script en un solo fichero.** En la defensa hay que explicar cualquier línea. Un fichero que no depende de otros se lee de arriba abajo sin saltar entre ficheros. A cambio, unas pocas funciones cortas aparecen copiadas.
- **El bucle del enunciado escrito tal cual** (`recv` → buffer → cortar por longitud), con un `try` alrededor que reconecta. Todos los errores de red (`ConnectionError`, timeout, conexión rechazada) son `OSError`, así que basta un solo `except`.
- **Los parsers comprueban las longitudes antes de leer.** Un mensaje corrupto devuelve `None` y se ignora. Un buffer desalineado lanza `ConnectionError` y el script reconecta. Así un byte erróneo nunca rompe el bucle con un `IndexError` o un `struct.error`.
- **`TAM_RECV = 65536`.** Es el máximo de bytes que devuelve cada `recv()`, no el tamaño de un mensaje: el buffer junta o corta lo que llegue. Pedir más de lo que hay no da más datos (el sistema tiene unos 64-128 KiB de buffer de recepción), y pedir poco obliga a dar más vueltas cuando hay atasco. Coincide con `MAX_LONGITUD`, así que cabe el mensaje más largo que se acepta.
- **`struct` con `>`.** El robot envía en big-endian. Sin `>`, Python lee en el orden del PC y salen ángulos absurdos.
- **Se pasa una copia a `move_robot`** (`list(q)`). El módulo alarga la lista que recibe hasta 12 valores, y `q` se sigue usando después.
- **Sin corrección del convenio de ángulos.** Se comprobó que el modelo de PyBullet usa los mismos orígenes y sentidos que el robot (error en la herramienta menor de 0,1 mm), así que los ángulos se pasan tal cual.
- **El fantasma de `ensenar_reproducir.py` es un segundo UR3e en la misma base, azul y semitransparente.** Muestra el punto al que va el robot, o recorre la secuencia en la previsualización.
- **Textos fijos encima del robot.** PyBullet solo sabe escribir texto en el espacio 3D. Ponerlo en una posición fija es lo más sencillo, y la cámara empieza enfocada a esa zona. Se quitan las tildes porque PyBullet corta el texto en la primera letra no ASCII.
- **Las órdenes se envían por el mismo socket del que se lee**, como recomienda el enunciado. Una segunda conexión obligaría a leer y tirar todo lo que el robot envía por ella.
- **Panel web sin JavaScript**, como el del cliente Modbus. Es un formulario HTML. La salida está en un marco que se recarga solo. No sabe nada de robots: lanza cada script en un proceso aparte, como desde una terminal.
- **Detener desde el panel manda Ctrl+C (SIGINT) en Linux**, para que el script termine como en la terminal y `ensenar_reproducir.py` pare el robot. Windows no permite mandar Ctrl+C a otro proceso, así que allí se termina sin más (ver límites).

## Límites conocidos

- En Windows, **Detener** en el panel termina el script sin que se ejecute su `stopj` final. Si `ensenar_reproducir.py` estaba moviendo el robot, este acaba el `movej` en curso y se para. Para parar a mitad de camino, pulsa Esc en la ventana de PyBullet.
- Los scripts de un robot cogen siempre el primero de `robots.json`. Para usar otro, hay que ponerlo el primero.
- En `ensenar_reproducir.py`, B borra solo el último punto. No se puede insertar ni editar un punto en medio de la secuencia.
- Si el dashboard no consigue desbloquear la parada de protección, a los 5 s la secuencia vuelve a DETENIDO con el motivo. Hay que revisar el robot y volver a pulsar Enter.
- `extras/windows.bat` no se ha probado en Windows.
