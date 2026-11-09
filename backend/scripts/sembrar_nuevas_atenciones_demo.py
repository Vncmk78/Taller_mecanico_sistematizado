"""Escenarios sintéticos A/B/C por API, idempotentes, para la demo final.

Solo se invoca después de verificar las marcas de propiedad con demo_final.py.
No modifica fechas ni estados directamente en ninguna base de datos.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.flujos_e2e_gateway import ADMINISTRADOR, CLIENTE


def sembrar(gateway: str) -> None:
    with httpx.Client(base_url=gateway.rstrip('/')+'/api', timeout=30) as cliente:
        def pedir(metodo, ruta, token=None, body=None):
            r=cliente.request(metodo,ruta,headers={'Authorization':'Bearer '+token} if token else {},
                              **({'json':body} if body is not None else {}))
            if r.status_code not in (200,201):
                raise RuntimeError(f'{metodo} {ruta}: HTTP {r.status_code}: {r.text[:180]}')
            return r.json()
        def login(cuenta):
            return pedir('POST','/auth/login',body={'email':cuenta[0], 'password':cuenta[1]})['access_token']
        admin,token=login(ADMINISTRADOR),login(CLIENTE)
        vehiculos=pedir('GET','/vehiculos',token)
        # El endpoint de vehículos devuelve una lista; cada patente es única.
        vehiculos={v['patente']:v for v in vehiculos}
        for patente,decision,generar,devolver in [
            ('DEMO07',None,False,False), ('DEMO08','aceptada',True,True),
            ('DEMO10','rechazada',False,True), ('DEMO11','aceptada',False,False),
        ]:
            v=vehiculos.get(patente)
            if v is None:
                v=pedir('POST','/vehiculos',token,{'patente':patente,'marca':'Kia','modelo':'Rio','anio':2022})
                vehiculos[patente]=v
            historial=pedir('GET',f"/ordenes/vehiculo/{v['vehiculo_id']}/historial",admin)['items']
            canceladas=[o for o in historial if o['estado_codigo']==8]
            if canceladas: orden=min(canceladas,key=lambda o:o['orden_id'])
            else:
                if historial: raise RuntimeError(f'{patente}: escenario previo distinto; no se altera')
                orden=pedir('POST','/ordenes',admin,{'vehiculo_id':v['vehiculo_id']})
                base=f"/ordenes/{orden['orden_id']}"
                pedir('POST',base+'/cancelacion',token,{'motivo':'Escenario sintético de nueva atención'})
                orden=pedir('POST',base+'/cancelacion/confirmacion',admin)
            if devolver and not orden['devuelto_en']:
                pedir('POST',f"/ordenes/{orden['orden_id']}/devolucion",admin,{})
            existentes=pedir('GET',f"/ordenes/nuevas-atenciones?orden_cancelada_id={orden['orden_id']}",token)['items']
            descripcion=f'Nueva atención de demostración {patente}: revisar frenos.'
            s=next((s for s in existentes if s['descripcion']==descripcion),None)
            if s is None:
                if existentes: raise RuntimeError(f'{patente}: solicitudes previas distintas; no se alteran')
                s=pedir('POST',f"/ordenes/{orden['orden_id']}/nueva-atencion",token,{'descripcion':descripcion})
            if decision:
                if s['situacion']=='pendiente':
                    s=pedir('POST',f"/ordenes/nuevas-atenciones/{s['solicitud_id']}/revision",admin,
                            {'decision':decision,'respuesta':'Revisión de demostración: '+decision})
                elif s['situacion']!=decision: raise RuntimeError(f'{patente}: revisión previa diferente; no se modifica')
            if generar:
                pedir('POST',f"/ordenes/nuevas-atenciones/{s['solicitud_id']}/orden",admin,{})
            print(f'{patente}: {s["situacion"]}'+(' con orden vinculada' if generar else ''))


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gateway',required=True)
    args=parser.parse_args()
    try: sembrar(args.gateway)
    except (RuntimeError,httpx.HTTPError) as exc:
        print(str(exc),file=sys.stderr)
        return 1
    return 0

if __name__=='__main__': raise SystemExit(main())
