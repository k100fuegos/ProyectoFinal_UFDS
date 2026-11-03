from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select
from config.session_dependencia import SessionDeDependencia
from config.security_dependencia import Admin_Token_Dependencia, Token_Dependencia
from librerias.pwd import get_password_hash
from models.usuario import Usuario, UsuarioCreate, UsuarioUpdate, UsuarioRead
from models.rol import Rol

router = APIRouter()


def validar_rol_existente(session: SessionDeDependencia, rol_id: int) -> None:
    if not session.get(Rol, rol_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El rol especificado no existe",
        )


@router.get(
    "/usuarios",
    response_model=list[UsuarioRead],
    status_code=status.HTTP_200_OK,
    summary="Listar usuarios del personal (solo Administrador)",
)
async def get_usuarios(
    session: SessionDeDependencia,
    token: Admin_Token_Dependencia,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return session.exec(select(Usuario).offset(offset).limit(limit)).all()


@router.get(
    "/usuarios/me",
    response_model=UsuarioRead,
    status_code=status.HTTP_200_OK,
    summary="Obtener perfil del usuario autenticado",
)
async def get_mi_usuario(
    session: SessionDeDependencia,
    token: Token_Dependencia,
):
    usuario_id = token.get("id")
    usuario = session.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    return usuario


@router.get(
    "/usuarios/{id}",
    response_model=UsuarioRead,
    status_code=status.HTTP_200_OK,
    summary="Obtener usuario por ID (solo Administrador)",
)
async def get_usuario(
    id: int,
    session: SessionDeDependencia,
    token: Admin_Token_Dependencia,
):
    usuario = session.get(Usuario, id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    return usuario


@router.post(
    "/usuarios",
    response_model=UsuarioRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nuevo usuario del personal (solo Administrador)",
)
async def create_usuario(
    datos: UsuarioCreate,
    session: SessionDeDependencia,
    token: Admin_Token_Dependencia,
):
    if session.exec(select(Usuario).where(Usuario.username == datos.username)).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nombre de usuario ya está en uso",
        )
    if session.exec(select(Usuario).where(Usuario.correo == datos.correo)).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo electrónico ya está registrado",
        )

    validar_rol_existente(session, datos.rol_id)

    usuario = Usuario(
        nombre=datos.nombre,
        username=datos.username,
        correo=datos.correo,
        activo=datos.activo,
        rol_id=datos.rol_id,
        password_hash=get_password_hash(datos.password),
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario


@router.put(
    "/usuarios/{id}",
    response_model=UsuarioRead,
    status_code=status.HTTP_200_OK,
    summary="Actualizar usuario (solo Administrador)",
)
async def update_usuario(
    id: int,
    datos: UsuarioUpdate,
    session: SessionDeDependencia,
    token: Admin_Token_Dependencia,
):
    usuario = session.get(Usuario, id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    if token.get("id") == id and datos.activo is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propio usuario",
        )

    if datos.username and session.exec(
        select(Usuario).where(
            Usuario.username == datos.username,
            Usuario.usuario_id != id,
        )
    ).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nombre de usuario ya está en uso",
        )

    if datos.correo and session.exec(
        select(Usuario).where(
            Usuario.correo == datos.correo,
            Usuario.usuario_id != id,
        )
    ).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo electrónico ya está registrado",
        )

    if datos.rol_id is not None:
        validar_rol_existente(session, datos.rol_id)

    datos_actualizados = datos.model_dump(exclude_unset=True)
    if "password" in datos_actualizados:
        nueva_pass = datos_actualizados.pop("password")
        if nueva_pass:
            usuario.password_hash = get_password_hash(nueva_pass)

    for campo, valor in datos_actualizados.items():
        setattr(usuario, campo, valor)

    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario


@router.patch(
    "/usuarios/{id}/desactivar",
    response_model=UsuarioRead,
    status_code=status.HTTP_200_OK,
    summary="Desactivar usuario mediante baja lógica (solo Administrador)",
)
async def desactivar_usuario(
    id: int,
    session: SessionDeDependencia,
    token: Admin_Token_Dependencia,
):
    if token.get("id") == id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propio usuario",
        )
    usuario = session.get(Usuario, id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    usuario.activo = False
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario
