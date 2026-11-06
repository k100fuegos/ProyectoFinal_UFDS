from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import update
from sqlmodel import select
from config.session_dependencia import SessionDeDependencia
from config.security_dependencia import Biblio_Token_Dependencia
from models.prestamo import (
    Prestamo,
    PrestamoCreate,
    PrestamoRead,
    DevolucionRequest,
)
from models.ejemplar import Ejemplar
from models.libro import Libro
from models.lector import Lector
from models.enums import EstadoEjemplar, EstadoPrestamo

router = APIRouter()


def obtener_prestamo_o_404(
    session: SessionDeDependencia, prestamo_id: int
) -> Prestamo:
    prestamo = session.get(Prestamo, prestamo_id)
    if not prestamo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Préstamo no encontrado",
        )
    return prestamo


def construir_prestamo_read(
    session: SessionDeDependencia, prestamo: Prestamo
) -> PrestamoRead:
    """Incluye el libro asociado al ejemplar en la respuesta del préstamo."""
    ejemplar = session.get(Ejemplar, prestamo.ejemplar_id)
    return PrestamoRead(
        **prestamo.model_dump(),
        libro_id=ejemplar.libro_id if ejemplar else None,
    )


def actualizar_prestamos_vencidos(session: SessionDeDependencia) -> None:
    """Marca como Vencido los préstamos activos cuya fecha de vencimiento pasó."""
    ahora = datetime.now(timezone.utc)
    session.execute(
        update(Prestamo)
        .where(
            Prestamo.estado == EstadoPrestamo.ACTIVO,
            Prestamo.fecha_vencimiento < ahora,
        )
        .values(estado=EstadoPrestamo.VENCIDO)
        .execution_options(synchronize_session=False)
    )
    # Se confirma siempre para cerrar la transacción y liberar bloqueos,
    # incluso cuando no había préstamos por vencer.
    session.commit()


@router.get(
    "/prestamos",
    response_model=list[PrestamoRead],
    status_code=status.HTTP_200_OK,
    summary="Consultar historial de préstamos con filtros opcionales",
)
async def get_prestamos(
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
    lector_id: int | None = Query(None, description="Filtrar por lector"),
    ejemplar_id: int | None = Query(None, description="Filtrar por ejemplar"),
    estado: EstadoPrestamo | None = Query(None, description="Filtrar por estado"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    actualizar_prestamos_vencidos(session)

    consulta = select(Prestamo)
    if lector_id is not None:
        consulta = consulta.where(Prestamo.lector_id == lector_id)
    if ejemplar_id is not None:
        consulta = consulta.where(Prestamo.ejemplar_id == ejemplar_id)
    if estado is not None:
        consulta = consulta.where(Prestamo.estado == estado)

    prestamos = session.exec(consulta.offset(offset).limit(limit)).all()
    return [construir_prestamo_read(session, prestamo) for prestamo in prestamos]


@router.get(
    "/prestamos/activos",
    response_model=list[PrestamoRead],
    status_code=status.HTTP_200_OK,
    summary="Listar únicamente los préstamos activos pendientes de devolución",
)
async def get_prestamos_activos(
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    actualizar_prestamos_vencidos(session)

    consulta = (
        select(Prestamo)
        .where(
            Prestamo.estado.in_([EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO])  # type: ignore
        )
        .offset(offset)
        .limit(limit)
    )
    prestamos = session.exec(consulta).all()
    return [construir_prestamo_read(session, prestamo) for prestamo in prestamos]


@router.get(
    "/prestamos/{prestamo_id}",
    response_model=PrestamoRead,
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de un préstamo por ID",
)
async def get_prestamo(
    prestamo_id: int,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    actualizar_prestamos_vencidos(session)
    prestamo = obtener_prestamo_o_404(session, prestamo_id)
    return construir_prestamo_read(session, prestamo)


@router.post(
    "/prestamos",
    response_model=PrestamoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar préstamo de un ejemplar disponible",
)
async def create_prestamo(
    datos: PrestamoCreate,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    """
    Reglas de negocio aplicadas:
    1. El lector debe existir y estar activo.
    2. El ejemplar debe existir, pertenecer a un libro activo y estar en estado 'Disponible'.
    3. Al registrarse el préstamo, el ejemplar pasa a 'Prestado' en la misma transacción.
    """
    lector = session.get(Lector, datos.lector_id)
    if not lector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El lector especificado no existe",
        )
    if not lector.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El lector se encuentra inactivo y no puede solicitar préstamos",
        )

    ejemplar = session.get(Ejemplar, datos.ejemplar_id)
    if not ejemplar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El ejemplar especificado no existe",
        )

    # Regla de negocio #1: No se puede prestar un ejemplar prestado o no disponible
    if ejemplar.estado != EstadoEjemplar.DISPONIBLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"El ejemplar '{ejemplar.codigo_inventario}' no está disponible "
                f"para préstamo (estado actual: {ejemplar.estado.value})"
            ),
        )

    libro = session.get(Libro, ejemplar.libro_id)
    if not libro or not libro.activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El libro asociado al ejemplar no se encuentra activo para préstamo",
        )

    prestamo_existente = session.exec(
        select(Prestamo).where(
            Prestamo.ejemplar_id == datos.ejemplar_id,
            Prestamo.estado.in_([EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO]),  # type: ignore
        )
    ).first()
    if prestamo_existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El ejemplar ya posee un préstamo activo pendiente de devolución",
        )

    # Actualización atómica: si dos solicitudes compiten por el mismo ejemplar,
    # solo una puede cambiar el estado de 'Disponible' a 'Prestado'.
    resultado = session.execute(
        update(Ejemplar)
        .where(
            Ejemplar.ejemplar_id == datos.ejemplar_id,
            Ejemplar.estado == EstadoEjemplar.DISPONIBLE,
        )
        .values(estado=EstadoEjemplar.PRESTADO)
        .execution_options(synchronize_session=False)
    )
    if resultado.rowcount != 1:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El ejemplar dejó de estar disponible para préstamo",
        )

    ahora = datetime.now(timezone.utc)
    vencimiento = ahora + timedelta(days=datos.dias_prestamo)
    usuario_id = token.get("id")

    prestamo = Prestamo(
        lector_id=datos.lector_id,
        ejemplar_id=datos.ejemplar_id,
        usuario_id=usuario_id,  # type: ignore
        fecha_prestamo=ahora,
        fecha_vencimiento=vencimiento,
        fecha_devolucion=None,
        estado=EstadoPrestamo.ACTIVO,
        observaciones=datos.observaciones,
    )

    session.add(prestamo)
    session.commit()
    session.refresh(prestamo)
    return construir_prestamo_read(session, prestamo)


@router.patch(
    "/prestamos/{prestamo_id}/devolucion",
    response_model=PrestamoRead,
    status_code=status.HTTP_200_OK,
    summary="Registrar devolución de un préstamo y liberar disponibilidad del ejemplar",
)
async def registrar_devolucion(
    prestamo_id: int,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
    datos: DevolucionRequest | None = None,
):
    """
    Regla de negocio #3: Al registrar una devolución, el préstamo pasa a 'Devuelto'
    y el ejemplar vuelve a estar 'Disponible'.
    """
    prestamo = obtener_prestamo_o_404(session, prestamo_id)

    if prestamo.estado == EstadoPrestamo.DEVUELTO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este préstamo ya fue devuelto anteriormente",
        )

    ejemplar = session.get(Ejemplar, prestamo.ejemplar_id)
    if not ejemplar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ejemplar asociado al préstamo no encontrado",
        )

    prestamo.estado = EstadoPrestamo.DEVUELTO
    prestamo.fecha_devolucion = datetime.now(timezone.utc)
    if datos and datos.observaciones is not None:
        prestamo.observaciones = datos.observaciones

    ejemplar.estado = EstadoEjemplar.DISPONIBLE

    session.add(prestamo)
    session.add(ejemplar)
    session.commit()
    session.refresh(prestamo)
    return construir_prestamo_read(session, prestamo)
