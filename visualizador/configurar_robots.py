"""Configura los robots del fichero robots.json desde la terminal."""

import json
import os
import tempfile
from pathlib import Path


FICHERO = Path(__file__).with_name("robots.json")
# La ruta junto al script funciona igual desde VS Code, el lanzador o CMD.


def pedir(texto, actual=""):
    # Una entrada vacía conserva el valor anterior.
    respuesta = input(f"{texto} [{actual}]: ").strip()
    return respuesta or str(actual)


def cargar():
    # Un fichero ausente o corrupto permite empezar desde una lista vacía.
    try:
        datos = json.loads(FICHERO.read_text(encoding="utf-8"))
        if not isinstance(datos, list):
            raise ValueError
        return datos
    except (OSError, ValueError, json.JSONDecodeError):
        print("No se pudo leer robots.json; se creara una configuracion nueva.")
        return []


def guardar(robots):
    # La copia y el temporal evitan perder el JSON anterior si falla una escritura.
    copia = FICHERO.with_suffix(".json.bak")
    if FICHERO.exists():
        copia.write_bytes(FICHERO.read_bytes())
    temporal = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=FICHERO.parent, delete=False)
    try:
        json.dump(robots, temporal, ensure_ascii=False, indent=4)
        temporal.write("\n")
        temporal.close()
        os.replace(temporal.name, FICHERO)
    except Exception:
        temporal.close()
        Path(temporal.name).unlink(missing_ok=True)
        raise


def main():
    # Se reutilizan nombre y host; los scripts deciden puerto y posición.
    actuales = cargar()
    print(f"\nConfiguracion de robots: {FICHERO}")
    try:
        cantidad = int(pedir("Numero de robots", len(actuales) or 1))
        if cantidad < 1:
            raise ValueError
    except ValueError:
        print("Numero no valido.")
        return 1

    robots = []
    for indice in range(cantidad):
        actual = actuales[indice] if indice < len(actuales) else {}
        print(f"\nRobot {indice + 1}")
        robots.append({
            "nombre": pedir("Nombre", actual.get("nombre", f"Robot_{indice + 1}")),
            "host": pedir("IP o nombre de host", actual.get("host", "127.0.0.1")),
        })

    guardar(robots)
    print(f"\nGuardado correctamente. Copia anterior: {FICHERO.with_suffix('.json.bak')}")
    return 0


if __name__ == "__main__":
    # El lanzador puede reaccionar al código de salida del asistente.
    raise SystemExit(main())