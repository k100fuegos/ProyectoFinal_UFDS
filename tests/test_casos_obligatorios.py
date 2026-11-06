import os
import unittest
from datetime import datetime, timedelta, timezone

# Debe configurarse antes de importar la aplicación: config.security exige
# la variable y falla al arrancar si no existe.
os.environ.setdefault("SECRET_KEY_TOKEN", "test-secret-key-para-pruebas-ufds-2026")
os.environ.setdefault("ENVIRONMENT", "testing")

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from config.db import get_session
from config.security import create_access_token
from librerias.pwd import get_password_hash
from librerias.rate_limiter import login_rate_limiter
from main import app
from models.autor import Autor
from models.categoria import Categoria
from models.ejemplar import Ejemplar
from models.enums import EstadoEjemplar, EstadoPrestamo
from models.lector import Lector
from models.libro import Libro
from models.prestamo import Prestamo
from models.rol import Rol
from models.usuario import Usuario

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def override_get_session():
    with Session(TEST_ENGINE) as session:
        yield session


class ApiBibliotecariaTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_session] = override_get_session
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        app.dependency_overrides.clear()
        TEST_ENGINE.dispose()

    def setUp(self):
        SQLModel.metadata.drop_all(TEST_ENGINE)
        SQLModel.metadata.create_all(TEST_ENGINE)
        login_rate_limiter.reset_all()
        self._crear_datos_base()
        self.admin_headers = self._headers(1, "admin", 1)
        self.biblio_headers = self._headers(2, "bibliotecario", 2)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _crear_datos_base(self):
        with Session(TEST_ENGINE) as session:
            session.add(
                Rol(
                    rol_id=1,
                    nombre="Administrador",
                    descripcion="Acceso completo",
                )
            )
            session.add(
                Rol(
                    rol_id=2,
                    nombre="Bibliotecario",
                    descripcion="Gestión operativa",
                )
            )
            session.add(
                Usuario(
                    usuario_id=1,
                    rol_id=1,
                    nombre="Administrador de Prueba",
                    username="admin",
                    correo="admin@test.com",
                    password_hash=get_password_hash("admin123"),
                    activo=True,
                )
            )
            session.add(
                Usuario(
                    usuario_id=2,
                    rol_id=2,
                    nombre="Bibliotecario de Prueba",
                    username="bibliotecario",
                    correo="bibliotecario@test.com",
                    password_hash=get_password_hash("biblio123"),
                    activo=True,
                )
            )
            session.commit()

    def _headers(self, usuario_id: int, username: str, rol_id: int):
        token, _ = create_access_token(
            {"id": usuario_id, "username": username, "id_rol": rol_id}
        )
        return {"Authorization": f"Bearer {token}"}

    def _login(self, username: str, password: str, status_code: int = 200):
        response = self.client.post(
            "/oauth/login",
            data={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, status_code, response.text)
        return response.json()

    def _crear_categoria(self, nombre: str = "Novela", headers=None):
        response = self.client.post(
            "/categorias",
            json={"nombre": nombre, "descripcion": "Categoría de prueba"},
            headers=headers or self.biblio_headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _crear_autor(self, headers=None):
        response = self.client.post(
            "/autores",
            json={
                "nombre": "Gabriel",
                "apellido": "García Márquez",
                "nacionalidad": "Colombiana",
            },
            headers=headers or self.biblio_headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _crear_libro(self, categoria_id: int, autor_id: int, headers=None):
        response = self.client.post(
            "/libros",
            json={
                "isbn": "9780307474728",
                "titulo": "Cien años de soledad",
                "editorial": "Sudamericana",
                "anio_publicacion": 1967,
                "categoria_id": categoria_id,
                "autores_ids": [autor_id],
            },
            headers=headers or self.biblio_headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _crear_lector(self, headers=None):
        response = self.client.post(
            "/lectores",
            json={
                "nombre": "Lector",
                "apellido": "de Prueba",
                "documento": "DOC-0001",
                "correo": "lector@test.com",
                "telefono": "70000000",
            },
            headers=headers or self.biblio_headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _crear_ejemplar(
        self, libro_id: int, codigo: str = "EJ-0001", headers=None
    ):
        response = self.client.post(
            "/ejemplares",
            json={
                "libro_id": libro_id,
                "codigo_inventario": codigo,
                "ubicacion": "Estante A-1",
            },
            headers=headers or self.biblio_headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _preparar_prestamo(self, codigo_ejemplar: str = "EJ-0001"):
        categoria = self._crear_categoria()
        autor = self._crear_autor()
        libro = self._crear_libro(categoria["categoria_id"], autor["autor_id"])
        lector = self._crear_lector()
        ejemplar = self._crear_ejemplar(libro["libro_id"], codigo_ejemplar)
        return lector, libro, ejemplar

    def _crear_prestamo(self, lector_id: int, ejemplar_id: int, headers=None):
        response = self.client.post(
            "/prestamos",
            json={"lector_id": lector_id, "ejemplar_id": ejemplar_id},
            headers=headers or self.biblio_headers,
        )
        return response

    # ------------------------------------------------------------------
    # Casos obligatorios del PDF
    # ------------------------------------------------------------------
    def test_01_login_valido(self):
        data = self._login("admin", "admin123")
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertGreater(data["expires_in"], 0)
        self.assertNotIn("password", data)

    def test_02_login_invalido(self):
        data = self._login("admin", "clave-incorrecta", status_code=401)
        self.assertEqual(data["detail"], "Credenciales inválidas")

        data = self._login("usuario-inexistente", "cualquiera", status_code=401)
        self.assertEqual(data["detail"], "Credenciales inválidas")

    def test_03_ruta_protegida_sin_token(self):
        response = self.client.get("/usuarios")
        self.assertEqual(response.status_code, 401)
        self.assertIn("www-authenticate", response.headers)

    def test_04_token_invalido_y_expirado(self):
        response = self.client.get(
            "/usuarios/me",
            headers={"Authorization": "Bearer token-invalido"},
        )
        self.assertEqual(response.status_code, 401)

        token_expirado, _ = create_access_token(
            {"id": 1, "username": "admin", "id_rol": 1},
            expires_delta=timedelta(seconds=-5),
        )
        response = self.client.get(
            "/usuarios/me",
            headers={"Authorization": f"Bearer {token_expirado}"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Token expirado")

    def test_05_accion_sin_permiso(self):
        response = self.client.post(
            "/usuarios",
            json={
                "nombre": "No Autorizado",
                "username": "no_autorizado",
                "correo": "no_autorizado@test.com",
                "password": "password123",
                "rol_id": 2,
            },
            headers=self.biblio_headers,
        )
        self.assertEqual(response.status_code, 403)

    def test_06_crud_libro(self):
        categoria = self._crear_categoria()
        autor = self._crear_autor()
        libro = self._crear_libro(categoria["categoria_id"], autor["autor_id"])

        response = self.client.get(
            f"/libros/{libro['libro_id']}", headers=self.biblio_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["titulo"], "Cien años de soledad")

        response = self.client.put(
            f"/libros/{libro['libro_id']}",
            json={"titulo": "Cien años de soledad (edición revisada)"},
            headers=self.biblio_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["titulo"], "Cien años de soledad (edición revisada)"
        )

        response = self.client.delete(
            f"/libros/{libro['libro_id']}", headers=self.admin_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["activo"])

    def test_07_prestamo_valido(self):
        lector, libro, ejemplar = self._preparar_prestamo()

        response = self._crear_prestamo(
            lector["lector_id"], ejemplar["ejemplar_id"]
        )
        self.assertEqual(response.status_code, 201, response.text)
        prestamo = response.json()
        self.assertEqual(prestamo["estado"], "Activo")
        self.assertEqual(prestamo["libro_id"], libro["libro_id"])
        self.assertIsNone(prestamo["fecha_devolucion"])

        response = self.client.get(
            f"/ejemplares/{ejemplar['ejemplar_id']}",
            headers=self.biblio_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["estado"], "Prestado")

    def test_08_prestamo_invalido(self):
        lector, _, ejemplar = self._preparar_prestamo()

        response = self._crear_prestamo(
            lector["lector_id"], ejemplar["ejemplar_id"]
        )
        self.assertEqual(response.status_code, 201, response.text)

        response = self._crear_prestamo(
            lector["lector_id"], ejemplar["ejemplar_id"]
        )
        self.assertEqual(response.status_code, 409)

    def test_09_devolucion(self):
        lector, _, ejemplar = self._preparar_prestamo()
        prestamo = self._crear_prestamo(
            lector["lector_id"], ejemplar["ejemplar_id"]
        ).json()

        response = self.client.patch(
            f"/prestamos/{prestamo['prestamo_id']}/devolucion",
            json={},
            headers=self.biblio_headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        devuelto = response.json()
        self.assertEqual(devuelto["estado"], "Devuelto")
        self.assertIsNotNone(devuelto["fecha_devolucion"])

        response = self.client.get(
            f"/ejemplares/{ejemplar['ejemplar_id']}",
            headers=self.biblio_headers,
        )
        self.assertEqual(response.json()["estado"], "Disponible")

        response = self.client.patch(
            f"/prestamos/{prestamo['prestamo_id']}/devolucion",
            json={},
            headers=self.biblio_headers,
        )
        self.assertEqual(response.status_code, 409)

    def test_10_datos_invalidos(self):
        response = self.client.post(
            "/libros",
            json={
                "isbn": "9780307474728",
                "titulo": "Libro sin autores",
                "categoria_id": 1,
                "autores_ids": [],
            },
            headers=self.biblio_headers,
        )
        self.assertEqual(response.status_code, 422)

        response = self.client.post(
            "/lectores",
            json={
                "nombre": "Lector",
                "apellido": "Inválido",
                "documento": "DOC-0002",
                "correo": "correo-invalido",
            },
            headers=self.biblio_headers,
        )
        self.assertEqual(response.status_code, 422)

        response = self.client.post(
            "/prestamos",
            json={"lector_id": 1, "ejemplar_id": 1, "dias_prestamo": 0},
            headers=self.biblio_headers,
        )
        self.assertEqual(response.status_code, 422)

    # ------------------------------------------------------------------
    # Pruebas adicionales de las correcciones
    # ------------------------------------------------------------------
    def test_usuario_desactivado_con_token_antiguo(self):
        response = self.client.post(
            "/usuarios",
            json={
                "nombre": "Usuario Temporal",
                "username": "temporal",
                "correo": "temporal@test.com",
                "password": "password123",
                "rol_id": 2,
            },
            headers=self.admin_headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        usuario_id = response.json()["usuario_id"]
        token = self._login("temporal", "password123")["access_token"]

        response = self.client.patch(
            f"/usuarios/{usuario_id}/desactivar", headers=self.admin_headers
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            "/usuarios/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Usuario inactivo o no disponible")

        self._login("temporal", "password123", status_code=403)

    def test_rol_actualizado_se_toma_de_la_bd(self):
        response = self.client.post(
            "/usuarios",
            json={
                "nombre": "Usuario Administrador",
                "username": "admin_temporal",
                "correo": "admin_temporal@test.com",
                "password": "password123",
                "rol_id": 1,
            },
            headers=self.admin_headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        usuario_id = response.json()["usuario_id"]
        token = self._login("admin_temporal", "password123")["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = self.client.put(
            f"/usuarios/{usuario_id}",
            json={"rol_id": 2},
            headers=self.admin_headers,
        )
        self.assertEqual(response.status_code, 200, response.text)

        response = self.client.post(
            "/usuarios",
            json={
                "nombre": "Otro Usuario",
                "username": "otro_usuario",
                "correo": "otro_usuario@test.com",
                "password": "password123",
                "rol_id": 2,
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/usuarios/me", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rol_id"], 2)

    def test_paginacion_roles_y_prestamos_activos(self):
        for nombre in ("Investigador", "Auditor"):
            response = self.client.post(
                "/roles",
                json={"nombre": nombre, "descripcion": "Rol de prueba"},
                headers=self.admin_headers,
            )
            self.assertEqual(response.status_code, 201, response.text)

        response = self.client.get(
            "/roles?offset=0&limit=1", headers=self.admin_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

        lector, libro, ejemplar_1 = self._preparar_prestamo("EJ-0001")
        ejemplar_2 = self._crear_ejemplar(libro["libro_id"], "EJ-0002")
        self._crear_prestamo(lector["lector_id"], ejemplar_1["ejemplar_id"])
        self._crear_prestamo(lector["lector_id"], ejemplar_2["ejemplar_id"])

        response = self.client.get(
            "/prestamos/activos?offset=0&limit=1", headers=self.biblio_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_prestamo_vencido_se_actualiza_al_consultar(self):
        lector, _, ejemplar = self._preparar_prestamo()
        prestamo = self._crear_prestamo(
            lector["lector_id"], ejemplar["ejemplar_id"]
        ).json()

        with Session(TEST_ENGINE) as session:
            registro = session.exec(
                select(Prestamo).where(
                    Prestamo.prestamo_id == prestamo["prestamo_id"]
                )
            ).first()
            registro.fecha_vencimiento = datetime.now(timezone.utc) - timedelta(
                days=1
            )
            registro.estado = EstadoPrestamo.ACTIVO
            session.add(registro)
            session.commit()

        response = self.client.get("/prestamos", headers=self.biblio_headers)
        self.assertEqual(response.status_code, 200)
        actualizado = next(
            p
            for p in response.json()
            if p["prestamo_id"] == prestamo["prestamo_id"]
        )
        self.assertEqual(actualizado["estado"], "Vencido")

        response = self.client.get(
            "/prestamos/activos", headers=self.biblio_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(
                p["prestamo_id"] == prestamo["prestamo_id"]
                for p in response.json()
            )
        )

    def test_patch_ejemplar_no_permite_eliminado(self):
        categoria = self._crear_categoria()
        autor = self._crear_autor()
        libro = self._crear_libro(categoria["categoria_id"], autor["autor_id"])
        ejemplar = self._crear_ejemplar(libro["libro_id"])

        response = self.client.patch(
            f"/ejemplares/{ejemplar['ejemplar_id']}",
            json={"estado": "Eliminado"},
            headers=self.biblio_headers,
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.delete(
            f"/ejemplares/{ejemplar['ejemplar_id']}", headers=self.admin_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["estado"], "Eliminado")

        response = self.client.patch(
            f"/ejemplares/{ejemplar['ejemplar_id']}",
            json={"ubicacion": "Otra ubicación"},
            headers=self.biblio_headers,
        )
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
