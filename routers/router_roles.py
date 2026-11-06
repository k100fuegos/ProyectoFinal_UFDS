from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select
from config.session_dependencia import SessionDeDependencia
from config.security_dependencia import (
    Admin_Token_Dependencia,
    Biblio_Token_Dependencia,
)
from models.rol import Rol, RolCreate, RolUpdate
from models.usuario import Usuario

router = APIRouter()


@router.get(
    "/roles",
    response_model=list[Rol],
    status_code=status.HTTP_200_OK,
    summary="Listar todos los roles",
)
async def get_roles(
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return session.exec(select(Rol).offset(offset).limit(limit)).all()


@router.get(
    "/roles/{rol_id}",
    response_model=Rol,
    status_code=status.HTTP_200_OK,
    summary="Obtener rol por ID",
)
async def get_rol(
    rol_id: int,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    rol = session.get(Rol, rol_id)
    if not rol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado",
        )
    return rol


@router.post(
    "/roles",
    response_model=Rol,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo rol (solo Administrador)",
)
async def create_rol(
    datos: RolCreate,
    session: SessionDeDependencia,
    token: Admin_Token_Dependencia,
):
    existente = session.exec(select(Rol).where(Rol.nombre == datos.nombre)).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un rol con ese nombre",
        )
    rol = Rol(**datos.model_dump())
    session.add(rol)
    session.commit()
    session.refresh(rol)
    return rol


@router.put(
    "/roles/{rol_id}",
    response_model=Rol,
    status_code=status.HTTP_200_OK,
    summary="Actualizar un rol (solo Administrador)",
)
async def update_rol(
    rol_id: int,
    datos: RolUpdate,
    session: SessionDeDependencia,
    token: Admin_Token_Dependencia,
):
    rol = session.get(Rol, rol_id)
    if not rol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado",
        )
    datos_actualizados = datos.model_dump(exclude_unset=True)
    if "nombre" in datos_actualizados and datos_actualizados["nombre"]:
        duplicado = session.exec(
            select(Rol).where(
                Rol.nombre == datos_actualizados["nombre"],
                Rol.rol_id != rol_id,
            )
        ).first()
        if duplicado:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un rol con ese nombre",
            )
    for campo, valor in datos_actualizados.items():
        setattr(rol, campo, valor)
    session.add(rol)
    session.commit()
    session.refresh(rol)
    return rol


@router.delete(
    "/roles/{rol_id}",
    status_code=status.HTTP_200_OK,
    summary="Eliminar un rol si no tiene usuarios asociados (solo Administrador)",
)
async def delete_rol(
    rol_id: int,
    session: SessionDeDependencia,
    token: Admin_Token_Dependencia,
):
    if rol_id in (1, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pueden eliminar los roles base del sistema (Administrador y Bibliotecario)",
        )
    rol = session.get(Rol, rol_id)
    if not rol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado",
        )
    usuario_asociado = session.exec(
        select(Usuario).where(Usuario.rol_id == rol_id)
    ).first()
    if usuario_asociado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar el rol porque tiene usuarios asociados",
        )
    session.delete(rol)
    session.commit()
    return {"message": "Rol eliminado correctamente", "rol_id": rol_id}
