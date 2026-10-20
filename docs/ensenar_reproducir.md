# Mini-aplicación «Enseñar y reproducir» · Bloque D (sobresaliente)

Documento de diseño: qué pide el enunciado, cómo lo resolvemos y cómo se demuestra en la defensa.
Script: `visualizador/ensenar_reproducir.py`.

La variante multi-robot se encuentra en `visualizador/ensenar_reproducir_varios.py`.
Mantiene una instancia independiente de esta aplicación para cada robot y
comparte únicamente la escena de PyBullet.

> Antes de ejecutar con un robot real, leer la sección de seguridad y validar la
> secuencia en URSim. Para conocer el resto del proyecto y el orden recomendado
> de lectura, consultar [`docs/guia_codigo.md`](guia_codigo.md).

## Lectura rápida del script

El fichero está dividido en cuatro capas. Las constantes del principio fijan
los límites de seguridad y los tiempos. Las funciones pequeñas convierten entre
radianes y PyBullet o validan puntos. `Robot` encapsula la conexión: un hilo
recibe estados y errores, mientras el programa principal envía órdenes por el
mismo socket. `Aplicacion` contiene la máquina de estados y separa las teclas,
la lógica de ejecución y el dibujo.

La regla importante es que el hilo receptor no toca PyBullet. Solo publica una
copia protegida por `Lock`; el bucle principal consume esa copia a 30 FPS.
Esto evita llamadas concurrentes a la biblioteca gráfica y permite detectar una
caída de red sin congelar la ventana.

## 1. Qué pide el enunciado

Apartados 10 (Bloque D) y 11 de *Práctica guiada: visualizador de un UR3e por TCP/IP*.

| Requisito | Detalle |
|---|---|
| Enseñar | Una tecla guarda la configuración actual (`q_actual` leído de la interfaz primaria) como punto de la secuencia. También se puede definir un punto con los deslizadores de PyBullet |
| Previsualizar | Ver en PyBullet qué va a hacer el robot antes de que lo haga |
| Ejecutar paso a paso | Un `movej` por punto. No se envía el siguiente hasta comprobar que el anterior ha terminado: `isProgramRunning` pasa a verdadero, vuelve a falso y `q_actual` queda a menos de 0,01 rad del objetivo |
| Supervisar | Si llega un mensaje de error (tipo 20, subtipos 6 o 10) o se activa `isProtectiveStopped`: se detiene la secuencia, se muestra el motivo y se espera a que el operador reanude o cancele |
| Guardar | La secuencia se guarda en un fichero y se carga en otra sesión |
| Límites en el robot real | Velocidad articular ≤ 0,3 rad/s, aceleración ≤ 0,5 rad/s², secuencia probada antes en URSim, profesor presente con la seta de emergencia al alcance |
| Defensa | Se enseña una secuencia de al menos 4 puntos, se previsualiza y se ejecuta. Se provoca un error y el programa lo muestra y se detiene |

## 2. Fundamentos que usamos

### Enviar órdenes

- Se envía **texto URScript** terminado en `\n` (sin él el controlador no ejecuta nada), con `sendall()`.
- Por el **mismo socket del puerto 30001** del que se lee el estado (recomendado por el enunciado).
  Los puertos de solo lectura (30011, 30012) no aceptan órdenes.
- Una orden suelta se ejecuta como un programa de una instrucción. Un programa nuevo **aborta** el que
  está en marcha: por eso no se envía el siguiente `movej` hasta confirmar el anterior.
- Orden usada: `movej([q0, q1, q2, q3, q4, q5], a=0.5, v=0.3)` (radianes, rad/s², rad/s).
  Para parar: `stopj(a)`.

### El robot no confirma las órdenes

El único acuse de recibo es el ACK de TCP: indica que los bytes han llegado, no que se hayan ejecutado.
La confirmación se deduce del estado que el robot sigue publicando (subpaquete 0, *Robot mode data*):

1. Tras enviar, `isProgramRunning` debe pasar a verdadero en 1–2 s. Si no, la orden se ha rechazado:
   buscar un mensaje tipo 20 que lo explique.
2. Mientras sea verdadero, el robot está ejecutando: no se envía otra orden.
3. Cuando vuelve a falso, se comprueba que `q_actual` está a menos de 0,01 rad del objetivo en cada
   articulación. Solo entonces la orden se da por cumplida.

Esta lógica ya está probada en `visualizador/test_conexion.py` (función `mover`), en versión bloqueante.

### Campos del estado que necesitamos

| Dato | Dónde | Byte (desde el inicio de los datos del subpaquete) |
|---|---|---|
| `isProtectiveStopped` | Subpaquete 0 | 12 |
| `isProgramRunning` | Subpaquete 0 | 13 |
| `robotMode` (7 = RUNNING) | Subpaquete 0 | 15 |
| `q_actual` × 6 | Subpaquete 1 | `41 · j` (double) |
| Error del robot | Mensaje tipo 20, subtipo 6 | texto desde el byte 32 del mensaje |
| Excepción de programa | Mensaje tipo 20, subtipo 10 | línea y columna en 15 y 19, texto desde el 23 |

### Condiciones previas en el robot

Encendido, frenos liberados, modo de seguridad Normal (`robotMode` = 7), **modo remoto** activado
(Ajustes → Sistema → Control remoto, y *Remoto* arriba a la derecha) y la interfaz habilitada y no en
solo lectura (Ajustes → Seguridad → Servicios). Las dos VMs URSim (`10.172.18.67` y `10.172.18.73`)
ya aceptan `movej` por el 30001: probado con `test_conexion.py`.

## 3. Arquitectura

El programa tiene que hacer a la vez cosas que bloquean: recibir del robot, esperar al operador y
mantener viva la ventana. Mismo patrón que la práctica 1 (ejemplo 2) y el bloque C:

```
hilo receptor ──> estado (q, programa_en_marcha, parada_proteccion, modo) + cola de errores ─┐
                                                                                           v
bucle principal (el único que llama a PyBullet y envía órdenes), a 30 FPS:
    1. lee las teclas de la ventana (p.getKeyboardEvents)
    2. avanza la máquina de estados de la secuencia
    3. dibuja el robot real, el fantasma y el texto de estado
```

- **Hilo receptor**: su socket del 30001 y su buffer. Guarda el último estado (protegido con `Lock`)
  y mete en una cola los mensajes de error (tipo 20, subtipos 6 y 10) para que no se pierda ninguno.
- **Bucle principal**: escribe las órdenes por el mismo socket (`sendall`). Un hilo lee y otro escribe:
  un socket TCP es bidireccional.
- **Teclado en la ventana de PyBullet**: no hace falta un hilo de teclado. Se desactivan los atajos
  propios de PyBullet (`configureDebugVisualizer(COV_ENABLE_KEYBOARD_SHORTCUTS, 0)`) para que todas las
  teclas queden libres. Funciona igual en Linux y Windows.
- **Reutilización** de `primaria.py`: `cargar_robots`, `cortar_mensajes`, `leer_estado`. El robot es el
  primero de `robots.json`.

### Dos robots en la misma base

| Robot | Aspecto | Qué muestra |
|---|---|---|
| Real | Opaco | Sigue al URSim / UR3e en todo momento |
| Fantasma | Semitransparente (`changeVisualShape`, alfa ≈ 0,3) | El punto seleccionado, la postura de los deslizadores o la previsualización |

Así se ve a la vez dónde está el robot y adónde va a ir.

**Previsualización**: el fantasma recorre la secuencia interpolando linealmente cada tramo en espacio
articular, que es como `movej` mueve el robot.

### Máquina de estados

```
           Enter                 isProgramRunning=True           llegó al punto (último)
 REPOSO ─────────> ENVIANDO ──────────────────────> MOVIENDO ─────────────────────────> REPOSO
   ^  │              │  (2 s sin arrancar)             │  llegó al punto (no último) -> ENVIANDO (siguiente)
   │  │ P            v                                 │
   │  └──> PREVISUALIZANDO ──(fin)──> REPOSO           │ error tipo 20 / parada de protección /
   │                                                   │ terminó lejos del objetivo
   │      Esc (cancelar)                               v
   └───────────────────────────────────────── DETENIDO (muestra el motivo)
                                                       │ Enter (reanudar): reenvía el punto actual
                                                       └──────────────> ENVIANDO
```

Nunca se bloquea esperando al robot: cada vuelta del bucle mira el estado y decide.

### Controles

| Tecla | Acción |
|---|---|
| **Espacio** | Enseñar: guardar la postura actual del robot como punto nuevo |
| **← / →** | Recorrer los puntos; el fantasma muestra el seleccionado |
| **B** | Borrar el punto seleccionado (también Supr/Retroceso si llegan) |
| **D** | Añadir un punto con la postura de los deslizadores |
| **P** | Previsualizar la secuencia con el fantasma |
| **Enter** | Ejecutar la secuencia / reanudar tras un error |
| **Esc** | Parar (`stopj`) y cancelar la secuencia |
| **G / C** | Guardar / Cargar `secuencias/secuencia.json` |
| **E** | Provocar un error para la demostración: envía `protective_stop()` |
| **S** | Mostrar u ocultar los paneles de PyBullet (deslizadores). Empiezan ocultos para dejar sitio al robot y a los textos |

En la ventana se muestra el estado (`REPOSO`, `MOVIENDO 2/4`, `DETENIDO: <motivo>`...), el número de
puntos y esta ayuda. La consola guarda el registro detallado.

### Variante multi-robot

En la versión multi-robot, `1..9` cambia el robot activo y `A` inicia todas las
secuencias que tengan puntos cargados. `L` activa o desactiva el bucle solo para
el robot activo. Cambiar de robot no envía `stopj` al robot anterior: cada
máquina de estados y cada bucle continúan de forma independiente.
Los deslizadores se muestran para el fantasma del robot activo, mientras que
los robots opacos siguen sus estados reales. La ventana muestra el estado
detallado solo del robot activo para evitar etiquetas duplicadas o solapadas.

### Fichero de secuencia

`visualizador/secuencias/secuencia.json`: lista de puntos, cada uno con sus 6 ángulos en radianes.

```json
[
    [0.0, -1.5708, 0.0, -1.5708, 0.0, 0.0],
    [0.5, -1.2, 1.0, -1.4, -1.5708, 0.0]
]
```

Al cargar se valida que cada punto tenga 6 números entre −2π y 2π.

## 4. Seguridad

- `V = 0.3` rad/s y `A = 0.5` rad/s² como constantes fijas: son los límites obligatorios del robot real.
- Antes de enviar, cada ángulo se valida entre −2π y 2π: un ángulo en grados (90 → más de 14 vueltas)
  se rechaza.
- Los puntos solo salen de posturas enseñadas o de los deslizadores, nunca de valores escritos a mano.
- Esc envía `stopj` en cualquier momento.
- En el robot real: secuencia probada antes en URSim y profesor presente con la seta al alcance.

## 5. Resultados de los experimentos (D0)

Medido contra URSim 5.25 (`10.172.18.67`), escuchando el puerto 30001 mientras se envían órdenes.

| Experimento | Qué envía el robot | Cómo lo detecta la aplicación |
|---|---|---|
| `movej` con 5 ángulos | Tipo 20 subtipo 10 (excepción): línea 1, columna 1, `type_not_list_size:6:` | Mensaje de error |
| `def p(): movej(no_existe) end` | Tipo 20 subtipo 10: línea 2, columna 9, `compile_error_name_not_found:no_existe:` | Mensaje de error |
| Una sola línea con sintaxis rota (`movej((`) o variable inexistente | **Nada**: ni error ni arranque de programa | `isProgramRunning` no pasa a verdadero en 2 s |
| `stopj(2)` a mitad de un `movej` (igual que parar desde PolyScope) | `isProgramRunning` vuelve a falso con la base en 31,9° y el objetivo en 48,1° | Terminó lejos del objetivo |
| `protective_stop()` a mitad de un `movej` | `isProtectiveStopped` = verdadero, tipo 20 subtipo 6 con código 209, nivel 2 y **sin texto**, y subtipo 5 (modo de seguridad) | Parada de protección y mensaje de error (se muestra el código `C209A0`) |
| Desbloqueo | Dashboard (29999): `unlock protective stop` → `Protective stop releasing`; después `close safety popup` | Al reanudar tras una parada de protección |

Otros mensajes tipo 20 observados: subtipo 7 (*key message*) con `PROGRAM_XXX_STARTED` / `PROGRAM_XXX_STOPPED`,
subtipo 12 y 17 al conectar. No son errores: se ignoran.

**Conclusiones para el diseño**

- Hacen falta las tres vías de detección: mensajes de error, `isProtectiveStopped` y la comprobación final de
  `q_actual`. Una orden mal escrita en una sola línea no genera ningún mensaje: solo se detecta porque el programa
  no arranca.
- El subtipo 6 puede venir sin texto: se muestra el código (`C<código>A<argumento>`).
- Error para la defensa: una tecla **E** que envía `protective_stop()` durante la ejecución. Es reproducible,
  se ve en PolyScope y prueba la detección por `isProtectiveStopped` y por mensaje. Al reanudar, la aplicación
  desbloquea la parada por el dashboard y reenvía el punto. También vale parar desde PolyScope.
- El fantasma con `changeVisualShape(rgbaColor=[0.2, 0.6, 1.0, 0.35])` en todos los enlaces se ve
  semitransparente y azul junto al robot real (comprobado con una captura de la ventana).

## 6. Plan de desarrollo

Cada fase se cierra con su comprobación contra URSim, un commit y un push.

| Fase | Qué | Cómo se comprueba | Estado |
|---|---|---|---|
| D0 | Experimentos: qué mensajes envía URSim ante un URScript erróneo y una parada de protección; transparencia en PyBullet | Ver tipos y subtipos con `primaria.py` en `MODO = "mensajes"` | Hecho (sección 5) |
| D1 | Esqueleto: hilo receptor con estado completo + bucle con teclado y texto en pantalla | El robot se mueve en la ventana y las teclas se reconocen | Hecho |
| D2 | Enviar un `movej` y confirmarlo sin bloquear | Un punto ejecutado y confirmado con la ventana fluida | Hecho |
| D3 | Enseñar: Espacio, deslizadores, ← →, B | 4 puntos guardados | Hecho |
| D4 | Previsualizar con el fantasma | El fantasma recorre la secuencia, el real no se mueve | Hecho |
| D5 | Ejecutar la secuencia completa | 4 puntos ejecutados, cada uno confirmado | Hecho |
| D6 | Supervisión: detener, mostrar el motivo, reanudar o cancelar | Error provocado → detenido con motivo → reanudar | Hecho |
| D7 | Guardar y cargar | Guardar, reiniciar el programa, cargar y ejecutar | Hecho |
| D8 | Ensayo de la defensa en URSim y checklist del robot real | Guion de la sección 6 completo | Ensayo automático hecho; falta el ensayo manual con teclado |

### Prueba automática del guion de la defensa

Un guion simula las teclas contra URSim (`10.172.18.67`) y recorre la defensa completa
(ejecutado el 2026-10-14):

| Paso | Resultado |
|---|---|
| Enseñar 4 puntos: 3 con Espacio moviendo URSim y 1 con D (deslizadores) | 4 puntos guardados; ← → recorre la lista |
| G | Secuencia guardada en JSON |
| P | El fantasma recorre los 4 tramos en 3,5 s; el robot real no se mueve |
| Enter | 4 puntos ejecutados, cada uno confirmado (`isProgramRunning` y `q_actual`) en 14 s |
| Enter y E a mitad del punto 1 | `DETENIDO: Error del robot C209A0` en 0,1 s |
| Enter (reanudar) tras 6 s | Dashboard: `Protective stop releasing`; reenvía el punto 1 y completa la secuencia |
| Enter y Esc a mitad | `stopj(2)`, el programa del robot se para, vuelve a REPOSO |
| C | 4 puntos cargados y validados |

**Falta comprobar a mano** (no se puede automatizar desde aquí): que las teclas se reciben con la
ventana de PyBullet activa (en especial que **Esc** no cierre la ventana) y que los textos se leen bien.
Si al usar la pestaña Mover de PolyScope el robot está en modo remoto y no deja moverlo, enseñar en
modo Local y pasar a Remoto para ejecutar, o enseñar con los deslizadores (D).

## 7. Guion para la defensa

### En el aula (URSim)

1. Lanzar `ensenar_reproducir.py` con F5. Comprobar que el robot de la ventana sigue a URSim.
2. **Enseñar 4 puntos**: mover URSim desde la pestaña Mover y pulsar Espacio en cada postura.
   Añadir uno más con los deslizadores (D).
3. Recorrer los puntos con ← → y explicar el fantasma.
4. **Previsualizar** (P): el fantasma recorre la secuencia; el robot real no se mueve.
5. **Ejecutar** (Enter): el robot va punto a punto. Explicar la confirmación de cada uno
   (`isProgramRunning` y `q_actual`).
6. **Provocar un error** durante la ejecución: tecla **E** (parada de protección, `protective_stop()`), o
   parar el programa desde PolyScope a mitad de un movimiento. El programa muestra el motivo y se detiene.
   Reanudar con Enter (desbloquea la parada y reenvía el punto) o cancelar con Esc.
7. **Guardar** (G), cerrar, volver a abrir, **cargar** (C) y ejecutar.

### En el laboratorio de robótica (UR3e real, con el profesor)

1. Poner el robot asignado el primero en `robots.json` (sin tocar el código).
2. Comprobar `ping` y el puerto 30001 (`test_conexion.py` con `MOVER = False`).
3. Primero solo leer: el robot de la pantalla sigue al real.
4. Ejecutar la secuencia solo con autorización del profesor y la seta al alcance.

### Preguntas del apartado 12 relacionadas

- **(S) 9.** ¿Por qué no basta con haber enviado un `movej` para saber que el robot ha llegado al punto?
  ¿Qué información del propio robot usáis para confirmarlo? → sección 2, *El robot no confirma las órdenes*, y sección 5.
- **(S) 10.** Cualquier equipo de la red puede conectarse al puerto 30001 y enviar un programa al robot.
  ¿Qué riesgo supone en una planta real? Proponed dos medidas, una en la configuración del robot y otra en
  la arquitectura de red.
