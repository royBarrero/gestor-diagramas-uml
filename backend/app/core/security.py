"""Utilidades de seguridad: hasheo y verificación de passwords."""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Genera el hash bcrypt de un password en texto plano."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifica un password en texto plano contra su hash. Se usará en el login."""
    return pwd_context.verify(plain_password, password_hash)
