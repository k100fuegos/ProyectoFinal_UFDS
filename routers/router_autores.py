from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select
from config.session_dependencia import SessionDeDependencia
from config.security_dependencia import (
    Admin_Token_Dependencia,
    Biblio_Token_Dependencia,
)
from models.autor import Autor, AutorCreate, AutorUpdate
from models.libro_autor import LibroAutor

router = APIRouter()


def obtener_autor_o_404(session: SessionDeDependencia, autor_id: int) -> Autor:
    autor = session.get(Autor, autor_id)
    if not autor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Autor no encontrado",
        )
    return autor


@router.get(
    "/autores",
    response_model=list[Autor],
    status_code=status.HTTP_200_OK,
    summary="Listar autores",
)
async def get_autores(
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return session.exec(select(Autor).offset(offset).limit(limit)).all()


@router.get(
    "/autores/{autor_id}",
    response_model=Autor,
    status_code=status.HTTP_200_OK,
    summary="Obtener autor por ID",
)
async def get_autor(
    autor_id: int,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    return obtener_autor_o_404(session, autor_id)


@router.post(
    "/autores",
    response_model=Autor,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo autor",
)
async def create_autor(
    datos: AutorCreate,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    autor = Autor(**datos.model_dump())
    session.add(autor)
    session.commit()
    session.refresh(autor)
    return autor


@router.put(
    "/autores/{autor_id}",
    response_model=Autor,
    status_code=status.HTTP_200_OK,
    summary="Actualizar un autor",
)
async def update_autor(
    autor_id: int,
    datos: AutorUpdate,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    autor = obtener_autor_o_404(session, autor_id)
    datos_actualizados = datos.model_dump(exclude_unset=True)
    for campo, valor in datos_actualizados.items():
        setattr(autor, campo, valor)
    session.add(autor)
    session.commit()
    session.refresh(autor)
    return autor


@router.delete(
    "/autores/{autor_id}",
    status_code=status.HTTP_200_OK,
    summary="Eliminar un autor si no tiene libros asociados (solo Administrador)",
)
async def delete_autor(
    autor_id: int,
    session: SessionDeDependencia,
    token: Admin_Token_Dependencia,
):
    autor = obtener_autor_o_404(session, autor_id)
    asociacion = session.exec(
        select(LibroAutor).where(LibroAutor.autor_id == autor_id)
    ).first()
    if asociacion:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar el autor porque tiene libros asociados",
        )
    session.delete(autor)
    session.commit()
    return {"message": "Autor eliminado correctamente", "autor_id": autor_id}
