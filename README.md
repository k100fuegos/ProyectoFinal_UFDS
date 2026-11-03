# API REST Sistema Bibliotecario

API REST desarrollada con **FastAPI**, **SQLModel** y **MySQL** para administrar las operaciones principales de una biblioteca: gestión de usuarios y roles, autenticación JWT con protección contra fuerza bruta, catálogo bibliográfico (libros, autores y categorías), ejemplares físicos, lectores, préstamos y devoluciones.

---

## 1. Requisitos e Instalación

1. Activar el entorno virtual e instalar dependencias:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. Configurar las variables de entorno copiando `.env-example` a `.env`:
   ```powershell
   Copy-Item .env-example .env
   ```
3. Ajustar las credenciales de tu servidor MySQL en `.env` (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME=biblioteca_db`). La base de datos, las 9 tablas y los datos semilla se crean automáticamente al iniciar la aplicación.

---

## 2. Ejecución de la API

```powershell
.\.venv\Scripts\python.exe main.py
```
O con `uvicorn`:
```powershell
.\.venv\Scripts\uvicorn.exe main:app --reload --port 8000
```

- **Documentación interactiva (Swagger UI):** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

---

## 3. Usuarios Semilla para la Demostración

Al iniciar la aplicación se crean automáticamente los 2 roles del sistema y 2 cuentas de personal:

| Rol | `rol_id` | Usuario (`username`) | Contraseña por defecto | Permisos |
|---|---|---|---|---|
| **Administrador** | `1` | `admin` | `admin123` | Acceso total (incluye gestión de usuarios/roles y bajas/eliminaciones). |
| **Bibliotecario** | `2` | `bibliotecario` | `biblio123` | Gestión operativa de catálogo, ejemplares, lectores, préstamos y devoluciones. |

> **Protección de Login:** El endpoint `POST /oauth/login` bloquea temporalmente por IP + usuario al alcanzar **3 intentos fallidos consecutivos** (`429 Too Many Requests`).

---

## 4. Estructura del Proyecto

```text
├── config/
│   ├── db.py                     # Conexión MySQL, creación de tablas y datos semilla
│   ├── security.py               # Emisión/validación JWT y control de roles
│   ├── security_dependencia.py   # Dependencias de seguridad inyectables
│   └── session_dependencia.py    # Dependencia de sesión SQLModel
├── librerias/
│   ├── pwd.py                    # Hash de contraseñas con Argon2id (pwdlib)
│   └── rate_limiter.py           # Bloqueo al 3er intento fallido de login
├── models/                       # 9 tablas SQLModel y esquemas Pydantic
├── oauth/
│   └── oauth.py                  # Endpoint POST /oauth/login
├── routers/                      # Endpoints REST por módulo
├── tests/
│   └── test_casos_obligatorios.py # Suite automatizada para los 10 casos del PDF
└── main.py                       # Punto de entrada FastAPI
```

---

## 5. Ejecución de Pruebas Automatizadas (10 Casos Obligatorios)

Para ejecutar la suite de pruebas que valida los 10 casos exigidos en la rúbrica sin requerir datos manuales:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
