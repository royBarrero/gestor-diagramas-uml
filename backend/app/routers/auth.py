"""Router de autenticación: registro de usuarios."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.jwt import create_access_token
from app.core.security import hash_password, verify_password
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, Token
from app.schemas.usuario import UsuarioOut, UsuarioRegistro

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/registro", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def registrar_usuario(datos: UsuarioRegistro, db: Session = Depends(get_db)):
    usuario_existente = db.query(Usuario).filter(Usuario.email == datos.email).first()
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario registrado con ese email.",
        )

    nuevo_usuario = Usuario(
        nombre=datos.nombre,
        email=datos.email,
        password_hash=hash_password(datos.password),
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    return nuevo_usuario


@router.post("/login", response_model=Token)
def login(datos: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == datos.email).first()

    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email o contraseña incorrectos.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not usuario or not verify_password(datos.password, usuario.password_hash):
        raise credenciales_invalidas

    access_token = create_access_token(data={"sub": str(usuario.id), "email": usuario.email})
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UsuarioOut)
def obtener_usuario_actual(usuario_actual: Usuario = Depends(get_current_user)):
    return usuario_actual
