"""Servidor TCP didáctico que espera recibir una cadena."""
from __future__ import annotations
from dataclasses import dataclass
import struct
from mensajes import Dato
import socket
import struct

# Ejemplo mínimo complementario a cliente.py: deja visible bind-listen-accept.
@dataclass
class Dato():
    """Registro binario que debe tener el mismo formato en ambos extremos."""
    edad: int
    dni: int
    altura: float

    def codificar(self) -> bytes:
        # Cliente y servidor deben coincidir en tipos y orden de bytes.
        return struct.pack(">BId",self.edad,self.dni,self.altura)

    def decodificar(self, trama: bytes) -> Dato:
        # Una trama con longitud incorrecta produce struct.error.
        datos_decodificados = struct.unpack(">BId",trama)
        return Dato(edad=datos_decodificados[0],dni=datos_decodificados[1],altura=datos_decodificados[2])

HOST = "0.0.0.0"
PUERTO = 33334

def main():
    # El socket servidor se cierra automáticamente al salir del bloque with.
    # Crear el socket, asociarlo al puerto y empezar a escuchar.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
        servidor.bind((HOST, PUERTO))
        servidor.listen(1)
        print(f"Esperando una conexión en el puerto {PUERTO}...")

        # Aceptar un cliente y esperar hasta recibir datos.
        conexion, direccion = servidor.accept()
        with conexion:
            print(f"Cliente conectado: {direccion}")
            datos = conexion.recv(1024)

            datos_recibidos = Dato(3, 3, 1.5)
            datos_recibidos = datos_recibidos.decodificar(datos)
            print(f"Primeros datos recibidos: {datos_recibidos}")

            contador = 0
            while contador < 1000:
                print(f"Servidor enviado: {contador}")
                conexion.sendall(contador.to_bytes(4, "big"))
                bytes_recibidos = conexion.recv(4)
                contador_vuelta = int.from_bytes(bytes_recibidos, "big")
                print(f"Servidor recibido: {contador_vuelta}")
                contador = contador_vuelta + 1


if __name__ == "__main__":
    # El ejemplo queda listo para ejecutarse desde una terminal.
    main()
