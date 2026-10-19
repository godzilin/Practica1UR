"""
Genera las figuras de la memoria y de las preguntas en memoria/figuras/.

Los datos medidos contra URSim están en memoria/datos/ (movej.json, recv.json, retraso.json)
y la captura de la aplicación en memoria/datos/captura_app.png.
Necesita matplotlib (pip install matplotlib).
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

CARPETA = Path(__file__).parent
DATOS = CARPETA / "datos"
SALIDA = CARPETA / "figuras"
SALIDA.mkdir(exist_ok=True)

# Paleta compartida por todas las figuras para que diagramas, capturas y
# gráficas se lean como una misma memoria.
AZUL, AZUL_CLARO, NARANJA, ROJO, GRIS, VERDE = "#005EB8", "#D6E6F7", "#E87722", "#C62828", "#555555", "#2E7D32"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 220, "savefig.bbox": "tight"})


def caja(ax, x, y, w, h, texto, color=AZUL_CLARO, borde=AZUL, tam=10, negrita=False):
    # Los diagramas usan cajas y flechas pequeñas en vez de depender de un
    # editor externo; así se pueden regenerar tras cambiar el diseño.
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=color, ec=borde, lw=1.4))
    ax.text(x + w / 2, y + h / 2, texto, ha="center", va="center", fontsize=tam,
            weight="bold" if negrita else "normal")


def flecha(ax, a, b, texto="", color=AZUL, curva=0.0, lado=0.12, tam=8.5, estilo="-|>", ls="-", dx=0.0, ha="center"):
    # La etiqueta se coloca en el punto medio para mantener el diagrama legible
    # aunque cambien las coordenadas de origen y destino.
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=estilo, mutation_scale=14, color=color, lw=1.5,
                                 connectionstyle=f"arc3,rad={curva}", linestyle=ls, shrinkA=2, shrinkB=2))
    if texto:
        xm, ym = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        ax.text(xm + dx, ym + lado, texto, ha=ha, va="center", fontsize=tam, color=color)


# ---------------------------------------------------------------------
# 1. Capturas: se recortan para eliminar bordes de la ventana y centrar la
# información relevante de la defensa.
# ---------------------------------------------------------------------
img = mpimg.imread(DATOS / "captura_app.png")
plt.imsave(SALIDA / "captura.png", img[0:470, 0:860])


# Captura de varios robots (bloque C)
img = mpimg.imread(DATOS / "captura_varios.png")
plt.imsave(SALIDA / "captura_varios.png", img[150:420, 280:900])


# ---------------------------------------------------------------------
# 2. Interfaz de tiempo real (bloque B): se compara un paquete fijo con el
# ritmo de llegada de datos y el ritmo deliberadamente menor de dibujo.
# ---------------------------------------------------------------------
fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.2, 2.6), gridspec_kw={"height_ratios": [1, 1.1]})
a1.set_xlim(0, 1220), a1.set_ylim(0, 1), a1.axis("off")
for x0, x1, t, c in ((0, 4, "", "#FFF1E3"), (4, 252, "tiempo, objetivos…", AZUL_CLARO),
                     (252, 300, "", "#C8E6C9"), (300, 1220, "resto de datos (corrientes, TCP, E/S…)", "#EEEEEE")):
    a1.add_patch(Rectangle((x0, 0.25), x1 - x0, 0.5, fc=c, ec=GRIS, lw=1))
    if t:
        a1.text((x0 + x1) / 2, 0.5, t, ha="center", va="center", fontsize=8.5)
a1.annotate("q_actual\nbyte 252", xy=(276, 0.75), xytext=(276, 1.15), ha="center", fontsize=8.5, color=VERDE,
            arrowprops=dict(arrowstyle="->", color=VERDE), annotation_clip=False)
a1.text(0, -0.05, "Paquete de tiempo real: 1220 B, siempre igual (sin tipos ni subpaquetes)", fontsize=8.5,
        color=GRIS, va="top")
a2.set_xlim(0, 100), a2.set_ylim(0, 1)
for spine in ("left",):
    a2.spines[spine].set_visible(False)
a2.set_yticks([])
a2.vlines([2 * i for i in range(51)], 0.1, 0.45, color=AZUL, lw=1)
a2.vlines([0, 100 / 3, 200 / 3, 100], 0.55, 0.95, color=NARANJA, lw=3)
a2.text(101, 0.27, "paquetes (500/s)", va="center", fontsize=8.5, color=AZUL)
a2.text(101, 0.75, "dibujo (30/s): solo el último", va="center", fontsize=8.5, color=NARANJA)
a2.set_xlabel("ms")
fig.tight_layout(h_pad=0.6)
fig.savefig(SALIDA / "tiempo_real.png")
plt.close(fig)


# ---------------------------------------------------------------------
# 3. Arquitectura: el gráfico hace visible la frontera entre red, estado
# compartido y PyBullet.
# ---------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 2.7))
ax.set_xlim(0, 11.6), ax.set_ylim(0, 4.0), ax.axis("off")
caja(ax, 0.0, 1.4, 1.6, 1.1, "UR3e\no URSim", "#EEEEEE", GRIS, negrita=True)
caja(ax, 2.7, 1.4, 2.2, 1.1, "Hilo receptor\nrecv → buffer\n→ mensajes")
caja(ax, 6.0, 1.4, 1.6, 1.1, "Último\nestado\n+ Lock", "#FFF1E3", NARANJA)
caja(ax, 8.7, 1.4, 2.9, 1.1, "Bucle principal\n30 veces/s: teclas,\nestados y dibujo", tam=9.5)
flecha(ax, (1.6, 1.95), (2.7, 1.95), "TCP", tam=8.5, lado=0.25)
ax.text(2.15, 1.5, "30001\n30003", ha="center", va="center", fontsize=8, color=AZUL)
flecha(ax, (4.9, 1.95), (6.0, 1.95), "escribe", lado=0.25)
flecha(ax, (7.6, 1.95), (8.7, 1.95), "lee", lado=0.25)
caja(ax, 9.15, 3.05, 2.0, 0.7, "PyBullet (3D)", "#EEEEEE", GRIS)
flecha(ax, (10.15, 2.5), (10.15, 3.05), color=GRIS)
# Órdenes de vuelta: por debajo, del bucle principal al robot
ax.plot([10.15, 10.15, 0.8], [1.4, 0.75, 0.75], color=NARANJA, lw=1.5)
flecha(ax, (0.8, 0.75), (0.8, 1.4), color=NARANJA)
ax.text(5.5, 0.35, "órdenes URScript (movej, stopj) por el mismo socket 30001",
        ha="center", fontsize=8.5, color=NARANJA)
fig.savefig(SALIDA / "arquitectura.png")
plt.close(fig)


# ---------------------------------------------------------------------
# 4. Del flujo TCP a q_actual: recv(), mensajes y subpaquetes son niveles
# diferentes y no deben confundirse.
# ---------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 2.9))
ax.set_xlim(0, 10.6), ax.set_ylim(0, 4.3), ax.axis("off")
# Fila 1: los recv() no coinciden con los mensajes
ax.text(0, 3.95, "Lo que devuelve cada recv()", fontsize=9, color=GRIS)
for x0, x1 in ((0, 2.3), (2.3, 5.9), (5.9, 7.1), (7.1, 10.6)):
    ax.add_patch(Rectangle((x0, 3.3), x1 - x0, 0.45, fc="#EEEEEE", ec=GRIS, lw=1, ls="--"))
ax.text(0, 2.95, "Mensajes completos (se cortan leyendo su longitud)", fontsize=9, color=AZUL)
for x0, x1, t in ((0, 3.4, "estado 16"), (3.4, 3.8, ""), (3.8, 7.6, "estado 16"), (7.6, 10.6, "estado 16…")):
    ax.add_patch(Rectangle((x0, 2.3), x1 - x0, 0.5, fc=AZUL_CLARO, ec=AZUL, lw=1.3))
    ax.text((x0 + x1) / 2, 2.55, t, ha="center", va="center", fontsize=8.5)
# Fila 2: un mensaje por dentro
ax.text(0.75, 1.6, "Dentro de un mensaje de estado", fontsize=9, color=AZUL)
partes = [(0.0, 1.0, "longitud\n4 B", "#FFF1E3"), (1.0, 1.7, "tipo\n1 B", "#FFF1E3"),
          (1.7, 3.6, "subpaq. 0\nmodo del robot", AZUL_CLARO), (3.6, 7.4, "subpaq. 1 · articulaciones\nq_actual: 6 × double", "#C8E6C9"),
          (7.4, 10.6, "otros subpaquetes\n(se saltan con su longitud)", "#EEEEEE")]
for x0, x1, t, c in partes:
    ax.add_patch(Rectangle((x0, 0.55), x1 - x0, 0.85, fc=c, ec=GRIS, lw=1))
    ax.text((x0 + x1) / 2, 0.975, t, ha="center", va="center", fontsize=8.3)
flecha(ax, (0.4, 2.3), (0.4, 1.42), color=GRIS)
ax.text(5.5, 0.18, "big-endian: struct.unpack('>d', …)", ha="center", fontsize=8.5, color=VERDE)
fig.savefig(SALIDA / "mensaje.png")
plt.close(fig)


# ---------------------------------------------------------------------
# 5. Máquina de estados del bloque D.
# ---------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 3.2))
ax.set_xlim(0, 11.0), ax.set_ylim(-0.6, 4.6), ax.axis("off")
w, h = 2.1, 0.75
n = {"REPOSO": (0.1, 2.8), "PREVISUALIZANDO": (0.0, 0.3), "ENVIANDO": (4.0, 2.8),
     "MOVIENDO": (8.8, 2.8), "DETENIDO": (8.8, 0.3), "REANUDANDO": (4.0, 0.3)}
for nombre, (x, y) in n.items():
    color, borde = (("#FFEBEE", ROJO) if nombre == "DETENIDO" else ("#E8F5E9", VERDE) if nombre == "REPOSO"
                    else (AZUL_CLARO, AZUL))
    caja(ax, x, y, 2.6 if nombre == "PREVISUALIZANDO" else w, h, nombre, color, borde, tam=8.5, negrita=True)
c = lambda k, fx=0.5, fy=0.5: (n[k][0] + w * fx, n[k][1] + h * fy)
flecha(ax, c("REPOSO", 1), c("ENVIANDO", 0), "Enter", lado=0.22)
flecha(ax, c("ENVIANDO", 1, 0.65), c("MOVIENDO", 0, 0.65), "el programa arranca", lado=0.25, tam=8)
flecha(ax, c("MOVIENDO", 0, 0.3), c("ENVIANDO", 1, 0.3), "llegó: siguiente punto", lado=-0.28, tam=8)
flecha(ax, c("MOVIENDO", 0.5, 1), c("REPOSO", 0.5, 1), "llegó al último punto", curva=0.18, lado=1.2, color=VERDE)
flecha(ax, c("MOVIENDO", 0.5, 0), c("DETENIDO", 0.5, 1), "error, parada\no sin red", color=ROJO,
       lado=0.0, tam=8, dx=0.15, ha="left")
flecha(ax, c("DETENIDO", 0), c("REANUDANDO", 1), "Enter", lado=0.22)
flecha(ax, c("REANUDANDO", 0.5, 1), c("ENVIANDO", 0.5, 0), "robot listo", lado=0.0, dx=0.12, ha="left")
flecha(ax, c("REPOSO", 0.3, 0), (0.69, 1.05), "P", lado=0.0, dx=-0.12, ha="right")
flecha(ax, (1.6, 1.05), c("REPOSO", 0.9, 0), "fin", lado=0.0, dx=0.12, ha="left")
ax.text(5.5, -0.35, "Esc en cualquier momento: stopj y vuelta a REPOSO", ha="center", fontsize=8.5,
        color=GRIS, style="italic")
fig.savefig(SALIDA / "estados.png")
plt.close(fig)


# ---------------------------------------------------------------------
# 6. Confirmar un movej con datos reales de URSim: se superponen las dos
# interfaces para justificar cuándo se considera alcanzado un objetivo.
# ---------------------------------------------------------------------
import math
d = json.loads((DATOS / "movej.json").read_text())
grados = math.degrees
t_rt = [t for t, _ in d["rt"]]
q_rt = [grados(q) for _, q in d["rt"]]
fig, ax = plt.subplots(figsize=(7.2, 2.6))
# Tramo en el que el robot dice que el programa está en marcha (interfaz primaria)
marcha = [t for t, run, _ in d["primaria"] if run]
ax.axvspan(min(marcha), max(marcha), color=AZUL_CLARO, alpha=0.7, lw=0)
ax.text(1.15, -145, "isProgramRunning\n= True", ha="center", fontsize=8.5, color=AZUL)
ax.plot(t_rt, q_rt, color=AZUL, lw=2, label="ángulo de la base (tiempo real, 500 Hz)")
ax.plot([t for t, _, _ in d["primaria"]], [grados(q) for _, _, q in d["primaria"]], "o", ms=3.5,
        color=NARANJA, label="estado de la primaria (10 Hz)")
obj = grados(d["objetivo_base"])
ax.axhline(obj, color=VERDE, ls="--", lw=1)
ax.text(t_rt[-1], obj + 1.2, "objetivo ± 0,01 rad", ha="right", fontsize=8.5, color=VERDE)
ax.set_ylim(top=obj + 5)
ax.axvline(0, color=GRIS, lw=1)
ax.text(0.05, grados(d["inicio_base"]) + 14, "movej\nenviado", fontsize=8.5, color=GRIS)
fin = max(marcha)
ax.annotate("termina el programa\ny q está en el objetivo\n→ punto confirmado", xy=(fin, obj - 0.3),
            xytext=(3.4, obj - 7), fontsize=8.5, color=VERDE, va="top",
            arrowprops=dict(arrowstyle="->", color=VERDE))
ax.set_xlabel("tiempo desde el envío (s)")
ax.set_ylabel("base (°)")
ax.legend(loc="upper left", fontsize=8, frameon=False)
fig.savefig(SALIDA / "movej.png")
plt.close(fig)


# ---------------------------------------------------------------------
# 7. Preguntas: qué trae cada recv() y qué retraso introduce cada interfaz.
# ---------------------------------------------------------------------
recv = json.loads((DATOS / "recv.json").read_text())
fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.3), gridspec_kw={"width_ratios": [1.4, 1]})
tam = sorted({l for l, _, _ in recv})
cuenta = [sum(1 for l, _, _ in recv if l == t) for t in tam]
a1.bar(range(len(tam)), cuenta, color=AZUL)
a1.set_xticks(range(len(tam)), [str(t) for t in tam], rotation=60, fontsize=7.5)
a1.set_xlabel("bytes devueltos por recv()")
a1.set_ylabel("veces en 1 min")
uno = sum(1 for _, nm, b in recv if nm == 1 and b == 0)
varios = sum(1 for _, nm, _ in recv if nm > 1)
a2.barh(["1 mensaje", "varios"], [uno, varios], color=[AZUL, NARANJA])
for i, v in enumerate([uno, varios]):
    a2.text(v + 15, i, str(v), va="center", fontsize=9)
a2.set_xlabel("recv() que trajeron…")
a2.set_xlim(0, max(uno, varios) * 1.25)
fig.tight_layout()
fig.savefig(SALIDA / "recv.png")
plt.close(fig)

r = json.loads((DATOS / "retraso.json").read_text())
fig, ax = plt.subplots(figsize=(3.6, 2.0))
for i, (k, nombre, color) in enumerate((("tiempo_real", "tiempo real\n(30003)", AZUL),
                                         ("primaria", "primaria\n(30001)", NARANJA))):
    v = r[k]
    media = sum(v) / len(v)
    ax.barh(i, media, color=color, xerr=[[media - min(v)], [max(v) - media]], capsize=4)
    ax.text(max(v) + 6, i, f"{media:.0f} ms", va="center", fontsize=9)
ax.set_yticks([0, 1], ["tiempo real\n(30003)", "primaria\n(30001)"])
ax.set_xlabel("ms desde el movej hasta verlo")
ax.set_xlim(0, 175)
fig.savefig(SALIDA / "retraso.png")
plt.close(fig)

print("Figuras en", SALIDA)
