"""Microservicio de mentira para simular fallos detrás de la Gateway (solo pruebas).

Semana 10 (SCRUM-583). Responde a cualquier ruta según el modo elegido, para
ver en la web o con curl cómo responde la Gateway a cada escenario de
`docs/escenarios-error-gateway.md`:

  lento      espera --espera segundos y luego responde 200 (provoca 504)
  json-roto  200 con Content-Type: application/json y un body roto (502 RESPUESTA_INVALIDA)
  no-http    contesta bytes que no son HTTP (502 RESPUESTA_INVALIDA)
  500-texto  500 en texto plano con una traza falsa (500 ERROR_MICROSERVICIO, sin la traza)
  ok         200 con una lista JSON vacía

El escenario "servicio caído" no necesita este script: basta con detener el
microservicio (o apuntar la Gateway a un puerto sin nadie).

Uso (MS2 de mentira en el puerto 8102):

    python scripts/simular_fallos_gateway.py --modo lento --puerto 8102
    # en otra terminal, la Gateway apuntando a él:
    GATEWAY_MS2_URL=http://127.0.0.1:8102 uvicorn gateway.main:app --port 8000
    curl -i http://localhost:8000/api/vehiculos -H "X-Request-ID: demo-1"

Cada petición recibida se imprime con su X-Request-ID, para comprobar la
correlación. No usar fuera del ambiente de pruebas.
"""
from __future__ import annotations

import argparse
import socketserver
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODOS = ("lento", "json-roto", "no-http", "500-texto", "ok")


def _manejador(modo: str, espera: float) -> type[BaseHTTPRequestHandler]:
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:
            pass

        def _responder(self, estado: int, cuerpo: bytes, tipo: str) -> None:
            self.send_response(estado)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _atender(self) -> None:
            print(
                f"[{modo}] {self.command} {self.path} "
                f"X-Request-ID={self.headers.get('X-Request-ID', '-')}",
                flush=True,
            )
            if modo == "lento":
                time.sleep(espera)
                self._responder(200, b"[]", "application/json")
            elif modo == "json-roto":
                self._responder(200, b'{"vehiculos": [ {"patente": "AB', "application/json")
            elif modo == "500-texto":
                self._responder(
                    500,
                    b'Traceback (most recent call last): File "/srv/ms2/db.py"',
                    "text/plain",
                )
            else:
                self._responder(200, b"[]", "application/json")

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _atender

    return Manejador


class _NoHttp(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        self.request.recv(65536)
        print("[no-http] conexión recibida", flush=True)
        self.request.sendall(b"ESTO NO ES HTTP\r\n\r\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--modo", choices=MODOS, required=True)
    parser.add_argument("--puerto", type=int, default=8102)
    parser.add_argument("--espera", type=float, default=30.0, help="segundos del modo lento")
    args = parser.parse_args()

    direccion = ("127.0.0.1", args.puerto)
    # Permite relanzar el script en el mismo puerto sin esperar el TIME_WAIT.
    socketserver.TCPServer.allow_reuse_address = True
    if args.modo == "no-http":
        servidor: socketserver.BaseServer = socketserver.ThreadingTCPServer(direccion, _NoHttp)
    else:
        servidor = ThreadingHTTPServer(direccion, _manejador(args.modo, args.espera))
    print(f"Simulando '{args.modo}' en http://127.0.0.1:{args.puerto} (Ctrl+C para salir)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
