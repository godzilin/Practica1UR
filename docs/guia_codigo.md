# Guía de lectura del código

## Orden recomendado

1. `visualizador/primaria.py`: base común. Lee `cargar_robots`, `cortar_mensajes`,
   `subpaquetes` y `leer_estado`.
2. `visualizador/test_conexion.py`: envía un `movej` y lo confirma con el estado.
3. `visualizador/tiempo_real.py`: paquetes de longitud fija; solo dibuja el último.
4. `visualizador/varios_robots.py`: un hilo receptor por robot y un `Lock`.
5. `visualizador/ensenar_reproducir.py`: aplicación completa con máquina de estados.
6. `visualizador/ensenar_reproducir_varios.py`: la misma aplicación, una por robot.

## TCP no respeta los mensajes

Un `recv()` puede devolver medio mensaje o varios juntos. Por eso cada script
acumula bytes en un buffer y corta por la longitud de la cabecera.

- **Primaria (30001):** cada mensaje empieza por 4 bytes de longitud y 1 de tipo.
  Los subpaquetes repiten ese formato.
- **Tiempo real (30003):** cada paquete empieza por su longitud. Los seis
  `q_actual` están en el byte 252. Llegan 500 por segundo y se dibuja a 30 FPS.

## Hilos

Cada robot tiene un hilo receptor. El hilo guarda el último estado bajo un
`Lock` y mete los errores en una cola para no perder ninguno.
Solo el hilo principal llama a PyBullet y envía órdenes.

## Máquina de estados (bloque D)

`Aplicacion.paso_maquina` nunca espera al robot: en cada fotograma mira el estado y decide.

```text
REPOSO -> ENVIANDO -> MOVIENDO -> ENVIANDO -> REPOSO
                         |
                       DETENIDO -> ENVIANDO (reanudar)
```

Detalles y teclas en [`ensenar_reproducir.md`](ensenar_reproducir.md).

## Pruebas

```text
python visualizador/prueba_robustez.py
python -m py_compile comprobar_dependencias.py web_dashboard.py visualizador/*.py
```

`prueba_robustez.py` no necesita robot: mete mensajes truncados, aleatorios y
con NaN en el parser, y prueba `robots.json` erróneos.
El resto de scripts necesita un URSim o un UR3e accesible.
