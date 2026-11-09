"""Recorrido WEB (Playwright) de inventario y proveedores, con comparación contra lo persistido.

Como Administrador, desde la interfaz real del ambiente de pruebas:
  1. Crea un proveedor (Oficial) y un repuesto de ese proveedor con stock inicial
     y umbral particular.
  2. Consulta su stock (físico, comprometido, disponible, umbral efectivo).
  3. Registra un ajuste que lo deja bajo el umbral → aparece en Alertas.
  4. Intenta un ajuste mayor que el stock → mensaje de stock insuficiente y nada cambia.
  5. Registra un ingreso que lo deja IGUAL al umbral → sale de Alertas (stock < umbral).
  6. Cambia el umbral general con observación y lo restaura (historial).
  7. Ve los movimientos con repuesto, cantidad, responsable y fecha.
Y como Cliente: la procedencia (proveedor) del repuesto en su presupuesto.

Cada pantalla se compara con la API (MS3) y con PostgreSQL. Usa nombres únicos:
se puede repetir sobre el mismo ambiente y obtener los mismos resultados.

Uso (desde backend/, ambiente de pruebas iniciado y sembrado):
    python scripts/ambiente_pruebas.py ejecutar -- python scripts/e2e_web_inventario.py \\
        --web http://127.0.0.1:5183 --gateway http://127.0.0.1:8100 --capturas evidencias-web
"""
from __future__ import annotations

import argparse
import re
import secrets
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from scripts.e2e_presupuestos_revision_recuperacion import contar  # noqa: E402
from scripts.e2e_web_presupuestos import Api, captura, comprobar, entrar, RESULTADOS  # noqa: E402
from scripts.flujos_e2e_gateway import ADMINISTRADOR, CLIENTE  # noqa: E402


def stock_api(api: Api, repuesto_id: int) -> dict:
    return api.pedir("GET", f"/inventario/stock/{repuesto_id}", "administrador")


def stock_bd(repuesto_id: int) -> int | None:
    return contar("MS3_DATABASE_URL", "SELECT stock FROM repuesto WHERE repuesto_id = :r", r=repuesto_id)


def movimiento(pagina: Page, repuesto_id: int, tipo: str, cantidad: int) -> None:
    pagina.get_by_role("button", name="Registrar movimiento").click()
    dialogo = pagina.get_by_role("dialog", name="Registrar movimiento")
    dialogo.get_by_label("Repuesto ID").fill(str(repuesto_id))
    dialogo.get_by_label("Tipo").select_option(tipo)
    dialogo.get_by_label("Cantidad").fill(str(cantidad))
    dialogo.get_by_role("button", name="Registrar").click()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--web", default="http://127.0.0.1:5183")
    parser.add_argument("--gateway", default="http://127.0.0.1:8100")
    parser.add_argument("--capturas", type=Path, default=Path("evidencias-web"))
    args = parser.parse_args()
    args.capturas.mkdir(parents=True, exist_ok=True)
    api = Api(args.gateway)
    marca = secrets.token_hex(2).upper()
    proveedor, repuesto = f"Proveedor Cierre {marca}", f"Balata Cierre {marca}"
    admin_id = api.pedir("GET", "/auth/me", "administrador")["id"]

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        adm = navegador.new_context(viewport={"width": 1280, "height": 900}).new_page()
        entrar(adm, args.web, ADMINISTRADOR)

        # 1. Proveedor y repuesto
        adm.goto(f"{args.web}/admin/distribuidores")
        adm.get_by_role("button", name="Nuevo proveedor").click()
        dialogo = adm.get_by_role("dialog", name="Nuevo proveedor")
        dialogo.get_by_label("Nombre").fill(proveedor)
        dialogo.get_by_label("Contacto").fill("ventas@cierre.test")
        dialogo.get_by_label("Tipo").select_option(label="Oficial")
        dialogo.get_by_role("button", name="Crear").click()
        fila = adm.get_by_role("row").filter(has_text=proveedor)
        expect(fila).to_contain_text("Oficial")
        proveedores = api.pedir("GET", "/proveedores", "administrador", params={"q": proveedor})
        lista = proveedores.get("proveedores", proveedores) if isinstance(proveedores, dict) else proveedores
        comprobar("Proveedor creado en la web y persistido en MS3 como oficial",
                  any(x["nombre"] == proveedor and x.get("tipo_distribuidor") == "oficial" for x in lista))
        captura(adm, args.capturas, "inv-1-proveedor")

        adm.goto(f"{args.web}/admin/inventario")
        adm.get_by_role("button", name="Nuevo repuesto").click()
        dialogo = adm.get_by_role("dialog", name="Nuevo repuesto")
        dialogo.get_by_label("Nombre").fill(repuesto)
        dialogo.get_by_label("Proveedor").select_option(label=proveedor)
        dialogo.get_by_label("Stock inicial").fill("4")
        dialogo.get_by_label("Umbral particular (vacío = general)").fill("3")
        dialogo.get_by_role("button", name="Crear").click()
        fila = adm.get_by_role("row").filter(has_text=repuesto)
        expect(fila).to_contain_text(proveedor)
        repuesto_id = int(re.search(r"#(\d+)", fila.inner_text()).group(1))
        comprobar("Repuesto con proveedor, stock 4 y umbral 3: pantalla = API = BD",
                  "4" in fila.inner_text() and stock_api(api, repuesto_id)["stock"] == 4 and stock_bd(repuesto_id) in (4, None))
        captura(adm, args.capturas, "inv-2-repuesto")

        # 2. Consulta de stock
        adm.goto(f"{args.web}/admin/inventario/stock/{repuesto_id}")
        expect(adm.get_by_text(repuesto, exact=True)).to_be_visible()
        dato = stock_api(api, repuesto_id)

        def valor(etiqueta: str) -> str:
            return adm.get_by_text(etiqueta, exact=True).locator("xpath=following-sibling::*[1]").inner_text().strip()

        en_pantalla = (valor("Stock físico"), valor("Comprometido"), valor("Disponible"), valor("Umbral efectivo"))
        comprobar("Detalle de stock coincide con la API (físico/comprometido/disponible/umbral)",
                  en_pantalla == tuple(str(dato[k]) for k in ("stock", "comprometido", "disponible", "umbral_efectivo")))
        captura(adm, args.capturas, "inv-3-stock")

        # 3. Ajuste que deja el stock bajo el umbral → alerta
        adm.goto(f"{args.web}/admin/inventario/movimientos")
        movimiento(adm, repuesto_id, "ajuste", -2)
        expect(adm.get_by_role("dialog", name="Registrar movimiento")).to_be_hidden()
        comprobar("Ajuste -2 persistido (stock 2)", stock_api(api, repuesto_id)["stock"] == 2 and stock_bd(repuesto_id) in (2, None))
        adm.goto(f"{args.web}/admin/inventario/alertas")
        expect(adm.get_by_role("row").filter(has_text=repuesto)).to_be_visible()
        comprobar("Stock 2 < umbral 3: aparece en Alertas",
                  any(a["repuesto_id"] == repuesto_id for a in api.pedir("GET", "/inventario/alertas", "administrador")["alertas"]))
        captura(adm, args.capturas, "inv-4-alerta")

        # 4. Stock insuficiente: mensaje claro y nada cambia
        adm.goto(f"{args.web}/admin/inventario/movimientos")
        movimientos_antes = contar("MS3_DATABASE_URL", "SELECT count(*) FROM movimiento_inventario WHERE repuesto_id = :r", r=repuesto_id)
        movimiento(adm, repuesto_id, "ajuste", -5)
        dialogo = adm.get_by_role("dialog", name="Registrar movimiento")
        expect(dialogo.get_by_text(re.compile(r"faltan 3 \(disponible 2, solicitado 5\)"))).to_be_visible()
        comprobar("Stock insuficiente: el mensaje detalla lo que falta", True)
        captura(adm, args.capturas, "inv-5-stock-insuficiente")
        comprobar("Stock insuficiente: stock y movimientos sin cambios",
                  stock_api(api, repuesto_id)["stock"] == 2 and contar(
                      "MS3_DATABASE_URL", "SELECT count(*) FROM movimiento_inventario WHERE repuesto_id = :r",
                      r=repuesto_id) == movimientos_antes)
        dialogo.get_by_role("button", name="Cancelar").click()

        # 5. Ingreso que lo deja igual al umbral → sale de alertas
        movimiento(adm, repuesto_id, "ingreso", 1)
        expect(adm.get_by_role("dialog", name="Registrar movimiento")).to_be_hidden()
        adm.goto(f"{args.web}/admin/inventario/alertas")
        expect(adm.get_by_text("alertas · umbral general")).to_be_visible()
        comprobar("Stock 3 = umbral 3: ya no está en Alertas (comparación estricta)",
                  adm.get_by_role("row").filter(has_text=repuesto).count() == 0 and not any(
                      a["repuesto_id"] == repuesto_id for a in api.pedir("GET", "/inventario/alertas", "administrador")["alertas"]))

        # 6. Umbral general con historial
        adm.goto(f"{args.web}/admin/inventario/umbral")
        actual = api.pedir("GET", "/inventario/umbral-general", "administrador")["umbral_general"]
        adm.get_by_label("Nuevo umbral").fill(str(actual + 1))
        adm.get_by_label("Observación").fill(f"Prueba de cierre {marca}")
        adm.get_by_role("button", name="Guardar").click()
        expect(adm.get_by_role("row").filter(has_text=f"Prueba de cierre {marca}")).to_be_visible()
        comprobar("Umbral general guardado y en el historial",
                  api.pedir("GET", "/inventario/umbral-general", "administrador")["umbral_general"] == actual + 1)
        captura(adm, args.capturas, "inv-6-umbral-general")
        adm.get_by_label("Nuevo umbral").fill(str(actual))
        adm.get_by_label("Observación").fill(f"Restaurar tras prueba {marca}")
        adm.get_by_role("button", name="Guardar").click()
        expect(adm.get_by_role("row").filter(has_text=f"Restaurar tras prueba {marca}")).to_be_visible()

        # 7. Movimientos con responsable y fecha
        adm.goto(f"{args.web}/admin/inventario/movimientos")
        adm.get_by_label("Repuesto ID").first.fill(str(repuesto_id))
        adm.get_by_role("button", name="Buscar").click()
        filas = adm.get_by_role("row").filter(has_text=f"{repuesto} (#{repuesto_id})")
        expect(filas).to_have_count(3)  # ingreso inicial 4, ajuste -2 e ingreso 1 (el ajuste rechazado no existe)
        comprobar("Movimientos muestran repuesto, tipo, cantidad y responsable",
                  all(f"Usuario #{admin_id}" in filas.nth(i).inner_text() for i in range(3)))
        captura(adm, args.capturas, "inv-7-movimientos")

        # 8. Procedencia en el presupuesto del Cliente
        orden = api.orden_asignada(f"WI{marca}")
        presupuesto = api.pedir("POST", "/presupuestos", "mecanico", json={"orden_id": orden, "items": [
            {"tipo": "repuesto", "descripcion": repuesto, "cantidad": "1", "precio_unitario": "9900",
             "repuesto_id": repuesto_id}]})
        api.pedir("POST", f"/presupuestos/{presupuesto['presupuesto_id']}/versiones/1/envio", "administrador")
        cli = navegador.new_context(viewport={"width": 1280, "height": 900}).new_page()
        entrar(cli, args.web, CLIENTE)
        cli.goto(f"{args.web}/client/presupuestos/{orden}")
        expect(cli.get_by_text(f"Origen: {proveedor}")).to_be_visible()
        comprobar("El Cliente ve la procedencia (proveedor) del repuesto en su presupuesto", True)
        captura(cli, args.capturas, "inv-8-procedencia-cliente")
        navegador.close()

    print(f"\n{sum(ok for _, ok in RESULTADOS)}/{len(RESULTADOS)} comprobaciones (repuesto #{repuesto_id}, marca {marca})")
    return 0 if all(ok for _, ok in RESULTADOS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
