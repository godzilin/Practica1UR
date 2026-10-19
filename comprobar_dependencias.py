"""Comprueba las dependencias locales sin acceder a Internet."""

import importlib
import sys


# La clave es el nombre que verá la persona usuaria; el valor es el nombre real
# que acepta importlib. No se usa pip para que esta comprobación sea offline.
DEPENDENCIAS = {
    "pybullet": "pybullet",
    "pybullet-planning": "pybullet_planning",
    "UR3e_rg2": "UR3e_rg2",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "python-docx": "docx",
}


def main():
    # Se prueban todas las importaciones y se acumulan los fallos para mostrar
    # un diagnóstico completo en una sola ejecución.
    faltan = []
    for paquete, modulo in DEPENDENCIAS.items():
        try:
            importlib.import_module(modulo)
        except Exception as error:
            faltan.append(f"  - {paquete}: {error}")

    if faltan:
        # El código distinto de cero permite que los lanzadores detengan el menú
        # y sugieran ejecutar el preparador correspondiente al sistema.
        print("Faltan dependencias en el entorno virtual:")
        print("\n".join(faltan))
        return 1

    print(f"Dependencias correctas. Python {sys.version.split()[0]}")
    return 0


if __name__ == "__main__":
    # Propaga el resultado de main al sistema operativo.
    raise SystemExit(main())