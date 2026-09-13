"""Dependencias compartidas de FastAPI para autenticación."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jwt import decode_access_token
from app.models.usuario import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la sesión.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credenciales_invalidas

    id_usuario = payload.get("sub")
    if id_usuario is None:
        raise credenciales_invalidas

    try:
        id_usuario = int(id_usuario)
    except ValueError:
        raise credenciales_invalidas

    usuario = db.query(Usuario).filter(Usuario.id == id_usuario).first()
    if usuario is None:
        raise credenciales_invalidas

    return usuario
