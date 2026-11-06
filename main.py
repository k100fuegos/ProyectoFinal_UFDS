import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.db import crear_db_y_tablas
from librerias.portadas import RUTA_PORTADAS
from oauth.oauth import router as oauth_router
from routers.router_roles import router as rol_router
from routers.router_usuarios import router as usuario_router
from routers.router_lectores import router as lector_router
from routers.router_categorias import router as categoria_router
from routers.router_autores import router as autor_router
from routers.router_libros import router as libro_router
from routers.router_ejemplares import router as ejemplar_router
from routers.router_prestamos import router as prestamo_router
import models  # noqa: F401

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
HABILITAR_DOCS = ENVIRONMENT in ("development", "dev", "local")


@asynccontextmanager
async def lifespan(app: FastAPI):
    crear_db_y_tablas()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="API REST Sistema Bibliotecario",
    description=(
        "API REST para la gestión de usuarios, roles, catálogo bibliográfico, "
        "ejemplares, lectores, préstamos y devoluciones."
    ),
    version="1.0.0",
    docs_url="/docs" if HABILITAR_DOCS else None,
    redoc_url="/redoc" if HABILITAR_DOCS else None,
    openapi_url="/openapi.json" if HABILITAR_DOCS else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Portadas subidas por los usuarios.
app.mount(
    "/media/portadas",
    StaticFiles(directory=RUTA_PORTADAS),
    name="portadas",
)


@app.get("/", summary="Estado de la API", status_code=status.HTTP_200_OK)
async def home():
    return {"message": "ok", "service": "API REST Sistema Bibliotecario"}


app.include_router(oauth_router, tags=["oauth"])
app.include_router(rol_router, tags=["roles"])
app.include_router(usuario_router, tags=["usuarios"])
app.include_router(lector_router, tags=["lectores"])
app.include_router(categoria_router, tags=["categorias"])
app.include_router(autor_router, tags=["autores"])
app.include_router(libro_router, tags=["libros"])
app.include_router(ejemplar_router, tags=["ejemplares"])
app.include_router(prestamo_router, tags=["prestamos"])

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True)
