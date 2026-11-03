from datetime import datetime, timezone
from typing import Optional
from pydantic import EmailStr
from sqlmodel import SQLModel, Field


def obtener_fecha_utc() -> datetime:
    return datetime.now(timezone.utc)


class LectorBase(SQLModel):
    nombre: str = Field(min_length=2, max_length=100)
    apellido: str = Field(min_length=2, max_length=100)
    documento: str = Field(
        min_length=5,
        max_length=30,
        unique=True,
        index=True,
        description="DUI, carnet estudiantil o pasaporte",
    )
    correo: EmailStr = Field(max_length=255, unique=True)
    telefono: Optional[str] = Field(default=None, min_length=8, max_length=20)
    activo: bool = Field(default=True)


class Lector(LectorBase, table=True):
    __tablename__ = "lectores"  # type: ignore
    lector_id: Optional[int] = Field(default=None, primary_key=True)
    fecha_registro: datetime = Field(default_factory=obtener_fecha_utc)


class LectorCreate(LectorBase):
    pass


class LectorUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    apellido: Optional[str] = Field(default=None, min_length=2, max_length=100)
    documento: Optional[str] = Field(default=None, min_length=5, max_length=30)
    correo: Optional[EmailStr] = Field(default=None, max_length=255)
    telefono: Optional[str] = Field(default=None, min_length=8, max_length=20)
    activo: Optional[bool] = None
