# Práctica visualizador UR3e por TCP/IP

Lee el estado de un UR3e (URSim o real) por TCP y lo dibuja en PyBullet.
El nivel más alto añade la mini-aplicación *Enseñar y reproducir*.

## Estructura

| Ruta                               | Contenido                                      |
| ---------------------------------- | ---------------------------------------------- |
| `visualizador/`                  | Scripts de la práctica y `robots.json`      |
| `web/`, `web_dashboard.py`     | Panel web local para lanzar los visualizadores |
| `docs/`                          | Guía del código y diseño del bloque D       |
| `memoria.pdf`, `preguntas.pdf` | Entrega escrita y respuestas del apartado 12   |
| `preparar_*`, `lanzador*`      | Preparan el entorno y abren el panel           |
| `comprobar_dependencias.py`      | Comprueba las librerías sin conexión         |

## Instalación

Los preparadores instalan `pybullet`, `pybullet-planning`, `numpy`, `matplotlib`,
`python-docx` y la wheel `material/ur3e_rg2-0.1.0-py3-none-any.whl`.

**Linux / macOS** (crea `.venv` en el proyecto):

```bash
./preparar_linux.sh
./lanzador.sh
```

**Windows** (descarga Python 3.11 portable en `python/`): doble clic en
`preparar_windows.bat` una vez y después en `lanzador_windows.bat`.

## Panel web

Los lanzadores comprueban las dependencias y abren `http://127.0.0.1:8765`.
Desde ahí se editan los robots y se inicia o detiene cada visualizador.

## Uso desde VS Code

Abre el script, cambia las constantes de `CONFIGURACIÓN` y pulsa F5.

Los robots (nombre e IP) están en `visualizador/robots.json`. Los scripts de un
solo robot usan el **primero** de la lista; los de varios robots usan todos.

| Script                           | Qué hace                                                                               |
| -------------------------------- | --------------------------------------------------------------------------------------- |
| `test_conexion.py`             | Lee versión, modo y `q_actual`. Con `MOVER = True` gira la base y vuelve           |
| `primaria.py`                  | Visualizador por el puerto 30001. `MODO`: `"angulos"`, `"bytes"` o `"mensajes"` |
| `tiempo_real.py`               | Visualizador por el puerto 30003 (500 Hz). `MODO`: `"angulos"` o `"paquetes"`     |
| `varios_robots.py`             | Varios robots en la misma ventana                                                       |
| `ensenar_reproducir.py`        | Enseñar y reproducir con un robot                                                      |
| `ensenar_reproducir_varios.py` | Enseñar y reproducir con varios robots                                                 |
| `configurar_robots.py`         | Edita `robots.json` y guarda una copia `.bak`                                       |
| `prueba_robustez.py`           | Prueba el parser sin robot; debe acabar en `TODO OK`                                  |

Teclas y funcionamiento de *Enseñar y reproducir*: [`docs/ensenar_reproducir.md`](docs/ensenar_reproducir.md).
Orden de lectura y protocolo: [`docs/guia_codigo.md`](docs/guia_codigo.md).

## Red

- URSim (VirtualBox, modo puente)
- UR3e reales (laboratorio)

## Robustez

| Situación                                                       | Respuesta                                                              |
| ---------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `robots.json` ausente o mal escrito                            | Mensaje que dice qué arreglar                                         |
| Robot caído, URSim reiniciado o cable cortado                   | Reintenta cada 2 s. Aperece un mensaje encima del robot ("SIN DATOS") |
| Mensaje truncado, corrupto o con NaN                             | Se descarta o se reconecta.                                            |
| Ventana de PyBullet cerrada                                      | El programa termina                                                    |
| Error, parada de protección o red perdida durante una secuencia | Pasa a DETENIDO con el motivo                                          |
| Parada de emergencia                                             | DETENIDO. Solo la rearma una persona                                   |
| Ctrl+C, Esc o fallo con el robot en marcha                       | Envía `stopj` antes de salir                                        |
| `V`/`A` por encima de 0,3 rad/s y 0,5 rad/s²                | `ensenar_reproducir.py` no arranca                                   |
| Secuencia con puntos no válidos                                 | No se carga ni se envía                                               |

## Evaluación (apartado 11)

Cada nivel exige los anteriores y se supera entero o no se supera.

| Nota | Requisitos                                                                                                                                             | Defensa                                                                       |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| 5    | `primaria.py` (30001) y `tiempo_real.py` (30003) mueven el UR3e de PyBullet con los 6 `q_actual`, con buffer y mensajes delimitados por longitud | El simulado sigue a URSim y no se cuelga al reiniciarlo                       |
| 7    | Un script con al menos dos robots, configurados sin tocar el código. Si uno cae, los demás siguen                                                    | Dos robots a la vez; después se desconecta uno                               |
| 10   | Envío de órdenes y *Enseñar y reproducir* en URSim, validado en un UR3e real                                                                      | Secuencia de 4 puntos: previsualizar, ejecutar, provocar un error y detenerse |

En el robot real: máximo 0,3 rad/s y 0,5 rad/s², secuencia probada antes en
URSim y profesor presente con la seta al alcance.

## Estado

- [X] A · `primaria.py`: ángulos verificados (error del TCP < 0,1 mm) y reconexión probada
- [X] B · `tiempo_real.py`: URSim 5.25 envía paquetes de 1220 B a ~480/s
- [X] C · `varios_robots.py`: probado con las dos VMs y cortando la red de una
- [X] D · `ensenar_reproducir.py`: probado en URSim con teclado
  - [X] Validación en un UR3e real con el profesor
- [X] Robustez (14/10/2026): mensajes rotos, robot falso, cortes de red y secuencias corruptas
  - Sin probar: parada de emergencia (URSim no la provoca por red)
