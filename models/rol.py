from typing import Optional
from sqlmodel import SQLModel, Field


class RolBase(SQLModel):
    nombre: str = Field(min_length=2, max_length=50, unique=True)
    descripcion: Optional[str] = Field(default=None, max_length=255)


class Rol(RolBase, table=True):
    __tablename__ = "roles"  # type: ignore
    rol_id: Optional[int] = Field(default=None, primary_key=True)


class RolCreate(RolBase):
    pass


class RolUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=50)
    descripcion: Optional[str] = Field(default=None, max_length=255)
