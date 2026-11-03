from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select
from config.session_dependencia import SessionDeDependencia
from config.security_dependencia import (
    Admin_Token_Dependencia,
    Biblio_Token_Dependencia,
)
from models.lector import Lector, LectorCreate, LectorUpdate
from models.prestamo import Prestamo
from models.enums import EstadoPrestamo

router = APIRouter()


def obtener_lector_o_404(session: SessionDeDependencia, lector_id: int) -> Lector:
    lector = session.get(Lector, lector_id)
    if not lector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lector no encontrado",
        )
    return lector


@router.get(
    "/lectores",
    response_model=list[Lector],
    status_code=status.HTTP_200_OK,
    summary="Listar lectores registrados",
)
async def get_lectores(
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
    activo: bool | None = Query(None, description="Filtrar por estado activo"),
    documento: str | None = Query(None, description="Filtrar por documento"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    consulta = select(Lector)
    if activo is not None:
        consulta = consulta.where(Lector.activo == activo)
    if documento:
        consulta = consulta.where(Lector.documento.contains(documento))
    return session.exec(consulta.offset(offset).limit(limit)).all()


@router.get(
    "/lectores/{lector_id}",
    response_model=Lector,
    status_code=status.HTTP_200_OK,
    summary="Obtener lector por ID",
)
async def get_lector(
    lector_id: int,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    return obtener_lector_o_404(session, lector_id)


@router.post(
    "/lectores",
    response_model=Lector,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo lector",
)
async def create_lector(
    datos: LectorCreate,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    if session.exec(select(Lector).where(Lector.documento == datos.documento)).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un lector con ese documento",
        )
    if session.exec(select(Lector).where(Lector.correo == datos.correo)).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un lector con ese correo electrónico",
        )
    lector = Lector(**datos.model_dump())
    session.add(lector)
    session.commit()
    session.refresh(lector)
    return lector


@router.put(
    "/lectores/{lector_id}",
    response_model=Lector,
    status_code=status.HTTP_200_OK,
    summary="Actualizar un lector",
)
async def update_lector(
    lector_id: int,
    datos: LectorUpdate,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    lector = obtener_lector_o_404(session, lector_id)
    datos_actualizados = datos.model_dump(exclude_unset=True)

    if "documento" in datos_actualizados and datos_actualizados["documento"]:
        if session.exec(
            select(Lector).where(
                Lector.documento == datos_actualizados["documento"],
                Lector.lector_id != lector_id,
            )
        ).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un lector con ese documento",
            )

    if "correo" in datos_actualizados and datos_actualizados["correo"]:
        if session.exec(
            select(Lector).where(
                Lector.correo == datos_actualizados["correo"],
                Lector.lector_id != lector_id,
            )
        ).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un lector con ese correo electrónico",
            )

    for campo, valor in datos_actualizados.items():
        setattr(lector, campo, valor)

    session.add(lector)
    session.commit()
    session.refresh(lector)
    return lector


@router.delete(
    "/lectores/{lector_id}",
    response_model=Lector,
    status_code=status.HTTP_200_OK,
    summary="Desactivar un lector si no tiene préstamos activos (solo Administrador)",
)
async def delete_lector(
    lector_id: int,
    session: SessionDeDependencia,
    token: Admin_Token_Dependencia,
):
    lector = obtener_lector_o_404(session, lector_id)
    prestamo_activo = session.exec(
        select(Prestamo).where(
            Prestamo.lector_id == lector_id,
            Prestamo.estado.in_([EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO]),  # type: ignore
        )
    ).first()
    if prestamo_activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede desactivar el lector porque posee préstamos activos pendientes de devolución",
        )
    lector.activo = False
    session.add(lector)
    session.commit()
    session.refresh(lector)
    return lector
