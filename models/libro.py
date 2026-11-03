from typing import Optional
from sqlmodel import SQLModel, Field


class LibroBase(SQLModel):
    isbn: str = Field(min_length=10, max_length=17, unique=True, index=True)
    titulo: str = Field(min_length=1, max_length=255, index=True)
    editorial: Optional[str] = Field(default=None, max_length=150)
    anio_publicacion: Optional[int] = Field(default=None, ge=1000, le=2100)
    categoria_id: int = Field(
        foreign_key="categorias.categoria_id",
        ondelete="RESTRICT",
    )


class Libro(LibroBase, table=True):
    __tablename__ = "libros"  # type: ignore
    libro_id: Optional[int] = Field(default=None, primary_key=True)
    activo: bool = Field(default=True)


class LibroCreate(LibroBase):
    autores_ids: list[int] = Field(min_length=1)


class LibroUpdate(SQLModel):
    isbn: Optional[str] = Field(default=None, min_length=10, max_length=17)
    titulo: Optional[str] = Field(default=None, min_length=1, max_length=255)
    editorial: Optional[str] = Field(default=None, max_length=150)
    anio_publicacion: Optional[int] = Field(default=None, ge=1000, le=2100)
    categoria_id: Optional[int] = None
    autores_ids: Optional[list[int]] = None
    activo: Optional[bool] = None


class LibroRead(LibroBase):
    libro_id: int
    activo: bool
    autores_ids: list[int] = []
    ejemplares_disponibles: int = 0
