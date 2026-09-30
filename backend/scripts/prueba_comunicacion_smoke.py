"""Prueba de humo de la comunicación Gateway -> Autenticación (MS1).

Verifica sobre HTTP real, contra la Gateway y contra MS1, los casos válidos y
los casos rechazados del flujo de autenticación. Es el equivalente ejecutable de
la lista de pruebas de TAREA_7, pensado para comprobar en un despliegue que la
cadena completa responde, no para sustituir a la suite de pytest.

Requiere la Gateway y MS1 levantados. Levanta solo lo necesario:

    uvicorn gateway.main:app --port 8000
    uvicorn services.ms1_auth.main:app --port 8001

Uso (desde backend/):
    python scripts/prueba_comunicacion_smoke.py

Variables de entorno opcionales:
    GATEWAY_URL           por defecto http://localhost:8000
    MS1_URL               por defecto http://localhost:8001
    MS1_JWT_SECRET_KEY    si está definida, se añade el caso de token expirado
    SMOKE_TIMEOUT         por defecto 10 (segundos por petición)

Devuelve código 0 si todas las comprobaciones aplicables pasan; 1 si alguna
falla. Los casos que no se pueden ejecutar (p. ej. el de token expirado sin la
clave) se reportan como OMITIDO, no como fallo, para no dar un falso negativo.

Notas de contrato que este script respeta y verifica:

* El registro es público y el rol lo asigna el servidor: el cuerpo NO admite
  `role`. Los esquemas de MS1 son `extra="forbid"`, así que mandarlo es un 422.
* El claim de rol es `roles` (plural) y el de identidad es `sub`, un texto con
  el entero positivo del `usuario_id`. No existen `role`, `id` ni `email`.
* Los errores del microservicio pasan por la Gateway sin modificarse, así que el
  cuerpo conserva la clave `detail` de FastAPI.
* La Gateway no valida el token: se lo reenvía intacto al microservicio. Por eso
  no puede responder 401 por sí misma, y un 401 en `/api/*` siempre lo generó el
  servicio de destino.
* El login responde el mismo 401 y el mismo mensaje tanto si el correo no existe
  como si la contraseña es incorrecta: no enumera usuarios.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from jose import jwt

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000").rstrip("/")
MS1_URL = os.getenv("MS1_URL", "http://localhost:8001").rstrip("/")
TIEMPO_MAX = float(os.getenv("SMOKE_TIMEOUT", "10"))

# Claims que el contrato oficial emite, y los que nunca deben aparecer.
CLAIMS_ESPERADOS = {"sub", "roles", "exp"}
CLAIMS_PROHIBIDOS = {"role", "id", "email", "password", "iat", "nbf"}

OK = "PASA"
FALLA = "FALLA"
OMITIDO = "OMITIDO"

_resultados: list[tuple[str, str, str]] = []


def _registrar(estado: str, nombre: str, detalle: str) -> None:
    _resultados.append((estado, nombre, detalle))
    print(f"  [{estado:^7}] {nombre}")
    if detalle:
        print(f"            {detalle}")


def _comprobar(condicion: bool, nombre: str, detalle: str = "") -> bool:
    _registrar(OK if condicion else FALLA, nombre, detalle)
    return condicion


def _omitir(nombre: str, motivo: str) -> None:
    _registrar(OMITIDO, nombre, motivo)


def _detalle(respuesta: httpx.Response) -> str:
    """Devuelve el mensaje de error de la respuesta, sea cual sea su envoltorio.

    Los errores de un microservicio llegan con la clave `detail` de FastAPI. Los
    que genera la Gateway propia añaden además `error.codigo` y `error.ruta`.
    """
    try:
        cuerpo = respuesta.json()
    except ValueError:
        return respuesta.text[:200]
    if isinstance(cuerpo, dict):
        if "detail" in cuerpo:
            return str(cuerpo["detail"])
        if "error" in cuerpo and isinstance(cuerpo["error"], dict):
            return str(cuerpo["error"].get("codigo", cuerpo["error"]))
        return str(cuerpo)[:200]
    return str(cuerpo)[:200]


def _codigo_de_error(respuesta: httpx.Response) -> str:
    """Devuelve `error.codigo` cuando la respuesta la trae (solo la Gateway)."""
    try:
        cuerpo = respuesta.json()
    except ValueError:
        return ""
    if isinstance(cuerpo, dict) and isinstance(cuerpo.get("error"), dict):
        return str(cuerpo["error"].get("codigo", ""))
    return ""


def _esperar_servicios(cliente: httpx.Client) -> bool:
    """Comprueba que la Gateway y MS1 responden antes de ejecutar los casos."""
    disponibles = True
    for nombre, url, ruta in (
        ("Gateway", GATEWAY_URL, "/api/health"),
        ("MS1", MS1_URL, "/health"),
    ):
        try:
            respuesta = cliente.get(f"{url}{ruta}", timeout=3)
        except httpx.HTTPError as exc:
            _registrar(
                FALLA,
                f"El servicio {nombre} responde",
                f"no se pudo conectar con {url}{ruta}: {type(exc).__name__}. "
                f"Levántalo con: uvicorn <app> --port <puerto>",
            )
            disponibles = False
            continue
        if respuesta.status_code != 200:
            _registrar(
                FALLA,
                f"El servicio {nombre} responde",
                f"{url}{ruta} devolvió {respuesta.status_code}",
            )
            disponibles = False
        else:
            _registrar(OK, f"El servicio {nombre} responde", f"{url}{ruta}")
    return disponibles


def main() -> int:
    print("Prueba de humo Gateway -> Autenticación (MS1)")
    print(f"  Gateway: {GATEWAY_URL}")
    print(f"  MS1    : {MS1_URL}")
    print()

    # Correo único por ejecución: el registro es público, así que dos pruebas
    # seguidas no pueden chocar con el 409 de "correo ya registrado".
    correo = f"humo-{uuid.uuid4().hex[:10]}@pruebas.cl"
    contrasena = "ContrasenaHumo123!"

    contexto: dict[str, object] = {"correo": correo, "contrasena": contrasena}

    with httpx.Client(timeout=TIEMPO_MAX) as cliente:
        if not _esperar_servicios(cliente):
            print()
            print("No se pueden ejecutar los casos: faltan servicios por levantar.")
            return 1

        print("\nCASOS VÁLIDOS")
        _caso_registro(cliente, contexto)
        _caso_login(cliente, contexto)
        _caso_me_con_token(cliente, contexto)
        _caso_claims_del_token(cliente, contexto)
        _caso_gateway_transparente(cliente, contexto)
        _caso_authorization_llega_al_destino(cliente, contexto)

        print("\nCASOS RECHAZADOS")
        _caso_correo_duplicado(cliente, contexto)
        _caso_registro_con_rol(cliente, contexto)
        _caso_registro_contrasena_corta(cliente, contexto)
        _caso_registro_correo_invalido(cliente, contexto)
        _caso_login_contrasena_incorrecta(cliente, contexto)
        _caso_login_no_enumera_usuarios(cliente, contexto)
        _caso_me_sin_token(cliente, contexto)
        _caso_me_token_malformado(cliente, contexto)
        _caso_me_token_otra_clave(cliente, contexto)
        _caso_me_token_expirado(cliente, contexto)
        _caso_vehiculos_sin_token(cliente, contexto)

        _observar_cabecera_www_authenticate(cliente, contexto)

    return _resumen()


# --------------------------------------------------------------------------
# Casos válidos
# --------------------------------------------------------------------------


def _caso_registro(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """Registro público por la Gateway: 201 y el rol lo asigna el servidor."""
    respuesta = cliente.post(
        f"{GATEWAY_URL}/api/auth/register",
        json={
            "email": ctx["correo"],
            "password": ctx["contrasena"],
            "full_name": "Cliente de Humo",
        },
    )
    if not _comprobar(
        respuesta.status_code == 201,
        "Registro por la Gateway responde 201",
        f"código recibido: {respuesta.status_code} / {_detalle(respuesta)}",
    ):
        return
    cuerpo = respuesta.json()
    _comprobar(
        cuerpo.get("roles") == ["cliente"],
        "El registro devuelve roles=['cliente'] aunque el rol no se pidió",
        f"roles recibidos: {cuerpo.get('roles')}",
    )
    _comprobar(
        cuerpo.get("email") == ctx["correo"],
        "El registro devuelve el correo normalizado",
        f"correo recibido: {cuerpo.get('email')}",
    )
    ctx["usuario_id"] = cuerpo.get("id")


def _caso_login(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """Login por la Gateway: 200 con token de tipo bearer."""
    respuesta = cliente.post(
        f"{GATEWAY_URL}/api/auth/login",
        json={"email": ctx["correo"], "password": ctx["contrasena"]},
    )
    if not _comprobar(
        respuesta.status_code == 200,
        "Login por la Gateway responde 200",
        f"código recibido: {respuesta.status_code} / {_detalle(respuesta)}",
    ):
        return
    cuerpo = respuesta.json()
    token = cuerpo.get("access_token")
    _comprobar(
        isinstance(token, str) and token.count(".") == 2,
        "El login entrega un JWT con tres segmentos",
        f"token recibido: {'presente' if token else 'ausente'}",
    )
    _comprobar(
        cuerpo.get("token_type") == "bearer",
        "El login declara token_type='bearer'",
        f"token_type recibido: {cuerpo.get('token_type')}",
    )
    ctx["token"] = token
    ctx["login_id"] = cuerpo.get("user", {}).get("id")


def _caso_me_con_token(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """/me con el token recién emitido devuelve la misma identidad."""
    token = ctx.get("token")
    if not token:
        _omitir("/me acepta el token válido", "no se obtuvo token en el login")
        return
    respuesta = cliente.get(
        f"{GATEWAY_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    if not _comprobar(
        respuesta.status_code == 200,
        "/me por la Gateway responde 200 con token válido",
        f"código recibido: {respuesta.status_code} / {_detalle(respuesta)}",
    ):
        return
    cuerpo = respuesta.json()
    _comprobar(
        cuerpo.get("id") == ctx.get("login_id") == ctx.get("usuario_id"),
        "/me devuelve el mismo id que el login y que el registro",
        f"id de /me: {cuerpo.get('id')}, del login: {ctx.get('login_id')}, "
        f"del registro: {ctx.get('usuario_id')}",
    )


def _caso_claims_del_token(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """El token lleva exactamente los claims del contrato oficial."""
    token = ctx.get("token")
    if not token:
        _omitir("El token cumple el contrato de claims", "no se obtuvo token en el login")
        return

    claims = jwt.get_unverified_claims(token)
    _comprobar(
        set(claims) == CLAIMS_ESPERADOS,
        "El token emite exactamente sub, roles y exp",
        f"claims recibidos: {sorted(claims)}",
    )
    sobrantes = sorted(set(claims) & CLAIMS_PROHIBIDOS)
    _comprobar(
        not sobrantes,
        "El token no emite role, id, email ni password",
        f"claims prohibidos presentes: {sobrantes}" if sobrantes else "",
    )
    _comprobar(
        claims.get("roles") == ["cliente"],
        "El claim de rol es `roles` y llega como lista",
        f"roles recibidos: {claims.get('roles')}",
    )
    sub = claims.get("sub")
    _comprobar(
        isinstance(sub, str) and sub.isdigit() and int(sub) > 0,
        "`sub` es un texto con el entero positivo del usuario_id",
        f"sub recibido: {sub!r}",
    )
    exp = claims.get("exp")
    vigente = isinstance(exp, (int, float)) and exp > datetime.now(timezone.utc).timestamp()
    _comprobar(vigente, "`exp` está presente y en el futuro", f"exp recibido: {exp!r}")
    _comprobar(
        jwt.get_unverified_headers(token).get("alg") == "HS256",
        "El encabezado declara alg=HS256",
        f"alg recibido: {jwt.get_unverified_headers(token).get('alg')!r}",
    )


def _caso_gateway_transparente(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """La Gateway no altera el resultado: Gateway y MS1 directo coinciden."""
    cuerpo_gateway = {
        "email": ctx["correo"],
        "password": ctx["contrasena"],
    }
    directo = cliente.post(f"{MS1_URL}/auth/login", json=cuerpo_gateway)
    por_gateway = cliente.post(f"{GATEWAY_URL}/api/auth/login", json=cuerpo_gateway)

    if not _comprobar(
        directo.status_code == por_gateway.status_code == 200,
        "El login directo a MS1 y por la Gateway devuelve el mismo código",
        f"MS1 directo: {directo.status_code}, por la Gateway: {por_gateway.status_code}",
    ):
        return
    id_directo = directo.json().get("user", {}).get("id")
    id_gateway = por_gateway.json().get("user", {}).get("id")
    _comprobar(
        id_directo == id_gateway,
        "La Gateway devuelve el mismo usuario que MS1 directo",
        f"MS1 directo: {id_directo}, por la Gateway: {id_gateway}",
    )


def _caso_authorization_llega_al_destino(
    cliente: httpx.Client, ctx: dict[str, object]
) -> None:
    """La Gateway reenvía el Authorization: MS2 ya no dice "no autenticado".

    Este usuario se acaba de registrar y no tiene perfil Cliente en MS2, así que
    la respuesta correcta es 404 ("la identidad es válida, el recurso no
    existe"), no 401. Que deje de ser 401 prueba que el token llegó al servicio.
    """
    token = ctx.get("token")
    if not token:
        _omitir(
            "La Gateway entrega el token a otro microservicio",
            "no se obtuvo token en el login",
        )
        return
    respuesta = cliente.get(
        f"{GATEWAY_URL}/api/vehiculos",
        headers={"Authorization": f"Bearer {token}"},
    )
    if respuesta.status_code == 502:
        _registrar(
            FALLA,
            "La Gateway entrega el token a otro microservicio",
            "MS2 no está levantado, así que la Gateway respondió 502 y el caso no "
            "probó nada. Levántalo con: uvicorn services.ms2_taller.main:app --port 8002",
        )
        return
    _comprobar(
        respuesta.status_code == 404,
        "La Gateway entrega el token a otro microservicio (404, ya no 401)",
        f"/api/vehiculos con token devolvió {respuesta.status_code} "
        f"({_detalle(respuesta)}); se esperaba 404 por falta de perfil en MS2",
    )


# --------------------------------------------------------------------------
# Casos rechazados
# --------------------------------------------------------------------------


def _caso_correo_duplicado(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """Un correo ya registrado se rechaza con 409."""
    respuesta = cliente.post(
        f"{GATEWAY_URL}/api/auth/register",
        json={
            "email": ctx["correo"],
            "password": ctx["contrasena"],
            "full_name": "Cliente de Humo",
        },
    )
    _comprobar(
        respuesta.status_code == 409,
        "El registro con correo duplicado se rechaza con 409",
        f"código recibido: {respuesta.status_code} / {_detalle(respuesta)}",
    )


def _caso_registro_con_rol(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """Mandar `role` en el registro es un 422: el rol no lo elige el cliente.

    Este es el caso que fallaba el script anterior: el esquema es
    `extra="forbid"`, así que un `role` inesperado se rechaza con 422 en lugar
    de concederse. Que el rol se asigne en el servidor es lo que impide que
    alguien se registre como administrador.
    """
    respuesta = cliente.post(
        f"{GATEWAY_URL}/api/auth/register",
        json={
            "email": f"admin-{uuid.uuid4().hex[:8]}@pruebas.cl",
            "password": ctx["contrasena"],
            "full_name": "Intruso",
            "role": "administrador",
        },
    )
    _comprobar(
        respuesta.status_code == 422,
        "El registro con `role` en el cuerpo se rechaza con 422",
        f"código recibido: {respuesta.status_code} / {_detalle(respuesta)}",
    )


def _caso_registro_contrasena_corta(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """Contraseña de menos de 8 caracteres: 422 de validación."""
    respuesta = cliente.post(
        f"{GATEWAY_URL}/api/auth/register",
        json={
            "email": f"corta-{uuid.uuid4().hex[:8]}@pruebas.cl",
            "password": "corta",
            "full_name": "Contraseña Corta",
        },
    )
    _comprobar(
        respuesta.status_code == 422,
        "El registro con contraseña corta se rechaza con 422",
        f"código recibido: {respuesta.status_code} / {_detalle(respuesta)}",
    )


def _caso_registro_correo_invalido(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """Correo que no es un email: 422 de validación."""
    respuesta = cliente.post(
        f"{GATEWAY_URL}/api/auth/register",
        json={
            "email": "no-es-un-correo",
            "password": ctx["contrasena"],
            "full_name": "Correo Inválido",
        },
    )
    _comprobar(
        respuesta.status_code == 422,
        "El registro con correo inválido se rechaza con 422",
        f"código recibido: {respuesta.status_code} / {_detalle(respuesta)}",
    )


def _caso_login_contrasena_incorrecta(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """Contraseña incorrecta para un correo existente: 401."""
    respuesta = cliente.post(
        f"{GATEWAY_URL}/api/auth/login",
        json={"email": ctx["correo"], "password": "ContrasenaIncorrecta123!"},
    )
    _comprobar(
        respuesta.status_code == 401,
        "El login con contraseña incorrecta se rechaza con 401",
        f"código recibido: {respuesta.status_code} / {_detalle(respuesta)}",
    )


def _caso_login_no_enumera_usuarios(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """Correo inexistente y contraseña incorrecta responden exactamente igual.

    Si los mensajes difieren, un atacante puede enumerar qué correos tienen cuenta
    probándolos uno por uno.
    """
    credenciales_incorrecta = {
        "email": ctx["correo"],
        "password": "ContrasenaIncorrecta123!",
    }
    credenciales_inexistente = {
        "email": f"nadie-{uuid.uuid4().hex[:8]}@pruebas.cl",
        "password": ctx["contrasena"],
    }
    incorrecta = cliente.post(f"{GATEWAY_URL}/api/auth/login", json=credenciales_incorrecta)
    inexistente = cliente.post(f"{GATEWAY_URL}/api/auth/login", json=credenciales_inexistente)
    _comprobar(
        incorrecta.status_code == inexistente.status_code == 401,
        "Login con usuario inexistente también responde 401",
        f"incorrecta: {incorrecta.status_code}, inexistente: {inexistente.status_code}",
    )
    _comprobar(
        _detalle(incorrecta) == _detalle(inexistente),
        "El login no enumera usuarios: mismo 401 y mismo mensaje",
        f"mensaje con contraseña incorrecta: {_detalle(incorrecta)!r}; "
        f"mensaje con usuario inexistente: {_detalle(inexistente)!r}",
    )


def _caso_me_sin_token(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """Sin cabecera Authorization: 401 y no 403.

    Importa que sea 401 y no 403: el frontend limpia la sesión al recibir un 401,
    de modo que un 403 dejaría al usuario con una sesión muerta.
    """
    respuesta = cliente.get(f"{GATEWAY_URL}/api/auth/me")
    _comprobar(
        respuesta.status_code == 401,
        "/me sin token se rechaza con 401 (no 403)",
        f"código recibido: {respuesta.status_code} / {_detalle(respuesta)}",
    )


def _caso_me_token_malformado(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """Un texto que no es un JWT: 401."""
    respuesta = cliente.get(
        f"{GATEWAY_URL}/api/auth/me",
        headers={"Authorization": "Bearer esto-no-es-un-jwt"},
    )
    _comprobar(
        respuesta.status_code == 401,
        "/me con token malformado se rechaza con 401",
        f"código recibido: {respuesta.status_code} / {_detalle(respuesta)}",
    )


def _caso_me_token_otra_clave(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """JWT bien formado pero firmado con otra clave: 401.

    Es el caso que cubre que el secreto de firma sea el mismo en MS1 y en el
    servicio que valida. La clave se genera al azar, así que el caso no depende
    de conocer el secreto configurado.
    """
    clave_ajena = uuid.uuid4().hex + uuid.uuid4().hex
    token = jwt.encode(
        {
            "sub": "1",
            "roles": ["administrador"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        },
        clave_ajena,
        algorithm="HS256",
    )
    respuesta = cliente.get(
        f"{GATEWAY_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    _comprobar(
        respuesta.status_code == 401,
        "/me con token firmado con otra clave se rechaza con 401",
        f"código recibido: {respuesta.status_code} / {_detalle(respuesta)}",
    )


def _caso_me_token_expirado(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """JWT vigente en firma pero con `exp` pasado: 401.

    Necesita la clave real de MS1, porque si no el rechazo vendría por la firma
    y el caso no probaría nada sobre la expiración. Sin la clave se omite.
    """
    clave = os.getenv("MS1_JWT_SECRET_KEY")
    if not clave:
        _omitir(
            "/me con token expirado se rechaza con 401",
            "define MS1_JWT_SECRET_KEY para poder firmar un token con la clave real "
            "de MS1; sin ella el rechazo probaría la firma, no la expiración",
        )
        return
    token = jwt.encode(
        {
            "sub": str(ctx.get("usuario_id", 1)),
            "roles": ["cliente"],
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
        clave,
        algorithm="HS256",
    )
    respuesta = cliente.get(
        f"{GATEWAY_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    _comprobar(
        respuesta.status_code == 401,
        "/me con token expirado se rechaza con 401",
        f"código recibido: {respuesta.status_code} / {_detalle(respuesta)}",
    )


def _caso_vehiculos_sin_token(cliente: httpx.Client, ctx: dict[str, object]) -> None:
    """Una ruta de MS2 sin token también da 401, y lo generó MS2.

    El 401 de la Gateway solo aparece para rutas que no tienen microservicio; en
    `/api/*` el código viene del servicio, que es quien tiene el secreto.
    """
    respuesta = cliente.get(f"{GATEWAY_URL}/api/vehiculos")
    _comprobar(
        respuesta.status_code == 401,
        "/api/vehiculos sin token se rechaza con 401",
        f"código recibido: {respuesta.status_code} / {_detalle(respuesta)}",
    )
    _comprobar(
        _codigo_de_error(respuesta) == "",
        "El 401 lo generó el microservicio, no la Gateway (sin error.codigo)",
        f"error.codigo recibido: {_codigo_de_error(respuesta)!r}",
    )


def _observar_cabecera_www_authenticate(
    cliente: httpx.Client, ctx: dict[str, object]
) -> None:
    """Anota si la Gateway conserva la cabecera `WWW-Authenticate` del 401.

    No es un caso que pueda fallar: el proxy reenvía el cuerpo y el estado pero
    solo la cabecera `content-type` de la respuesta. RFC 9110 pide que un 401
    incluya `WWW-Authenticate`, así que conviene tenerlo visible al operate.
    """
    directo = cliente.get(f"{MS1_URL}/auth/me")
    por_gateway = cliente.get(f"{GATEWAY_URL}/api/auth/me")
    directa = "WWW-Authenticate" in directo.headers
    gateway = "WWW-Authenticate" in por_gateway.headers
    _registrar(
        OK,
        "Observación: cabecera WWW-Authenticate en el 401",
        f"MS1 directo: {directa}, por la Gateway: {gateway}"
        + ("" if gateway else " (la Gateway no la reenvía; ver estudio de seguridad)"),
    )


# --------------------------------------------------------------------------


def _resumen() -> int:
    """Imprime el recuento y devuelve 0 solo si no hubo fallos."""
    print("\nRESUMEN")
    passed = sum(1 for estado, _, _ in _resultados if estado == OK)
    fallidos = [n for estado, n, _ in _resultados if estado == FALLA]
    omitidos = [n for estado, n, _ in _resultados if estado == OMITIDO]
    print(f"  {passed} comprobaciones pasaron")
    print(f"  {len(fallidos)} fallaron")
    print(f"  {len(omitidos)} se omitieron")
    if fallidos:
        print("\n  Comprobaciones fallidas:")
        for nombre in fallidos:
            print(f"    - {nombre}")
    return 1 if fallidos else 0


if __name__ == "__main__":
    sys.exit(main())