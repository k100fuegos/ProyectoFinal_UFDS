from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlmodel import select
from config.session_dependencia import SessionDeDependencia
from config.security_dependencia import (
    Admin_Token_Dependencia,
    Biblio_Token_Dependencia,
)
from librerias.portadas import eliminar_portada, guardar_portada
from models.libro import Libro, LibroRead
from models.libro_autor import LibroAutor
from models.autor import Autor
from models.categoria import Categoria
from models.ejemplar import Ejemplar
from models.enums import EstadoEjemplar

router = APIRouter()


def obtener_libro_o_404(session: SessionDeDependencia, libro_id: int) -> Libro:
    libro = session.get(Libro, libro_id)
    if not libro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Libro no encontrado",
        )
    return libro


def construir_libro_read(session: SessionDeDependencia, libro: Libro) -> LibroRead:
    autores_links = session.exec(
        select(LibroAutor).where(LibroAutor.libro_id == libro.libro_id)
    ).all()
    autores_ids = [link.autor_id for link in autores_links]

    disponibles = session.exec(
        select(Ejemplar).where(
            Ejemplar.libro_id == libro.libro_id,
            Ejemplar.estado == EstadoEjemplar.DISPONIBLE,
        )
    ).all()

    return LibroRead(
        libro_id=libro.libro_id,  # type: ignore
        isbn=libro.isbn,
        titulo=libro.titulo,
        editorial=libro.editorial,
        anio_publicacion=libro.anio_publicacion,
        categoria_id=libro.categoria_id,
        activo=libro.activo,
        portada=libro.portada,
        autores_ids=autores_ids,
        ejemplares_disponibles=len(disponibles),
    )


def validar_categoria_y_autores(
    session: SessionDeDependencia,
    categoria_id: int | None,
    autores_ids: list[int] | None,
) -> None:
    if categoria_id is not None and not session.get(Categoria, categoria_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La categoría con ID {categoria_id} no existe",
        )
    if autores_ids is not None:
        if len(autores_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El libro debe tener al menos un autor asociado",
            )
        for autor_id in set(autores_ids):
            if not session.get(Autor, autor_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"El autor con ID {autor_id} no existe",
                )


@router.get(
    "/libros",
    response_model=list[LibroRead],
    status_code=status.HTTP_200_OK,
    summary="Listar catálogo de libros con disponibilidad y autores",
)
async def get_libros(
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
    categoria_id: int | None = Query(None, description="Filtrar por categoría"),
    autor_id: int | None = Query(None, description="Filtrar por autor"),
    activo: bool | None = Query(None, description="Filtrar por estado activo"),
    titulo: str | None = Query(None, description="Buscar por título"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    consulta = select(Libro)
    if categoria_id is not None:
        consulta = consulta.where(Libro.categoria_id == categoria_id)
    if activo is not None:
        consulta = consulta.where(Libro.activo == activo)
    if titulo:
        consulta = consulta.where(Libro.titulo.contains(titulo))
    if autor_id is not None:
        libros_del_autor = session.exec(
            select(LibroAutor.libro_id).where(LibroAutor.autor_id == autor_id)
        ).all()
        if not libros_del_autor:
            return []
        consulta = consulta.where(Libro.libro_id.in_(libros_del_autor))  # type: ignore

    libros = session.exec(consulta.offset(offset).limit(limit)).all()
    return [construir_libro_read(session, libro) for libro in libros]


@router.get(
    "/libros/{libro_id}",
    response_model=LibroRead,
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de un libro por ID",
)
async def get_libro(
    libro_id: int,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
):
    libro = obtener_libro_o_404(session, libro_id)
    return construir_libro_read(session, libro)


@router.post(
    "/libros",
    response_model=LibroRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo libro con su categoría, autores y portada",
)
async def create_libro(
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
    isbn: str = Form(..., min_length=10, max_length=17),
    titulo: str = Form(..., min_length=1, max_length=255),
    editorial: str | None = Form(None, max_length=150),
    anio_publicacion: int | None = Form(None, ge=1000, le=2100),
    categoria_id: int = Form(...),
    autores_ids: list[int] = Form(
        ...,
        description="ID de cada autor; repita el campo para varios autores",
    ),
    portada: UploadFile | None = File(
        None,
        description="Imagen de portada (JPG, PNG, WebP, etc.). Se convierte a WebP.",
    ),
):
    if session.exec(select(Libro).where(Libro.isbn == isbn)).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un libro registrado con ese ISBN",
        )

    validar_categoria_y_autores(session, categoria_id, autores_ids)

    nombre_portada = None
    if portada is not None and portada.filename:
        nombre_portada = await guardar_portada(portada, titulo)

    libro = Libro(
        isbn=isbn,
        titulo=titulo,
        editorial=editorial,
        anio_publicacion=anio_publicacion,
        categoria_id=categoria_id,
        portada=nombre_portada,
        activo=True,
    )

    try:
        session.add(libro)
        session.flush()

        for autor_id in dict.fromkeys(autores_ids):
            session.add(
                LibroAutor(
                    libro_id=libro.libro_id,  # type: ignore
                    autor_id=autor_id,
                )
            )

        session.commit()
    except Exception:
        session.rollback()
        eliminar_portada(nombre_portada)
        raise

    session.refresh(libro)
    return construir_libro_read(session, libro)


@router.put(
    "/libros/{libro_id}",
    response_model=LibroRead,
    status_code=status.HTTP_200_OK,
    summary="Actualizar los datos, autores y portada de un libro",
)
async def update_libro(
    libro_id: int,
    session: SessionDeDependencia,
    token: Biblio_Token_Dependencia,
    isbn: str | None = Form(None, min_length=10, max_length=17),
    titulo: str | None = Form(None, min_length=1, max_length=255),
    editorial: str | None = Form(None, max_length=150),
    anio_publicacion: int | None = Form(None, ge=1000, le=2100),
    categoria_id: int | None = Form(None),
    autores_ids: list[int] | None = Form(
        None,
        description="ID de cada autor; omita el campo para no cambiar los autores",
    ),
    activo: bool | None = Form(None),
    portada: UploadFile | None = File(
        None,
        description="Nueva portada. Si se envía, reemplaza la anterior.",
    ),
):
    libro = obtener_libro_o_404(session, libro_id)

    if isbn is not None:
        duplicado = session.exec(
            select(Libro).where(
                Libro.isbn == isbn,
                Libro.libro_id != libro_id,
            )
        ).first()
        if duplicado:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe otro libro con ese ISBN",
            )

    validar_categoria_y_autores(session, categoria_id, autores_ids)

    portada_anterior = libro.portada
    nombre_portada = None
    if portada is not None and portada.filename:
        nombre_portada = await guardar_portada(portada, titulo or libro.titulo)

    try:
        if isbn is not None:
            libro.isbn = isbn
        if titulo is not None:
            libro.titulo = titulo
        if editorial is not None:
            libro.editorial = editorial or None
        if anio_publicacion is not None:
            libro.anio_publicacion = anio_publicacion
        if categoria_id is not None:
            libro.categoria_id = categoria_id
        if activo is not None:
            libro.activo = activo
        if nombre_portada is not None:
            libro.portada = nombre_portada

        if autores_ids is not None:
            enlaces_actuales = session.exec(
                select(LibroAutor).where(LibroAutor.libro_id == libro_id)
            ).all()
            for enlace in enlaces_actuales:
                session.delete(enlace)
            session.flush()
            for autor_id in dict.fromkeys(autores_ids):
                session.add(LibroAutor(libro_id=libro_id, autor_id=autor_id))

        session.add(libro)
        session.commit()
    except Exception:
        session.rollback()
        eliminar_portada(nombre_portada)
        raise

    session.refresh(libro)
    if (
        nombre_portada is not None
        and portada_anterior
        and portada_anterior != nombre_portada
    ):
        eliminar_portada(portada_anterior)

    return construir_libro_read(session, libro)


@router.delete(
    "/libros/{libro_id}",
    response_model=LibroRead,
    status_code=status.HTTP_200_OK,
    summary="Dar de baja lógica un libro si no tiene ejemplares prestados (solo Administrador)",
)
async def delete_libro(
    libro_id: int,
    session: SessionDeDependencia,
    token: Admin_Token_Dependencia,
):
    libro = obtener_libro_o_404(session, libro_id)

    ejemplar_prestado = session.exec(
        select(Ejemplar).where(
            Ejemplar.libro_id == libro_id,
            Ejemplar.estado == EstadoEjemplar.PRESTADO,
        )
    ).first()
    if ejemplar_prestado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede dar de baja el libro porque tiene ejemplares actualmente prestados",
        )

    libro.activo = False
    session.add(libro)
    session.commit()
    session.refresh(libro)
    return construir_libro_read(session, libro)
