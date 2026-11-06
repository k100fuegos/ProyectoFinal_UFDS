import os
from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "biblioteca_db")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")
DB_PORT = os.getenv("DB_PORT", "3306")

DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
SERVER_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}"

engine = create_engine(DB_URL, echo=False)


def asegurar_base_de_datos():
    """Crea la base de datos en el servidor MySQL si no existe."""
    try:
        server_engine = create_engine(SERVER_URL)
        with server_engine.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                    f"CHARACTER SET {DB_CHARSET} COLLATE {DB_CHARSET}_unicode_ci;"
                )
            )
            conn.commit()
    except Exception as e:
        print(f"Aviso al verificar o crear la base de datos '{DB_NAME}': {e}")


def inicializar_datos_semilla(target_engine=None):
    """Inserta los 2 roles fijos (1 = Administrador, 2 = Bibliotecario) y usuarios semilla si no existen."""
    from models.rol import Rol
    from models.usuario import Usuario
    from librerias.pwd import get_password_hash

    active_engine = target_engine or engine

    roles_default = [
        {
            "rol_id": 1,
            "nombre": "Administrador",
            "descripcion": (
                "Acceso completo al sistema, administración de usuarios, roles, "
                "catálogo bibliográfico, ejemplares, lectores, préstamos y bajas."
            ),
        },
        {
            "rol_id": 2,
            "nombre": "Bibliotecario",
            "descripcion": (
                "Gestión operativa del catálogo bibliográfico, ejemplares, lectores, "
                "registro de préstamos y devoluciones."
            ),
        },
    ]

    try:
        with Session(active_engine) as session:
            for rol_data in roles_default:
                rol_existente = session.exec(
                    select(Rol).where(
                        (Rol.rol_id == rol_data["rol_id"])
                        | (Rol.nombre == rol_data["nombre"])
                    )
                ).first()
                if not rol_existente:
                    session.add(Rol(**rol_data))
            session.commit()

            # 1. Usuario Administrador por defecto (rol_id = 1)
            admin_user = session.exec(
                select(Usuario).where(Usuario.username == "admin")
            ).first()
            if not admin_user:
                default_admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
                admin_user = Usuario(
                    rol_id=1,
                    nombre="Administrador General",
                    username="admin",
                    correo="admin@biblioteca.com",
                    password_hash=get_password_hash(default_admin_pass),
                    last_login=None,
                    activo=True,
                )
                session.add(admin_user)
                session.commit()
                print("Usuario administrador creado (username: admin)")

            # 2. Usuario Bibliotecario por defecto (rol_id = 2)
            biblio_user = session.exec(
                select(Usuario).where(Usuario.username == "bibliotecario")
            ).first()
            if not biblio_user:
                default_biblio_pass = os.getenv("DEFAULT_BIBLIO_PASSWORD", "biblio123")
                biblio_user = Usuario(
                    rol_id=2,
                    nombre="Bibliotecario de Turno",
                    username="bibliotecario",
                    correo="bibliotecario@biblioteca.com",
                    password_hash=get_password_hash(default_biblio_pass),
                    last_login=None,
                    activo=True,
                )
                session.add(biblio_user)
                session.commit()
                print("Usuario bibliotecario creado (username: bibliotecario)")
    except Exception as e:
        print(f"Aviso al inicializar datos semilla: {e}")


def asegurar_columna_portada():
    """Agrega la columna ``portada`` a bases de datos creadas antes de la feature.

    ``SQLModel.metadata.create_all`` no modifica tablas existentes, por lo que
    esta migración mínima mantiene compatibles las instalaciones ya en uso.
    """
    from sqlalchemy import inspect

    inspector = inspect(engine)
    if "libros" not in inspector.get_table_names():
        return

    columnas = {columna["name"] for columna in inspector.get_columns("libros")}
    if "portada" not in columnas:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE libros ADD COLUMN portada VARCHAR(255) NULL")
            )


def crear_db_y_tablas():
    asegurar_base_de_datos()
    try:
        import models  # noqa: F401 - Registra todos los modelos en SQLModel.metadata

        SQLModel.metadata.create_all(engine)
        asegurar_columna_portada()
        inicializar_datos_semilla()
    except Exception as e:
        print(f"Error en la inicialización de la base de datos: {e}")


def get_session():
    with Session(engine) as session:
        try:
            yield session
        except Exception as e:
            print(f"Error en la sesión de la base de datos: {e}")
            raise
