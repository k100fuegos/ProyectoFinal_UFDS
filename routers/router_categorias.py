from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select
from config.session_dependencia import SessionDeDependencia
from config.security_dependencia import (
    Admin_Token_Dependencia,
    Biblio_Token_Dependencia,
)
from models.categoria import Categoria, CategoriaCreate, CategoriaUpdate
from models.libro import Libro

router = APIRouter()


def obtener_categoria_o_404(
    session: SessionDeDependencia, categoria_id: int
) -> Categoria:
    categoria = session.get(Categoria, categoria_id)
    if not categoria:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoría no encontrada",
        )
    return categoria


def validar_nombre_unico(
    session: SessionDeDependencia,
    nombre: str,
    categoria_id: int | None = None,
) -> None:
    consulta = select(Categoria).where(Categoria.nombre == nombre)
    if categoria_id is not None:
        consulta = consulta.where(Categoria.categoria_id != categoria_id)
    if session.exec(consulta).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una categoría con ese nombre",
        )


@router.get(
    "/categorias",
    response_model=list[Categoria],
    status_code=status.HTTP_200_OK,
    summary="Listar categorías bibliográficas",
)
async def get_categorias(
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return session.exec(select(Categoria).offset(offset).limit(limit)).all()


@router.get(
    "/categorias/{categoria_id}",
    response_model=Categoria,
    status_code=status.HTTP_200_OK,
    summary="Obtener categoría por ID",
)
async def get_categoria(
    categoria_id: int,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    return obtener_categoria_o_404(session, categoria_id)


@router.post(
    "/categorias",
    response_model=Categoria,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva categoría",
)
async def create_categoria(
    datos: CategoriaCreate,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    validar_nombre_unico(session, datos.nombre)
    categoria = Categoria(**datos.model_dump())
    session.add(categoria)
    session.commit()
    session.refresh(categoria)
    return categoria


@router.put(
    "/categorias/{categoria_id}",
    response_model=Categoria,
    status_code=status.HTTP_200_OK,
    summary="Actualizar categoría",
)
async def update_categoria(
    categoria_id: int,
    datos: CategoriaUpdate,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    categoria = obtener_categoria_o_404(session, categoria_id)
    datos_actualizados = datos.model_dump(exclude_unset=True)

    if "nombre" in datos_actualizados and datos_actualizados["nombre"]:
        validar_nombre_unico(session, datos_actualizados["nombre"], categoria_id)

    for campo, valor in datos_actualizados.items():
        setattr(categoria, campo, valor)

    session.add(categoria)
    session.commit()
    session.refresh(categoria)
    return categoria


@router.delete(
    "/categorias/{categoria_id}",
    status_code=status.HTTP_200_OK,
    summary="Eliminar categoría si no tiene libros asociados (solo Administrador)",
)
async def delete_categoria(
    categoria_id: int,
    session: SessionDeDependencia,
    token: Admin_Token_Dependencia,
):
    categoria = obtener_categoria_o_404(session, categoria_id)
    libro_asociado = session.exec(
        select(Libro).where(Libro.categoria_id == categoria_id)
    ).first()
    if libro_asociado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar la categoría porque tiene libros asociados",
        )
    session.delete(categoria)
    session.commit()
    return {
        "message": "Categoría eliminada correctamente",
        "categoria_id": categoria_id,
    }
