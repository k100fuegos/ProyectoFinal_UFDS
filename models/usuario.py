from datetime import datetime, timezone
from typing import Optional
from pydantic import EmailStr
from sqlmodel import SQLModel, Field


def obtener_fecha_utc() -> datetime:
    return datetime.now(timezone.utc)


class UsuarioBase(SQLModel):
    nombre: str = Field(min_length=3, max_length=150)
    username: str = Field(min_length=4, max_length=50, unique=True, index=True)
    correo: EmailStr = Field(max_length=255, unique=True)
    activo: bool = Field(default=True)


class Usuario(UsuarioBase, table=True):
    __tablename__ = "usuarios"  # type: ignore
    usuario_id: Optional[int] = Field(default=None, primary_key=True)
    rol_id: int = Field(foreign_key="roles.rol_id", ondelete="RESTRICT")
    password_hash: str = Field(max_length=255)
    fecha_creacion: datetime = Field(default_factory=obtener_fecha_utc)
    last_login: Optional[datetime] = Field(default=None)


class UsuarioCreate(UsuarioBase):
    password: str = Field(min_length=8, max_length=128)
    rol_id: int = Field(default=2)  # 1 = Administrador, 2 = Bibliotecario


class UsuarioUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, min_length=3, max_length=150)
    username: Optional[str] = Field(default=None, min_length=4, max_length=50)
    correo: Optional[EmailStr] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    rol_id: Optional[int] = None
    activo: Optional[bool] = None


class UsuarioRead(UsuarioBase):
    usuario_id: int
    rol_id: int
    fecha_creacion: datetime
    last_login: Optional[datetime] = None
