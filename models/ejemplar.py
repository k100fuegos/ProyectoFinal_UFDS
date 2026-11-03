from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field, Column, Enum as SAEnum
from models.enums import EstadoEjemplar


def obtener_fecha_utc() -> datetime:
    return datetime.now(timezone.utc)


class EjemplarBase(SQLModel):
    libro_id: int = Field(foreign_key="libros.libro_id", ondelete="RESTRICT")
    codigo_inventario: str = Field(min_length=3, max_length=50, unique=True)
    ubicacion: Optional[str] = Field(default=None, max_length=100)


class Ejemplar(EjemplarBase, table=True):
    __tablename__ = "ejemplares"  # type: ignore
    ejemplar_id: Optional[int] = Field(default=None, primary_key=True)
    estado: EstadoEjemplar = Field(
        default=EstadoEjemplar.DISPONIBLE,
        sa_column=Column(
            SAEnum(EstadoEjemplar),
            nullable=False,
            default=EstadoEjemplar.DISPONIBLE,
        ),
    )
    fecha_ingreso: datetime = Field(default_factory=obtener_fecha_utc)


class EjemplarCreate(EjemplarBase):
    pass


class EjemplarUpdate(SQLModel):
    ubicacion: Optional[str] = Field(default=None, max_length=100)
    estado: Optional[EstadoEjemplar] = None
