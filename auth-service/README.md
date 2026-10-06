# MS1 · Microservicio de Autenticación y Usuarios

> ⚠️ **DEPRECADO — este servicio no es el MS1 del sistema**
>
> El MS1 vigente es [`backend/services/ms1_auth`](../backend/services/ms1_auth),
> y su Gateway es [`backend/gateway`](../backend/gateway). Este directorio
> mantiene un MS1 alternativo en el puerto 8001 con un **contrato de token
> incompatible**:
>
> | | `auth-service/` (este) | `backend/services/ms1_auth/` (vigente) |
> |---|---|---|
> | Identificador | `sub` = UUID (`user_id: UUID`) | `sub` = entero positivo (`usuario_id`) |
> | Roles | claim `role`, **singular** | claim `roles`, **lista** plural |
> | Migraciones | sin Alembic | Alembic (`0001`, `0002`) |
> | Roles de la respuesta | `role: string` | `roles: list[NombreRol]` |
> | Contrato compartido | local a este servicio | [`shared/auth.py`](../backend/shared/auth.py) |
>
> Un token emitido aquí **no es aceptado** por MS2, MS3, MS4 ni por la Gateway,
> porque todos validan con `shared/auth.py`. Por eso las dos implementaciones no
> pueden convivir en la misma arquitectura: quien use la ruta equivocada obtiene
> `401` de forma difícil de diagnosticar.
>
> **Al integrar, usa `backend/services/ms1_auth/`.** El contrato del token está
> documentado en
> [`backend/docs/contratos-api-gateway.md`](../backend/docs/contratos-api-gateway.md),
> sección «El JWT: claims, validación y quién las aplica».
>
> Este código **no se borra** en esta rama: retirar un microservicio completo es
> decisión del equipo, no de una corrección de documentación. Si se decide
> eliminarlo, `git rm -r auth-service/` es suficiente, porque nada en
> `backend/`, `frontend/` ni la Gateway lo importa.

---

Microservicio Python/FastAPI del sistema **Taller Mecánico Sistematizado**
(ver `Sprint 0 - Entregables/01-arquitectura.png`). Gestiona cuentas, roles,
autenticación y emisión de sesiones (JWT) para los portales de Cliente,
Mecánico y Administrador.

## Arquitectura

Sigue arquitectura hexagonal, igual que el frontend (RNF-01):

```
app/
├── domain/            # Entidades y puertos (interfaces). No depende de nada externo.
│   ├── entities/user.py
│   └── ports/         # PasswordHasher, TokenProvider, UserRepository
├── application/        # Casos de uso: RegisterUserUseCase, LoginUserUseCase
│   ├── dto/
│   └── use_cases/
├── infrastructure/      # Implementaciones concretas (adapters)
│   ├── db/             # SQLAlchemy + PostgreSQL
│   ├── security/        # bcrypt (passlib) + JWT (python-jose)
│   └── api/             # FastAPI: routers, schemas, dependencias
└── main.py
```

## Requisitos cumplidos hoy

- **Estructura inicial del microservicio** (dominio/aplicación/infraestructura).
- **Autenticación con JWT** (`POST /auth/login`, RF-01, RF-02, RNF-07).
- **Almacenamiento seguro de contraseñas** con bcrypt vía `passlib` (RNF-06).
- Registro de usuarios con rol (`POST /auth/register`, RF-03).
- Endpoint `GET /auth/me` para validar sesión con el token (RF-05).

## Cómo correrlo localmente

1. Copiar variables de entorno:
   ```bash
   cp .env.example .env
   ```
2. Levantar la base de datos y el servicio con Docker:
   ```bash
   docker compose up --build
   ```
   La API queda en `http://localhost:8001` (docs interactivas en `/docs`).

   **Alternativa sin Docker:** crea una BD Postgres local, ajusta `DATABASE_URL`
   en `.env`, y corre:
   ```bash
   python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements-dev.txt
   uvicorn app.main:app --reload --port 8001
   ```

## Endpoints

| Método | Ruta            | Descripción                              | Auth |
| ------ | --------------- | ----------------------------------------- | ---- |
| POST   | `/auth/register` | Crea un usuario (cliente/mecanico/administrador) | No   |
| POST   | `/auth/login`     | Autentica y devuelve `access_token` (JWT) | No   |
| GET    | `/auth/me`        | Devuelve el usuario del token actual      | Sí (`Authorization: Bearer <token>`) |
| GET    | `/health`         | Healthcheck                               | No   |

## Probar rápido con curl

```bash
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"ana@example.com","password":"ClaveSegura123","full_name":"Ana Pérez","role":"cliente"}'

curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ana@example.com","password":"ClaveSegura123"}'
```

## Tests

```bash
pytest
```

## Pendiente (próximas iteraciones)

- Migraciones con Alembic (por ahora las tablas se crean automáticamente al iniciar).
- Endpoint de logout / revocación de tokens.
- Rate limiting en `/auth/login`.
- Conexión con el API Gateway (FastAPI) que enruta a los 4 microservicios.
