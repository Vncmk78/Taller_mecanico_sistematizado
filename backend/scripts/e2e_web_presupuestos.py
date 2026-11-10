"""Recorrido WEB (Playwright) de presupuestos: A-03 revisión administrativa y A-04 recuperación.

Prepara órdenes asignadas por la API y luego recorre la interfaz real del
ambiente de pruebas como Mecánico, Administrador y Cliente, con capturas en
--capturas. Los fallos de coordinación se provocan con scripts/proxy_fallos_ms2.py.

Uso (desde backend/, ambiente de pruebas iniciado y MS3 detrás del proxy):
    python scripts/ambiente_pruebas.py ejecutar -- python scripts/e2e_web_presupuestos.py \\
        --web http://127.0.0.1:5183 --gateway http://127.0.0.1:8100 --proxy http://127.0.0.1:8112 \\
        --capturas evidencias-web
Sale con 0 si todas las comprobaciones pasan.
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from scripts.e2e_presupuestos_revision_recuperacion import (  # noqa: E402
    Proxy, decisiones, envios, transiciones,
)
from scripts.flujos_e2e_gateway import ADMINISTRADOR, CLIENTE, MECANICO  # noqa: E402

RESULTADOS: list[tuple[str, bool]] = []


def comprobar(nombre: str, condicion: bool) -> None:
    RESULTADOS.append((nombre, bool(condicion)))
    print(("OK   " if condicion else "FALLA ") + nombre, flush=True)


class Api:
    def __init__(self, gateway: str) -> None:
        self.http = httpx.Client(base_url=gateway.rstrip("/") + "/api", timeout=30)
        self.tokens = {n: self._login(c) for n, c in
                       (("cliente", CLIENTE), ("mecanico", MECANICO), ("administrador", ADMINISTRADOR))}

    def _login(self, cuenta) -> str:
        r = self.http.post("/auth/login", json={"email": cuenta[0], "password": cuenta[1]})
        r.raise_for_status()
        return r.json()["access_token"]

    def pedir(self, metodo: str, ruta: str, quien: str, **kw):
        r = self.http.request(metodo, ruta, headers={"Authorization": f"Bearer {self.tokens[quien]}"}, **kw)
        r.raise_for_status()
        return r.json() if r.content else None

    def orden_asignada(self, patente: str) -> int:
        vehiculo = self.pedir("POST", "/vehiculos", "cliente",
                              json={"patente": patente, "marca": "Kia", "modelo": "Rio", "anio": 2021})
        orden = self.pedir("POST", "/ordenes", "administrador", json={"vehiculo_id": vehiculo["vehiculo_id"]})
        mecanico_id = self.pedir("GET", "/auth/me", "mecanico")["id"]
        self.pedir("PUT", f"/ordenes/{orden['orden_id']}/mecanico", "administrador", json={"mecanico_id": mecanico_id})
        return orden["orden_id"]

    def borrador(self, orden_id: int) -> int:
        return self.pedir("POST", "/presupuestos", "mecanico", json={"orden_id": orden_id, "items": [
            {"tipo": "mano_de_obra", "descripcion": "Cambio de pastillas", "cantidad": "1",
             "precio_unitario": "18000"}]})["presupuesto_id"]

    def estado(self, orden_id: int) -> int:
        return self.pedir("GET", f"/ordenes/{orden_id}", "administrador")["estado_codigo"]


def entrar(page: Page, web: str, cuenta) -> None:
    page.goto(f"{web}/login")
    page.get_by_label("Correo Electrónico").fill(cuenta[0])
    page.get_by_label("Contraseña", exact=True).fill(cuenta[1])
    page.locator("button[type=submit]").click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=15000)


def captura(page: Page, carpeta: Path, nombre: str) -> None:
    page.wait_for_timeout(900)  # termina la animación de entrada
    page.screenshot(path=str(carpeta / f"{nombre}.png"), full_page=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--web", default="http://127.0.0.1:5183")
    parser.add_argument("--gateway", default="http://127.0.0.1:8100")
    parser.add_argument("--proxy", default="http://127.0.0.1:8112")
    parser.add_argument("--capturas", type=Path, default=Path("evidencias-web"))
    args = parser.parse_args()
    args.capturas.mkdir(parents=True, exist_ok=True)
    api, proxy = Api(args.gateway), Proxy(args.proxy)
    proxy.reiniciar()
    sufijo = secrets.token_hex(2).upper()
    reintentar = "Reintentar aplicación en la orden"

    with sync_playwright() as p:
        navegador = p.chromium.launch()

        def sesion(cuenta) -> Page:
            pagina = navegador.new_context(viewport={"width": 1280, "height": 900}).new_page()
            entrar(pagina, args.web, cuenta)
            return pagina

        # ── A-03: Mecánico propone, Administrador revisa y envía, Cliente consulta ──
        orden = api.orden_asignada(f"WA{sufijo}")
        mec = sesion(MECANICO)
        mec.goto(f"{args.web}/mechanic/ordenes/{orden}/presupuesto")
        mec.get_by_label("Descripción").first.fill("Cambio de pastillas delanteras")
        mec.get_by_label("Precio unitario").first.fill("18000")
        mec.get_by_role("button", name="Crear presupuesto").click()
        expect(mec.get_by_text("Versión 1 — borrador")).to_be_visible()
        comprobar("A-03 Mecánico crea el borrador desde la web", True)
        comprobar("A-03 Mecánico no ve 'Enviar al cliente'",
                  mec.get_by_role("button", name="Enviar al cliente").count() == 0)
        comprobar("A-03 Mecánico ve que la revisión y el envío son del Administrador",
                  mec.get_by_text("Un Administrador revisa los precios y la envía al cliente").is_visible())
        captura(mec, args.capturas, "a03-1-mecanico-borrador")

        adm = sesion(ADMINISTRADOR)
        adm.goto(f"{args.web}/admin/ordenes/{orden}")
        adm.get_by_role("link", name="Revisar presupuesto y precios").click()
        precio = adm.get_by_label("Precio unitario").first
        expect(precio).to_have_value("18000")
        precio.fill("21500")
        adm.get_by_role("button", name="Enviar al cliente").click()
        expect(adm.get_by_text("Versión enviada al cliente")).to_be_visible()
        expect(adm.get_by_text("Versión 1 — enviada")).to_be_visible()
        comprobar("A-03 Administrador revisa el precio y envía desde su portal", api.estado(orden) == 3)
        captura(adm, args.capturas, "a03-2-administrador-envia")

        cli = sesion(CLIENTE)
        cli.goto(f"{args.web}/client/presupuestos/{orden}")
        expect(cli.get_by_role("button", name="Aprobar Presupuesto")).to_be_visible()
        comprobar("A-03 Cliente ve la versión enviada con el precio revisado",
                  cli.get_by_text("21.500").first.is_visible())
        captura(cli, args.capturas, "a03-3-cliente-consulta")

        # ── A-04 envío: 503 guardado, reintento fallido, recarga, recuperación ──
        orden2 = api.orden_asignada(f"WB{sufijo}")
        presupuesto2 = api.borrador(orden2)
        proxy.modo("coordinacion")
        adm.goto(f"{args.web}/admin/ordenes/{orden2}/presupuesto")
        adm.get_by_role("button", name="Enviar al cliente").click()
        expect(adm.get_by_text("Envío registrado, pendiente de aplicar en la orden")).to_be_visible()
        comprobar("A-04 Envío con 503: la web informa 'registrado, pendiente' y oculta 'Enviar'",
                  adm.get_by_role("button", name="Enviar al cliente").count() == 0)
        comprobar("A-04 Se conserva la referencia del presupuesto",
                  adm.get_by_text(f"Presupuesto n° {presupuesto2}").is_visible())
        captura(adm, args.capturas, "a04-1-envio-pendiente")
        adm.get_by_role("button", name=reintentar).click()
        expect(adm.get_by_role("alert").filter(has_text="MS2")).to_be_visible()
        comprobar("A-04 Reintento fallido: sigue pendiente", api.estado(orden2) == 2)
        captura(adm, args.capturas, "a04-2-reintento-fallido")
        adm.reload()
        expect(adm.get_by_role("button", name=reintentar)).to_be_visible()
        comprobar("A-04 Tras recargar, la web reconoce el envío pendiente desde el servidor", True)
        proxy.modo("ninguno")
        adm.get_by_role("button", name=reintentar).click()
        expect(adm.get_by_text("Aplicación confirmada")).to_be_visible()
        comprobar("A-04 Envío recuperado: la orden pasó a 3", api.estado(orden2) == 3)
        comprobar("A-04 Un solo envío y una sola transición a 3",
                  envios(presupuesto2) in (1, None) and transiciones(orden2, 3) in (1, None))
        captura(adm, args.capturas, "a04-3-envio-recuperado")

        # ── A-04 decisión: 503 guardado y recuperación desde el portal Cliente ──
        proxy.modo("coordinacion")
        cli.goto(f"{args.web}/client/presupuestos/{orden2}")
        cli.get_by_role("button", name="Aprobar Presupuesto").click()
        cli.get_by_label("He revisado las partidas y el total").check()
        cli.get_by_role("button", name="Confirmar aprobación").click()
        expect(cli.get_by_text("Decisión registrada, pendiente de aplicar en la orden")).to_be_visible()
        comprobar("A-04 Decisión con 503: aprobar queda bloqueado",
                  cli.get_by_role("button", name="Aprobar Presupuesto").count() == 0
                  or cli.get_by_role("button", name="Aprobar Presupuesto").is_disabled())
        captura(cli, args.capturas, "a04-4-decision-pendiente")
        cli.reload()
        expect(cli.get_by_role("button", name=reintentar)).to_be_visible()
        proxy.modo("ninguno")
        cli.get_by_role("button", name=reintentar).click()
        expect(cli.get_by_text("Decisión aplicada")).to_be_visible()
        estado_final = api.estado(orden2)
        comprobar("A-04 Decisión recuperada: la orden salió de 3", estado_final in (4, 5))
        comprobar("A-04 Una sola decisión y una sola transición al estado final",
                  decisiones(presupuesto2) in (1, None) and transiciones(orden2, estado_final) in (1, None))
        captura(cli, args.capturas, "a04-5-decision-recuperada")
        navegador.close()

    print(f"\n{sum(ok for _, ok in RESULTADOS)}/{len(RESULTADOS)} comprobaciones; "
          f"llamadas bloqueadas por el proxy: {len(proxy.bloqueadas())}")
    return 0 if all(ok for _, ok in RESULTADOS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
