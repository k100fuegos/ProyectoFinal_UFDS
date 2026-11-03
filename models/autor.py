from typing import Optional
from sqlmodel import SQLModel, Field


class AutorBase(SQLModel):
    nombre: str = Field(min_length=2, max_length=100)
    apellido: str = Field(min_length=2, max_length=100)
    nacionalidad: Optional[str] = Field(default=None, max_length=80)


class Autor(AutorBase, table=True):
    __tablename__ = "autores"  # type: ignore
    autor_id: Optional[int] = Field(default=None, primary_key=True)


class AutorCreate(AutorBase):
    pass


class AutorUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    apellido: Optional[str] = Field(default=None, min_length=2, max_length=100)
    nacionalidad: Optional[str] = Field(default=None, max_length=80)
