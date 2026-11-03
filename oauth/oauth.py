from datetime import datetime, timezone
from fastapi import APIRouter, Request, status, HTTPException
from sqlmodel import select
from config.session_dependencia import SessionDeDependencia
from config.security import create_access_token
from config.security_dependencia import OAuth2FormDeDependencia
from librerias.pwd import verify_password
from librerias.rate_limiter import login_rate_limiter
from models.usuario import Usuario
from models.auth import Token

router = APIRouter()


@router.post(
    "/oauth/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión y obtener token JWT",
)
async def login(
    request: Request,
    form_data: OAuth2FormDeDependencia,
    session: SessionDeDependencia,
):
    username = form_data.username
    client_key = login_rate_limiter.get_client_key(request, username)

    # 1. Comprobar si el usuario/IP se encuentra bloqueado (máx. 3 intentos fallidos)
    is_locked, remaining = login_rate_limiter.is_locked(client_key)
    if is_locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Demasiados intentos fallidos. Por favor, espere {remaining} "
                "segundos antes de volver a intentarlo."
            ),
            headers={"Retry-After": str(remaining)},
        )

    def _fallo_autenticacion(
        detail: str = "Credenciales inválidas",
        status_code: int = status.HTTP_401_UNAUTHORIZED,
    ):
        _, is_now_locked, wait_seconds = login_rate_limiter.record_failure(client_key)
        if is_now_locked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Ha alcanzado el límite de {login_rate_limiter.max_attempts} "
                    f"intentos fallidos. Debe esperar {wait_seconds} segundos."
                ),
                headers={"Retry-After": str(wait_seconds)},
            )
        raise HTTPException(
            status_code=status_code,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
            if status_code == status.HTTP_401_UNAUTHORIZED
            else None,
        )

    # 2. Búsqueda del usuario (Regla 5: no revelar si el usuario existe o no)
    consulta = select(Usuario).where(Usuario.username == username)
    usuario = session.exec(consulta).first()

    if not usuario or not verify_password(form_data.password, usuario.password_hash):
        _fallo_autenticacion("Credenciales inválidas", status.HTTP_401_UNAUTHORIZED)

    if not usuario.activo:
        _fallo_autenticacion(
            "El usuario se encuentra inactivo. Comuníquese con el administrador.",
            status.HTTP_403_FORBIDDEN,
        )

    # 3. Credenciales válidas: reiniciar contador de fallos y actualizar last_login
    login_rate_limiter.record_success(client_key)

    usuario.last_login = datetime.now(timezone.utc)
    session.add(usuario)
    session.commit()
    session.refresh(usuario)

    token, expires_in = create_access_token(
        data={
            "id": usuario.usuario_id,
            "username": usuario.username,
            "id_rol": usuario.rol_id,
        }
    )
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
    )
