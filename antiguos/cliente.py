"""Cliente TCP didáctico que envía una cadena al servidor."""
from __future__ import annotations
from dataclasses import dataclass
import struct
import socket
import struct
from mensajes import Dato

# Ejemplo mínimo para estudiar un protocolo binario antes de leer el estado UR.
@dataclass
class Dato():
    """Registro de tamaño fijo compartido conceptualmente por cliente y servidor."""
    edad: int
    dni: int
    altura: float

    def codificar(self) -> bytes:
        # > fija big-endian; B, I y d fijan el contrato exacto de bytes.
        return struct.pack(">BId",self.edad,self.dni,self.altura)

    def decodificar(self, trama: bytes) -> Dato:
        # unpack aplica el mismo contrato en sentido inverso.
        datos_decodificados = struct.unpack(">BId",trama)
        return Dato(edad=datos_decodificados[0],dni=datos_decodificados[1],altura=datos_decodificados[2])

HOST = "127.0.0.1"
PUERTO = 33334

def main():
    # Primero se envía un registro binario y después se intercambian contadores.
    datos_enviar = Dato(edad=30, dni=87666666, altura=1.56)

    with socket.create_connection((HOST, PUERTO)) as cliente:
        secuencia_bytes_enviar = datos_enviar.codificar()
        cliente.sendall(secuencia_bytes_enviar)

        while True:
            bytes_recibidos = cliente.recv(4)
            if not bytes_recibidos:
                break
            contador = int.from_bytes(bytes_recibidos, "big")
            print(f"Cliente recibido {contador}")
            contador += 1
            cliente.sendall(contador.to_bytes(4, "big"))
            print(f"Cliente enviado {contador}")


if __name__ == "__main__":
    # El ejemplo se ejecuta solo cuando se lanza como programa.
    main()
