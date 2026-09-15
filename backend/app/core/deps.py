"""Dependencias compartidas de FastAPI para autenticación."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jwt import decode_access_token
from app.models.usuario import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def obtener_usuario_desde_token(token: str, db: Session) -> Usuario | None:
    """Igual que get_current_user pero sin lanzar HTTPException — para usar
    fuera de una dependencia de FastAPI (ej. el handshake de WebSocket)."""
    payload = decode_access_token(token)
    if payload is None:
        return None

    id_usuario = payload.get("sub")
    if id_usuario is None:
        return None

    try:
        id_usuario = int(id_usuario)
    except ValueError:
        return None

    return db.query(Usuario).filter(Usuario.id == id_usuario).first()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    usuario = obtener_usuario_desde_token(token, db)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar la sesión.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return usuario
