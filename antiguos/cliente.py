"""Cliente TCP didáctico que envía una cadena al servidor."""
from __future__ import annotations
from dataclasses import dataclass
import struct
import socket
import struct
from mensajes import Dato

@dataclass
class Dato():
    edad: int
    dni: int
    altura: float
    def codificar(self) -> bytes:
        return struct.pack(">BId",self.edad,self.dni,self.altura)
    
    def decodificar(self, trama: bytes) -> Dato:
        datos_decodificados = struct.unpack(">BId",trama)
        return Dato(edad=datos_decodificados[0],dni=datos_decodificados[1],altura=datos_decodificados[2])

HOST = "127.0.0.1"
PUERTO = 33334

def main():
	datos_enviar = Dato(edad=30, dni=87666666, altura= 1.56)
 
	with socket.create_connection((HOST, PUERTO)) as cliente:
		secuencia_bytes_enviar = datos_enviar.codificar()
		cliente.sendall(secuencia_bytes_enviar)
 
		while True:
			bytes_recibidos = cliente.recv(4)
			if not bytes_recibidos:
				break
			contador = int.from_bytes(bytes_recibidos,"big")
			print(f"Cliente recibido {contador}")
			contador += 1
			cliente.sendall(contador.to_bytes(4,"big"))
			print(f"Cliente enviado {contador}")


if __name__ == "__main__":
	main()
