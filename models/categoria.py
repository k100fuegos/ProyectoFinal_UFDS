from typing import Optional
from sqlmodel import SQLModel, Field


class CategoriaBase(SQLModel):
    nombre: str = Field(min_length=2, max_length=100, unique=True)
    descripcion: Optional[str] = Field(default=None, max_length=255)


class Categoria(CategoriaBase, table=True):
    __tablename__ = "categorias"  # type: ignore
    categoria_id: Optional[int] = Field(default=None, primary_key=True)


class CategoriaCreate(CategoriaBase):
    pass


class CategoriaUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)
