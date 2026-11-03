from enum import Enum


class EstadoEjemplar(str, Enum):
    DISPONIBLE = "Disponible"
    PRESTADO = "Prestado"
    MANTENIMIENTO = "Mantenimiento"
    ELIMINADO = "Eliminado"


class EstadoPrestamo(str, Enum):
    ACTIVO = "Activo"
    DEVUELTO = "Devuelto"
    VENCIDO = "Vencido"
