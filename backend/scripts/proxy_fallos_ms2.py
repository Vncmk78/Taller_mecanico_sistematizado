"""Proxy de fallos controlados entre MS3 y MS2 (solo pruebas).

Reenvía todo a MS2 sin cambios, salvo cuando se activa un modo de fallo:

  coordinacion  responde 503 a POST /ordenes/{id}/envios-presupuesto y
                /ordenes/{id}/decisiones-presupuesto. MS3 ya guardó el envío o
                la decisión y no recibe la confirmación de MS2: es el caso
                "guardado, pendiente de aplicar".
  verificacion  responde 503 a GET /ordenes/{id}... (la verificación previa de
                la orden). MS3 falla ANTES de guardar: no hay nada que reintentar.
  ninguno       todo pasa (modo inicial).

Control (solo desde 127.0.0.1):
  POST /__fallos/modo/{coordinacion|verificacion|ninguno}
  POST /__fallos/reiniciar   (modo ninguno y contadores en cero)
  GET  /__fallos/estado   → {"modo": ..., "bloqueadas": [...], "reenviadas": n}

Uso: iniciar MS3 con MS3_MS2_URL=http://127.0.0.1:8112 y luego
    python scripts/proxy_fallos_ms2.py --puerto 8112 --destino http://127.0.0.1:8102
No usar fuera del ambiente de pruebas.
"""
from __future__ import annotations

import argparse
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

COORDINACION = re.compile(r"^/ordenes/\d+/(envios|decisiones)-presupuesto/?$")
VERIFICACION = re.compile(r"^/ordenes/\d+(/.*)?$")
SALTAR_CABECERAS = {"host", "content-length", "connection", "transfer-encoding"}


class Estado:
    def __init__(self) -> None:
        self.modo = "ninguno"
        self.bloqueadas: list[str] = []
        self.reenviadas = 0
        self.candado = threading.Lock()


def crear_manejador(destino: str, estado: Estado):
    cliente = httpx.Client(base_url=destino.rstrip("/"), timeout=30.0)

    class Manejador(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args) -> None:  # silencioso
            return

        def _responder(self, codigo: int, cuerpo: dict) -> None:
            datos = json.dumps(cuerpo).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def _control(self) -> bool:
            if not self.path.startswith("/__fallos"):
                return False
            if self.client_address[0] != "127.0.0.1":
                self._responder(403, {"detail": "solo local"})
                return True
            partes = self.path.strip("/").split("/")
            if self.command == "POST" and len(partes) == 3 and partes[1] == "modo" \
                    and partes[2] in ("coordinacion", "verificacion", "ninguno"):
                with estado.candado:
                    estado.modo = partes[2]
                self._responder(200, {"modo": estado.modo})
            elif self.command == "POST" and partes[-1] == "reiniciar":
                with estado.candado:
                    estado.modo, estado.bloqueadas, estado.reenviadas = "ninguno", [], 0
                self._responder(200, {"modo": estado.modo})
            elif self.command == "GET" and partes[-1] == "estado":
                with estado.candado:
                    self._responder(200, {"modo": estado.modo, "bloqueadas": estado.bloqueadas,
                                          "reenviadas": estado.reenviadas})
            else:
                self._responder(404, {"detail": "control desconocido"})
            return True

        def _bloquear(self) -> bool:
            ruta = self.path.split("?", 1)[0]
            with estado.candado:
                modo = estado.modo
            falla = (modo == "coordinacion" and self.command == "POST" and COORDINACION.match(ruta)) or (
                modo == "verificacion" and self.command == "GET" and VERIFICACION.match(ruta))
            if falla:
                with estado.candado:
                    estado.bloqueadas.append(f"{self.command} {ruta}")
                self._responder(503, {"detail": f"Fallo controlado del proxy de pruebas ({modo})"})
            return bool(falla)

        def _reenviar(self) -> None:
            if self._control() or self._bloquear():
                return
            largo = int(self.headers.get("Content-Length") or 0)
            cuerpo = self.rfile.read(largo) if largo else None
            cabeceras = {k: v for k, v in self.headers.items() if k.lower() not in SALTAR_CABECERAS}
            try:
                respuesta = cliente.request(self.command, self.path, content=cuerpo, headers=cabeceras)
            except httpx.HTTPError:
                self._responder(502, {"detail": "MS2 no respondió al proxy"})
                return
            with estado.candado:
                estado.reenviadas += 1
            self.send_response(respuesta.status_code)
            for clave, valor in respuesta.headers.items():
                if clave.lower() not in SALTAR_CABECERAS:
                    self.send_header(clave, valor)
            self.send_header("Content-Length", str(len(respuesta.content)))
            self.end_headers()
            self.wfile.write(respuesta.content)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _reenviar

    return Manejador


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--puerto", type=int, default=8112)
    parser.add_argument("--destino", default="http://127.0.0.1:8102")
    args = parser.parse_args()
    servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), crear_manejador(args.destino, Estado()))
    print(f"Proxy de fallos en 127.0.0.1:{args.puerto} → {args.destino}", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
