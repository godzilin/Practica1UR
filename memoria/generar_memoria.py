"""
Genera memoria.docx (la memoria de la práctica) a partir del texto de este fichero.

Necesita python-docx (pip install python-docx). El texto se edita aquí y se vuelve a generar;
también se puede retocar el .docx directamente en Word.
"""

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

CARPETA = Path(__file__).parent
AUTOR = "Daniel López Farray"
ASIGNATURA = "Redes de Comunicación Industriales"
TITULO = "Práctica 1 · Visualizador de un UR3e por TCP/IP"
REPO = "https://github.com/godzilin/Practica1UR"
AZUL = RGBColor(0x00, 0x5E, 0xB8)          # azul del escudo de Deusto
LETRA, TAM = "Calibri", 10


# ---------------------------------------------------------------------
# Utilidades de formato
# ---------------------------------------------------------------------
def campo(parrafo, codigo):
    """Inserta un campo de Word (PAGE, NUMPAGES): Word calcula el número al abrir."""
    r = parrafo.add_run()
    for tipo, texto in (("begin", None), (None, codigo), ("separate", None), (None, "1"), ("end", None)):
        if tipo:
            e = OxmlElement("w:fldChar")
            e.set(qn("w:fldCharType"), tipo)
        elif texto == codigo:
            e = OxmlElement("w:instrText")
            e.set(qn("xml:space"), "preserve")
            e.text = f" {codigo} "
        else:
            e = OxmlElement("w:t")
            e.text = texto
        r._r.append(e)
    return r


def sin_bordes(tabla):
    bordes = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = OxmlElement(f"w:{lado}")
        b.set(qn("w:val"), "nil")
        bordes.append(b)
    tabla._tbl.tblPr.append(bordes)


def borde_inferior(parrafo):
    pPr = parrafo._p.get_or_add_pPr()
    bordes = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "005EB8")):
        b.set(qn(k), v)
    bordes.append(b)
    pPr.append(bordes)


def sombrear(celda, color):
    tcPr = celda._tc.get_or_add_tcPr()
    s = OxmlElement("w:shd")
    s.set(qn("w:val"), "clear")
    s.set(qn("w:fill"), color)
    tcPr.append(s)


def texto_rico(parrafo, texto):
    """**negrita** y `código` dentro de una línea."""
    import re
    for trozo in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", texto):
        if trozo.startswith("**"):
            parrafo.add_run(trozo[2:-2]).bold = True
        elif trozo.startswith("`"):
            r = parrafo.add_run(trozo[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(TAM - 1)
        elif trozo:
            parrafo.add_run(trozo)


# ---------------------------------------------------------------------
# Documento
# ---------------------------------------------------------------------
doc = Document()
estilo = doc.styles["Normal"]
estilo.font.name, estilo.font.size = LETRA, Pt(TAM)
estilo.element.rPr.rFonts.set(qn("w:eastAsia"), LETRA)
estilo.paragraph_format.space_after = Pt(3)
estilo.paragraph_format.line_spacing = 1.0

seccion = doc.sections[0]
seccion.page_height, seccion.page_width = Cm(29.7), Cm(21.0)
seccion.top_margin, seccion.bottom_margin = Cm(2.3), Cm(1.6)
seccion.left_margin = seccion.right_margin = Cm(1.9)
seccion.header_distance, seccion.footer_distance = Cm(0.7), Cm(0.7)

# Encabezado: logo a la izquierda, autor y práctica a la derecha
cab = seccion.header
tabla = cab.add_table(rows=1, cols=2, width=Cm(17.2))
sin_bordes(tabla)
tabla.alignment = WD_TABLE_ALIGNMENT.CENTER
tabla.cell(0, 0).paragraphs[0].add_run().add_picture(str(CARPETA / "logo_deusto.png"), height=Cm(1.15))
derecha = tabla.cell(0, 1).paragraphs[0]
derecha.alignment = WD_ALIGN_PARAGRAPH.RIGHT
r = derecha.add_run(AUTOR + "\n")
r.bold, r.font.size = True, Pt(9)
r = derecha.add_run(f"{ASIGNATURA}\n{TITULO}")
r.font.size, r.font.color.rgb = Pt(8), RGBColor(0x55, 0x55, 0x55)
cab.paragraphs[0].paragraph_format.space_after = Pt(0)
borde_inferior(cab.add_paragraph())

# Pie: Página X de Y
pie = seccion.footer.paragraphs[0]
pie.alignment = WD_ALIGN_PARAGRAPH.CENTER
for t in ("Página ", "PAGE", " de ", "NUMPAGES"):
    r = campo(pie, t) if t.isupper() else pie.add_run(t)
    r.font.size = Pt(8)


def titulo(texto, tam=12.5):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(7)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(texto)
    r.bold, r.font.size, r.font.color.rgb = True, Pt(tam), AZUL
    return p


def parrafo(texto):
    p = doc.add_paragraph()
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    texto_rico(p, texto)
    return p


def punto(texto):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    texto_rico(p, texto)
    return p


def tabla_tareas(filas, anchos):
    t = doc.add_table(rows=len(filas), cols=len(filas[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, fila in enumerate(filas):
        for j, texto in enumerate(fila):
            c = t.cell(i, j)
            c.width = Cm(anchos[j])
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            texto_rico(p, texto)
            for r in p.runs:
                r.font.size = Pt(TAM - 1 if r.font.size is None else r.font.size.pt)
            if i == 0:
                sombrear(c, "005EB8")
                for r in p.runs:
                    r.bold, r.font.color.rgb = True, RGBColor(0xFF, 0xFF, 0xFF)
    return t


# ---------------------------------------------------------------------
# Contenido
# ---------------------------------------------------------------------
p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(2)
r = p.add_run(TITULO)
r.bold, r.font.size, r.font.color.rgb = True, Pt(16), AZUL

parrafo("El objetivo es ver en tiempo real, en una simulación 3D (PyBullet), la postura de un brazo "
        "robótico UR3e leyendo los datos que el propio robot publica por la red (TCP/IP). Se ha probado "
        "contra URSim (el robot simulado de Universal Robots en una máquina virtual en modo puente) y se "
        "han completado los cuatro niveles (A–D). Todo el código, con su historial, está en "
        f"**{REPO}**.")

titulo("1. Cómo funciona: la idea común")
parrafo("El robot no envía «mensajes» sueltos: TCP entrega un **flujo continuo de bytes**, y cada "
        "`recv()` puede traer medio mensaje, uno o varios. Por eso todos los programas siguen la misma "
        "estrategia de lectura: (1) se acumula lo recibido en un **buffer**; (2) se lee la **longitud** "
        "que va al principio de cada mensaje (4 bytes) y solo se procesa cuando ha llegado entero; "
        "(3) dentro de él se recorren los **subpaquetes** saltando de uno a otro con su propia longitud, "
        "sin necesidad de entender los que no interesan; (4) los números se decodifican en "
        "**big-endian** con `struct`. Si una longitud es absurda, el buffer se ha desalineado y se "
        "reconecta. Cada script tiene sus parámetros como constantes al principio y las IP de los robots "
        "en `robots.json`, de modo que se configura sin tocar el código y se ejecuta con F5 en VS Code.")

titulo("2. El código, por tareas")
tabla_tareas([
    ["Tarea", "Script", "Qué hace y cómo"],
    ["**A** · Interfaz primaria", "`primaria.py`",
     "Puerto 30001, 10 mensajes por segundo. Corta el flujo en mensajes, busca el de estado (tipo 16) "
     "y en él el subpaquete de articulaciones (tipo 1), del que saca los 6 ángulos `q_actual` para mover "
     "el robot 3D. Muestra también los mensajes del robot (versión, errores) y reconecta solo si se cae."],
    ["**B** · Tiempo real", "`tiempo_real.py`",
     "Puerto 30003, unos 500 paquetes por segundo de estructura fija: los ángulos están siempre en el "
     "byte 252. Lee todos los paquetes pero solo guarda el último y dibuja 30 veces por segundo; "
     "dibujar cada paquete saturaría el programa. Mide paquetes/s y paquetes por `recv()`."],
    ["**C** · Varios robots", "`varios_robots.py`",
     "Un **hilo** por robot recibe sus datos y deja el último estado en una variable compartida "
     "protegida con un **Lock**; un único bucle dibuja todos los robots. Si uno deja de enviar, solo "
     "ese se congela y su etiqueta pasa a rojo «SIN DATOS»; los demás siguen."],
    ["**D** · Enseñar y reproducir", "`ensenar_reproducir.py`",
     "Mini-aplicación manejada con el teclado: se guardan posturas del robot como puntos, se "
     "**previsualizan** con un robot «fantasma» semitransparente sin mover el real y se ejecutan con "
     "`movej` punto a punto. Una **máquina de estados** confirma cada punto con el estado del robot y, "
     "si hay error o parada de protección, detiene la secuencia, muestra el motivo y permite reanudar."],
    ["Herramienta", "`test_conexion.py`",
     "Comprueba la conexión, el modo del robot y, opcionalmente, gira la base unos grados y vuelve."],
], [3.0, 3.3, 10.9])

titulo("3. Trabajo adicional")
punto("**Repositorio GitHub con control de versiones**: cada cambio se ha subido como un commit, con "
      "README (instalación, uso, configuración de IP) y un documento de diseño de la aplicación D con "
      "el guion de la defensa.")
punto("**Robustez («a prueba de bombas»)**: `robots.json` se valida con mensajes claros; los mensajes "
      "truncados, corruptos o con ángulos no numéricos se descartan sin romper nada; los hilos nunca "
      "mueren en silencio; si se pierde la red o el robot se reinicia, se reconecta solo; cerrar la "
      "ventana termina el programa limpiamente.")
punto("**Seguridad del robot**: si el programa se cierra (Ctrl+C, ventana, fallo) con el robot "
      "moviéndose, se envía `stopj` antes de salir; velocidad y aceleración se limitan a 0,3 rad/s y "
      "0,5 rad/s²; cada punto se comprueba antes de enviarlo; una parada de emergencia nunca se "
      "desbloquea por red.")
punto("**Pruebas**: `prueba_robustez.py` lanza 20 000 mensajes rotos contra el lector; un robot falso "
      "envió basura, silencios y mensajes cortados; y en URSim se apagó el robot, se cortó la red y se "
      "cayó el dashboard a mitad de una secuencia. En todos los casos la aplicación se recuperó.")

titulo("4. Robot real")
parrafo("**[Completar tras la sesión en el laboratorio: qué UR3e se ha usado (10.172.21.x) y qué "
        "diferencias se han observado respecto a URSim.]** En URSim se observó, por ejemplo, que la "
        "interfaz de tiempo real da unos 480 paquetes/s en lugar de 500 porque la máquina virtual "
        "simula algo más lenta que el tiempo real.")

titulo("5. Preguntas de comprensión")


def pregunta(n, enunciado, respuesta):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(f"{n}. {enunciado}")
    r.bold, r.font.color.rgb = True, AZUL
    parrafo(respuesta)


pregunta(1, "¿Coincide cada recv() con un mensaje?",
         "No. En un minuto contra URSim hubo 1113 `recv()` de 11 tamaños distintos (de 9 a 1448 bytes): "
         "1025 trajeron justo un mensaje, 86 trajeron varios y alguno dejó un mensaje a medias. Además el "
         "mensaje de estado no mide siempre lo mismo (722 o 743 bytes). Consecuencia: nunca se puede "
         "suponer que un `recv()` es un mensaje; hay que acumular en un buffer y cortar por la longitud.")
pregunta(2, "¿Por qué el mensaje y cada subpaquete empiezan con su longitud? ¿Y si llega un tipo desconocido?",
         "Porque en un flujo de bytes no hay separadores: la longitud dice dónde acaba cada pieza y permite "
         "saltarla sin entenderla. Un subpaquete de tipo desconocido simplemente se salta sumando su "
         "longitud, así que el programa sigue funcionando aunque una versión nueva del robot añada datos.")
pregunta(3, "¿Qué pasa si se decodifica q_actual sin big-endian?",
         "Se obtienen valores absurdos, porque los bytes se leen en orden inverso. Ejemplo: −1,5708 rad "
         "(−90°) se envía como `BF F9 21 FF 2E 48 E8 A7`; leído en little-endian (el orden del PC) da "
         "−1,9·10⁻¹¹⁶, un número sin sentido. Por eso se usa `struct` con `>` (big-endian).")
pregunta(4, "Primaria frente a tiempo real: ¿cuál para cada uso?",
         "La **primaria** envía 10 veces por segundo, con mensajes por tipos que incluyen errores y avisos, "
         "y acepta órdenes: poco tráfico y mucha información. La de **tiempo real** envía unas 500 veces por "
         "segundo una estructura fija: más precisión y menos retraso, pero unas 50 veces más tráfico. Para "
         "un **panel de supervisión**, la primaria (10 Hz basta y trae los errores). Para **registrar la "
         "trayectoria de un movimiento rápido**, la de tiempo real (un dato cada 2 ms).")
pregunta(5, "¿Por qué con NAT no se puede conectar a URSim y en modo puente sí? ¿Quién ve la MAC de la VM?",
         "Con NAT, VirtualBox esconde la máquina virtual detrás de su propia red privada: solo puede iniciar "
         "conexiones hacia fuera y desde el PC no hay una IP a la que llegar (haría falta redirigir puertos). "
         "En modo puente la VM se conecta a la red del laboratorio como un equipo más, con su propia IP "
         "(10.172.18.67). Su MAC la ven el switch del laboratorio y los equipos del mismo segmento de red "
         "(por ejemplo, nuestro PC en su tabla ARP); el router no la propaga más allá.")
pregunta(6, "Si se desconecta la red 5 s, ¿qué hace el programa y qué hace TCP?",
         "Se probó cortando la red con el cortafuegos (equivale a quitar el cable para TCP). TCP no pierde "
         "nada: el robot guarda y reenvía los datos pendientes, y al volver la red llegan de golpe (en un "
         "corte de 1,6 s llegaron 12 estados seguidos, ya atrasados). Nuestro programa espera como máximo "
         "5 s sin datos: si el corte los supera, da la conexión por perdida, reconecta a los 2 s y sigue con "
         "datos frescos en lugar de dibujar los atrasados.")
pregunta(7, "(N) Retraso entre URSim y el robot simulado con cada interfaz.",
         "Medido desde que se envía un `movej` hasta que se ve cambiar el ángulo (4 movimientos): "
         "**tiempo real 61 ms**, **primaria 123 ms** de media (105–132 ms). Unos 60 ms son lo que tarda el "
         "robot en arrancar el programa; la diferencia, unos 60 ms, se debe a que la primaria solo publica "
         "cada 100 ms. A esto se suma hasta 33 ms del dibujo a 30 FPS. Depende del periodo de publicación, "
         "del ritmo de dibujo, de la red y de la carga del PC y de la VM.")
pregunta(8, "(N) ¿Qué ocurriría sin Lock?",
         "El bucle de dibujo podría leer el estado mientras un hilo lo escribe y mezclar datos de dos "
         "instantes (ángulos de un paquete con la marca de tiempo de otro), o fallar al copiar el diccionario "
         "compartido justo cuando otro hilo añade un robot (`dictionary changed size during iteration`). "
         "Son fallos raros e imprevisibles; el Lock garantiza que se lee siempre un estado completo.")
pregunta(9, "(S) ¿Por qué enviar un movej no basta para saber que el robot ha llegado?",
         "Porque el robot no responde a las órdenes: la orden puede rechazarse (error de sintaxis, robot en "
         "modo local), interrumpirse (parada de protección, `stopj`) o tardar. Se confirma con el propio "
         "estado del robot: `isProgramRunning` pasa a verdadero (aceptada) y luego a falso (terminada), "
         "`q_actual` queda a menos de 0,01 rad del objetivo, y no han llegado mensajes de error (tipo 20) "
         "ni `isProtectiveStopped`. Si el programa no arranca en 2 s, se da la orden por rechazada.")
pregunta(10, "(S) Riesgo de que cualquiera pueda enviar programas al puerto 30001 y dos medidas.",
         "No hay autenticación ni cifrado: cualquier equipo de la red (un portátil infectado, un error de "
         "otro programa) podría mover el robot con personas cerca, parar la producción o dañar el equipo. "
         "Medidas: (1) **en el robot**, en los ajustes de seguridad de PolyScope desactivar o restringir los "
         "servicios entrantes (30001/30002/30003) y usar el modo Local o contraseña, dejando para "
         "supervisión solo interfaces de lectura como 30011; (2) **en la red**, aislar los robots en una "
         "VLAN o segmento propio tras un cortafuegos que solo permita conectarse a los puertos de control "
         "desde la IP del equipo autorizado (zonas y conductos de IEC 62443).")

salida = CARPETA / "memoria.docx"
doc.save(salida)
print(f"Guardado {salida}")
