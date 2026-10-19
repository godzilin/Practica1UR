"""Comprueba las dependencias locales sin acceder a Internet."""

import importlib
import sys


DEPENDENCIAS = {
    "pybullet": "pybullet",
    "pybullet-planning": "pybullet_planning",
    "UR3e_rg2": "UR3e_rg2",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "python-docx": "docx",
}


def main():
    faltan = []
    for paquete, modulo in DEPENDENCIAS.items():
        try:
            importlib.import_module(modulo)
        except Exception as error:
            faltan.append(f"  - {paquete}: {error}")

    if faltan:
        print("Faltan dependencias en el entorno virtual:")
        print("\n".join(faltan))
        return 1

    print(f"Dependencias correctas. Python {sys.version.split()[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())