# Enseñar y reproducir (bloque D)

Scripts: `visualizador/ensenar_reproducir.py` (un robot) y
`visualizador/ensenar_reproducir_varios.py` (varios robots).

> Con un robot real: prueba antes la secuencia en URSim y ten al profesor
> presente con la seta al alcance.

## Qué hace

1. **Enseñar:** guarda la postura actual del robot (o la de los deslizadores) como punto.
2. **Previsualizar:** un robot fantasma recorre la secuencia sin mover el real.
3. **Ejecutar:** envía un `movej` por punto y espera a que termine antes del siguiente.
4. **Supervisar:** ante un error o una parada de protección se detiene y muestra el motivo.
5. **Guardar y cargar:** la secuencia se guarda en JSON.

## Controles

| Tecla | Acción |
|---|---|
| Espacio | Guardar la postura actual como punto |
| ← / → | Recorrer los puntos (el fantasma muestra el seleccionado) |
| B | Borrar el punto seleccionado (también Supr o Retroceso) |
| D | Añadir un punto con los deslizadores |
| P | Previsualizar |
| Enter | Ejecutar o reanudar tras un error |
| Esc | Parar (`stopj`) y cancelar |
| G / C | Guardar / cargar `secuencias/secuencia.json` |
| E | Provocar un error de prueba (`protective_stop()`) |
| S | Mostrar u ocultar los deslizadores |

**Varios robots:** `1..9` cambia el robot activo sin detener los demás.
`A` ejecuta todas las secuencias a la vez. `L` activa el bucle del robot activo.
Cada robot guarda su secuencia en `secuencias/secuencia_<nombre>.json`.

## Cómo funciona

### Enviar órdenes

Las órdenes son texto URScript terminado en `\n`, enviado por el mismo socket
del puerto 30001 que se lee:

```text
movej([q0, q1, q2, q3, q4, q5], a=0.5, v=0.3)
```

Un programa nuevo aborta el que está en marcha. Por eso no se envía el
siguiente `movej` hasta confirmar el anterior.

### Confirmar una orden

El robot no responde a las órdenes. El programa lo deduce del estado:

1. `isProgramRunning` pasa a verdadero en menos de 2 s. Si no, la orden se rechazó.
2. Mientras sea verdadero, el robot se mueve.
3. Al volver a falso, cada `q_actual` debe estar a menos de 0,01 rad del objetivo.

### Detectar errores

Hacen falta tres vías, porque cada fallo se ve por una distinta:

| Fallo | Cómo se detecta |
|---|---|
| Error del robot o excepción de programa | Mensaje tipo 20, subtipos 6 o 10 |
| Parada de protección | `isProtectiveStopped` |
| URScript roto en una línea | No llega nada: el programa no arranca en 2 s |
| Parada desde PolyScope o `stopj` | Termina lejos del objetivo |

El subtipo 6 puede llegar sin texto; entonces se muestra el código (por ejemplo `C209A0`).
Al reanudar tras una parada de protección se desbloquea por el dashboard
(puerto 29999, `unlock protective stop`) y se reenvía el punto.

### Campos del estado

| Dato | Dónde | Byte |
|---|---|---|
| `isProtectiveStopped` | Subpaquete 0 | 12 |
| `isProgramRunning` | Subpaquete 0 | 13 |
| `robotMode` (7 = RUNNING) | Subpaquete 0 | 15 |
| `q_actual` × 6 | Subpaquete 1 | `41 · j` (double) |

### Arquitectura

```text
hilo receptor -> último estado (con Lock) + cola de errores
bucle principal a 30 FPS: teclas -> máquina de estados -> dibujo
```

El hilo receptor nunca toca PyBullet. Así la ventana no se congela si la red se corta.

### Máquina de estados

```text
REPOSO --Enter--> ENVIANDO --arranca--> MOVIENDO --último punto--> REPOSO
  |                                        |  otro punto -> ENVIANDO
  P -> PREVISUALIZANDO -> REPOSO           |  error / parada / lejos del objetivo
                                           v
REPOSO <--Esc-- DETENIDO --Enter (reanudar)--> ENVIANDO
```

### Fichero de secuencia

Lista de puntos con 6 ángulos en radianes. Al cargar se rechazan valores
fuera de ±2π, NaN o no numéricos.

```json
[
    [0.0, -1.5708, 0.0, -1.5708, 0.0, 0.0],
    [0.5, -1.2, 1.0, -1.4, -1.5708, 0.0]
]
```

## Requisitos en el robot

Encendido, frenos liberados, `robotMode` = 7 y **modo remoto** activado.
Si en modo remoto PolyScope no deja mover el robot, enseña en Local y
cambia a Remoto para ejecutar, o enseña con los deslizadores (D).

## Guion de la defensa

### Aula (URSim)

1. Lanza `ensenar_reproducir.py` y comprueba que sigue a URSim.
2. Enseña 4 puntos con Espacio y uno con D.
3. Recórrelos con ← → y explica el fantasma.
4. Previsualiza (P).
5. Ejecuta (Enter) y explica la confirmación de cada punto.
6. Pulsa E durante la ejecución: se detiene con el motivo. Reanuda con Enter o cancela con Esc.
7. Guarda (G), reinicia el programa, carga (C) y ejecuta.

### Laboratorio (UR3e real)

1. Pon el robot asignado el primero en `robots.json`.
2. Comprueba la conexión con `test_conexion.py` y `MOVER = False`.
3. Comprueba que la pantalla sigue al robot sin enviar órdenes.
4. Ejecuta solo con autorización del profesor.

### Preguntas del apartado 12

- **(S) 9.** Por qué un `movej` enviado no garantiza la llegada: ver *Confirmar una orden*.
- **(S) 10.** Riesgo de que cualquiera envíe programas al puerto 30001: proponer una medida
  en el robot y otra en la red.
