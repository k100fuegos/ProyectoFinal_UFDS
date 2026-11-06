from datetime import datetime, timedelta, timezone
from typing import Optional
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session
import jwt
import os

from config.db import get_session
from models.usuario import Usuario

load_dotenv()

SECRET_KEY_TOKEN = (os.getenv("SECRET_KEY_TOKEN") or "").strip()
if not SECRET_KEY_TOKEN:
    raise RuntimeError(
        "SECRET_KEY_TOKEN no está definido. Configure la variable de entorno "
        "o el archivo .env antes de iniciar la API."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="oauth/login")

ROLES_OPERATIVOS = {1, 2}


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, int]:
    """Genera un token JWT firmado con tiempo de expiración y devuelve (token, expires_in_seconds)."""
    to_encode = data.copy()
    delta = expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + delta
    to_encode.update({"exp": expire})
    token = jwt.encode(
        payload=to_encode,
        key=SECRET_KEY_TOKEN,
        algorithm=ALGORITHM,
    )
    return token, int(delta.total_seconds())


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(
        token,
        key=SECRET_KEY_TOKEN,
        algorithms=[ALGORITHM],
    )
    return payload


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> dict:
    credencial_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado o token inválido",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        id_usuario: Optional[int] = payload.get("id")

        if not isinstance(id_usuario, int):
            raise credencial_exception

        # El token identifica al usuario, pero el estado y el rol se consultan
        # siempre en la base de datos para que una desactivación o un cambio
        # de rol tengan efecto inmediato sin esperar a que expire el token.
        usuario = session.get(Usuario, id_usuario)
        if not usuario:
            raise credencial_exception
        if not usuario.activo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario inactivo o no disponible",
            )

        return {
            "id": usuario.usuario_id,
            "username": usuario.username,
            "id_rol": usuario.rol_id,
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise credencial_exception


def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Restringe la operación exclusivamente al rol Administrador (rol_id = 1)."""
    if current_user.get("id_rol") != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos de administrador para realizar esta operación",
        )
    return current_user


def verificar_permisos_bibliotecario(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Autoriza operaciones del personal bibliotecario (Administrador = 1 o Bibliotecario = 2)."""
    if current_user.get("id_rol") not in ROLES_OPERATIVOS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para realizar esta operación",
        )
    return current_user
