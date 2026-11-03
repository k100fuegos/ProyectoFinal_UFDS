from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field, Column, Enum as SAEnum
from models.enums import EstadoPrestamo


def obtener_fecha_utc() -> datetime:
    return datetime.now(timezone.utc)


class PrestamoBase(SQLModel):
    lector_id: int = Field(
        foreign_key="lectores.lector_id",
        ondelete="RESTRICT",
        index=True,
    )
    ejemplar_id: int = Field(
        foreign_key="ejemplares.ejemplar_id",
        ondelete="RESTRICT",
        index=True,
    )
    observaciones: Optional[str] = Field(default=None, max_length=255)


class Prestamo(PrestamoBase, table=True):
    __tablename__ = "prestamos"  # type: ignore
    prestamo_id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(
        foreign_key="usuarios.usuario_id",
        ondelete="RESTRICT",
    )
    fecha_prestamo: datetime = Field(default_factory=obtener_fecha_utc)
    fecha_vencimiento: datetime
    fecha_devolucion: Optional[datetime] = Field(default=None)
    estado: EstadoPrestamo = Field(
        default=EstadoPrestamo.ACTIVO,
        sa_column=Column(
            SAEnum(EstadoPrestamo),
            nullable=False,
            index=True,
            default=EstadoPrestamo.ACTIVO,
        ),
    )


class PrestamoCreate(PrestamoBase):
    dias_prestamo: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Cantidad de días del préstamo para calcular fecha_vencimiento",
    )


class DevolucionRequest(SQLModel):
    observaciones: Optional[str] = Field(default=None, max_length=255)


class PrestamoRead(PrestamoBase):
    prestamo_id: int
    usuario_id: int
    fecha_prestamo: datetime
    fecha_vencimiento: datetime
    fecha_devolucion: Optional[datetime]
    estado: EstadoPrestamo
