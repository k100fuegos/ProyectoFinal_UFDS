from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select
from config.session_dependencia import SessionDeDependencia
from config.security_dependencia import (
    Admin_Token_Dependencia,
    Biblio_Token_Dependencia,
)
from models.ejemplar import Ejemplar, EjemplarCreate, EjemplarUpdate
from models.libro import Libro
from models.enums import EstadoEjemplar

router = APIRouter()


def obtener_ejemplar_o_404(
    session: SessionDeDependencia, ejemplar_id: int
) -> Ejemplar:
    ejemplar = session.get(Ejemplar, ejemplar_id)
    if not ejemplar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ejemplar no encontrado",
        )
    return ejemplar


@router.get(
    "/ejemplares",
    response_model=list[Ejemplar],
    status_code=status.HTTP_200_OK,
    summary="Listar ejemplares físicos con filtros por libro o estado",
)
async def get_ejemplares(
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
    libro_id: int | None = Query(None, description="Filtrar por libro"),
    estado: EstadoEjemplar | None = Query(None, description="Filtrar por estado"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    consulta = select(Ejemplar)
    if libro_id is not None:
        consulta = consulta.where(Ejemplar.libro_id == libro_id)
    if estado is not None:
        consulta = consulta.where(Ejemplar.estado == estado)
    return session.exec(consulta.offset(offset).limit(limit)).all()


@router.get(
    "/ejemplares/{ejemplar_id}",
    response_model=Ejemplar,
    status_code=status.HTTP_200_OK,
    summary="Obtener ejemplar por ID",
)
async def get_ejemplar(
    ejemplar_id: int,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    return obtener_ejemplar_o_404(session, ejemplar_id)


@router.post(
    "/ejemplares",
    response_model=Ejemplar,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una nueva copia física (ejemplar) de un libro",
)
async def create_ejemplar(
    datos: EjemplarCreate,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    libro = session.get(Libro, datos.libro_id)
    if not libro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El libro con ID {datos.libro_id} no existe",
        )
    if not libro.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pueden agregar ejemplares a un libro inactivo",
        )

    duplicado = session.exec(
        select(Ejemplar).where(
            Ejemplar.codigo_inventario == datos.codigo_inventario
        )
    ).first()
    if duplicado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un ejemplar con ese código de inventario",
        )

    ejemplar = Ejemplar(
        libro_id=datos.libro_id,
        codigo_inventario=datos.codigo_inventario,
        ubicacion=datos.ubicacion,
        estado=EstadoEjemplar.DISPONIBLE,
    )
    session.add(ejemplar)
    session.commit()
    session.refresh(ejemplar)
    return ejemplar


@router.patch(
    "/ejemplares/{ejemplar_id}",
    response_model=Ejemplar,
    status_code=status.HTTP_200_OK,
    summary="Actualizar ubicación o estado operativo de un ejemplar",
)
async def update_ejemplar(
    ejemplar_id: int,
    datos: EjemplarUpdate,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    ejemplar = obtener_ejemplar_o_404(session, ejemplar_id)
    datos_actualizados = datos.model_dump(exclude_unset=True)

    if ejemplar.estado == EstadoEjemplar.ELIMINADO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El ejemplar está eliminado y no puede modificarse",
        )

    if "estado" in datos_actualizados and datos_actualizados["estado"] is not None:
        nuevo_estado = datos_actualizados["estado"]
        if ejemplar.estado == EstadoEjemplar.PRESTADO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El ejemplar está prestado; registre primero su devolución antes de cambiar el estado",
            )
        if nuevo_estado == EstadoEjemplar.PRESTADO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El estado 'Prestado' solo puede asignarse mediante el registro de un préstamo",
            )
        if nuevo_estado == EstadoEjemplar.ELIMINADO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El estado 'Eliminado' solo puede asignarse mediante la baja del ejemplar",
            )

    for campo, valor in datos_actualizados.items():
        setattr(ejemplar, campo, valor)

    session.add(ejemplar)
    session.commit()
    session.refresh(ejemplar)
    return ejemplar


@router.delete(
    "/ejemplares/{ejemplar_id}",
    response_model=Ejemplar,
    status_code=status.HTTP_200_OK,
    summary="Marcar un ejemplar como Eliminado si no está prestado (solo Administrador)",
)
async def delete_ejemplar(
    ejemplar_id: int,
    session: SessionDeDependencia,
    token: Admin_Token_Dependencia,
):
    ejemplar = obtener_ejemplar_o_404(session, ejemplar_id)
    if ejemplar.estado == EstadoEjemplar.PRESTADO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar un ejemplar que se encuentra prestado",
        )
    ejemplar.estado = EstadoEjemplar.ELIMINADO
    session.add(ejemplar)
    session.commit()
    session.refresh(ejemplar)
    return ejemplar
