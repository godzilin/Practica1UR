# Guía de lectura del proyecto

Esta guía acompaña a los comentarios didácticos de los scripts. La práctica
visualiza un UR3e a partir de dos interfaces TCP distintas y conserva una
separación clara entre protocolo, conexión, simulación y lógica de aplicación.

## Orden recomendado

1. `comprobar_dependencias.py`: comprueba el entorno local sin descargar nada.
2. `visualizador/primaria.py`: es la base común. Conviene leer primero
   `cargar_robots`, `cortar_mensajes`, `subpaquetes` y `leer_estado`.
3. `visualizador/test_conexion.py`: muestra una ejecución bloqueante sencilla y
   cómo se confirma una orden con el estado del robot.
4. `visualizador/tiempo_real.py`: cambia a paquetes de longitud fija y conserva
   solo el estado más reciente para que la visualización no acumule retraso.
5. `visualizador/varios_robots.py`: generaliza el receptor a varios robots y
   usa un `Lock` para compartir el último estado.
6. `visualizador/ensenar_reproducir.py`: añade la aplicación completa, con
   teclado, secuencias, fantasma, errores y máquina de estados.

Los ficheros de `antiguos/` son ejemplos previos de aprendizaje. `memoria/`
contiene scripts de generación de documentos y figuras, no código necesario
para conectar con el robot.

## El límite de TCP no es el límite del mensaje

TCP entrega un flujo de bytes. Un `recv()` puede devolver medio mensaje, un
mensaje y medio o varios mensajes juntos. La interfaz primaria pone al inicio
de cada mensaje una longitud de 4 bytes y un tipo de 1 byte. Por eso
`cortar_mensajes` mantiene un `bytearray`, espera a tener la longitud indicada
y solo entonces extrae el mensaje. Los subpaquetes de estado repiten el mismo
patrón de longitud y tipo.

La interfaz de tiempo real usa otra regla: cada paquete empieza por su longitud
y los seis `q_actual` están en el byte 252. `cortar_paquetes` aplica esa regla,
pero el dibujo se hace a 30 FPS, no 500 veces por segundo.

## Hilos y acceso a PyBullet

Los receptores pueden bloquearse esperando red, así que cada robot tiene su
propio hilo en los bloques C y D. El `Lock` protege el intercambio de datos y la
cola de errores evita que un mensaje importante se pierda entre dos fotogramas.
Solo el hilo principal llama a PyBullet. Esta regla es especialmente importante
en `varios_robots.py` y `ensenar_reproducir.py`.

## Máquina de estados del bloque D

`Aplicacion.paso_maquina` no espera activamente al robot. En cada fotograma
comprueba errores, conexión, parada de protección, `robotMode`,
`isProgramRunning` y distancia al objetivo. Las transiciones principales son:

```text
REPOSO -> ENVIANDO -> MOVIENDO -> ENVIANDO -> REPOSO
                         |
                       DETENIDO -> REANUDANDO -> ENVIANDO
```

`Esc` envía `stopj` también desde `DETENIDO`, porque una pérdida de red puede
haber dejado un movimiento activo. Una parada de emergencia no se desbloquea
por red; una parada de protección sí puede desbloquearse mediante el dashboard,
si el estado del robot lo permite.

## Validación y pruebas

`visualizador/prueba_robustez.py` construye mensajes válidos y los altera con
truncados, bytes aleatorios y `NaN`. También prueba configuraciones inválidas
de `robots.json`. El parser debe fallar solo con excepciones que el receptor
captura para reconectar.

Pruebas rápidas:

```text
python visualizador/prueba_robustez.py
python -m py_compile comprobar_dependencias.py visualizador/*.py antiguos/*.py memoria/*.py
```

La prueba de robustez no necesita robot. Los demás scripts necesitan las
dependencias instaladas y, para leer datos, un URSim o un UR3e accesible.

## Generación de la memoria

Ejecutar `memoria/figuras.py` cuando cambien los datos de `memoria/datos/` y
después `memoria/generar_memoria.py`. Ambos scripts escriben dentro de
`memoria/`; las figuras se generan con backend no interactivo para que también
funcionen desde una terminal sin servidor gráfico.