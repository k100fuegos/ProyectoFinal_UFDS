# API REST Sistema Bibliotecario

API REST desarrollada con **FastAPI**, **SQLModel** y **MySQL** para administrar las operaciones principales de una biblioteca: usuarios y roles, autenticación JWT, catálogo bibliográfico (libros, autores y categorías), ejemplares físicos, lectores, préstamos y devoluciones.

---

## 1. Requisitos e instalación

1. Crear y activar el entorno virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Linux / macOS
   # .\.venv\Scripts\Activate.ps1   # Windows PowerShell
   ```
2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Copiar `.env-example` a `.env` y ajustar los datos de MySQL:
   ```bash
   cp .env-example .env             # Linux / macOS
   # Copy-Item .env-example .env    # Windows PowerShell
   ```
4. Definir `SECRET_KEY_TOKEN` en `.env`. Es **obligatorio**: la API no arranca si falta.
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
5. Verificar `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME=biblioteca_db` y `DB_PORT`. La base de datos, las tablas y los datos semilla se crean automáticamente al iniciar.

---

## 2. Ejecución

```bash
python main.py
```

O con `uvicorn`:

```bash
uvicorn main:app --reload --port 8000
```

- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

La documentación solo se habilita cuando `ENVIRONMENT` es `development`, `dev` o `local`.

---

## 3. Usuarios semilla

Al iniciar la aplicación se crean los 2 roles base y 2 cuentas de personal:

| Rol | `rol_id` | Usuario | Contraseña por defecto | Acceso |
|---|---|---|---|---|
| Administrador | `1` | `admin` | `admin123` | Acceso completo, incluida administración de usuarios/roles y bajas. |
| Bibliotecario | `2` | `bibliotecario` | `biblio123` | Gestión operativa de catálogo, ejemplares, lectores, préstamos y devoluciones. |

> Las contraseñas semilla son solo para demostración. Se recomienda cambiarlas en `.env` antes de un uso real.

Los roles personalizados (`rol_id >= 3`) pueden autenticarse, pero solo acceden a `GET /usuarios/me`; el resto de operaciones exige rol Administrador o Bibliotecario.

---

## 4. Seguridad

- Contraseñas almacenadas con **Argon2id** (`pwdlib`), con compatibilidad de verificación para hashes PBKDF2.
- Token **JWT** firmado con `SECRET_KEY_TOKEN`, con expiración configurable mediante `ACCESS_TOKEN_EXPIRE_MINUTES` (60 minutos por defecto).
- En cada request protegida se valida la firma y expiración del token y, además, se consulta la base de datos para comprobar que:
  - el usuario exista;
  - el usuario siga **activo**;
  - se use el **rol actual** del usuario, no el rol que tenía cuando se emitió el token.
- Login con bloqueo temporal por IP + usuario tras 3 intentos fallidos (`429 Too Many Requests`).
- Las credenciales incorrectas devuelven un mensaje genérico y no revelan si el usuario existe.
- El campo `password_hash` nunca se expone en las respuestas.

---

## 5. Paginación

Todos los endpoints de listado aceptan `offset` (por defecto `0`) y `limit` (por defecto `20`, máximo `100`):

- `GET /usuarios`
- `GET /roles`
- `GET /lectores`
- `GET /categorias`
- `GET /autores`
- `GET /libros`
- `GET /ejemplares`
- `GET /prestamos`
- `GET /prestamos/activos`

Los endpoints de detalle y las operaciones de escritura no se paginan.

---

## 6. Reglas de negocio implementadas

- No se presta un ejemplar que no esté en estado `Disponible` o que ya tenga un préstamo activo.
- El cambio de estado del ejemplar a `Prestado` se hace con una actualización atómica para evitar dos préstamos simultáneos del mismo ejemplar.
- Un préstamo identifica al lector, al ejemplar (y su libro), al usuario que lo registró, las fechas y el estado. La respuesta incluye `libro_id`.
- Al registrar la devolución, el préstamo pasa a `Devuelto` y el ejemplar vuelve a `Disponible`.
- Los préstamos activos cuya fecha de vencimiento ya pasó se marcan automáticamente como `Vencido` al consultar el historial o los préstamos activos.
- Las bajas de libros, lectores y ejemplares son lógicas; las eliminaciones físicas de roles, categorías y autores se bloquean si existen registros asociados.
- El estado `Eliminado` de un ejemplar solo se asigna mediante `DELETE /ejemplares/{id}`; un ejemplar eliminado no puede modificarse.

---

## 7. Pruebas automatizadas

La suite cubre los 10 casos obligatorios del PDF y validaciones adicionales de las correcciones (usuario desactivado con token antiguo, cambio de rol, paginación, préstamos vencidos y estado de ejemplares).

```bash
python -m unittest discover -s tests -v
```

Resultado esperado: **15 pruebas OK**. Las pruebas usan SQLite en memoria y no requieren MySQL ni datos manuales.

---

## 8. Estructura del proyecto

```text
├── config/
│   ├── db.py                     # Conexión MySQL, creación de tablas y datos semilla
│   ├── security.py               # Emisión/validación JWT y control de roles/usuario activo
│   ├── security_dependencia.py   # Dependencias de seguridad inyectables
│   └── session_dependencia.py    # Dependencia de sesión SQLModel
├── librerias/
│   ├── pwd.py                    # Hash de contraseñas con Argon2id
│   └── rate_limiter.py           # Bloqueo tras intentos fallidos de login
├── models/                       # 9 tablas SQLModel y esquemas Pydantic
├── oauth/
│   └── oauth.py                  # Endpoint POST /oauth/login
├── routers/                      # Endpoints REST por módulo
├── tests/
│   └── test_casos_obligatorios.py
├── main.py                       # Punto de entrada FastAPI
└── requirements.txt
```
