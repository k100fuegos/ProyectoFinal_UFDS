import base64
import hashlib
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def verify_django_pbkdf2(plain_password: str, hashed_password: str) -> bool:
    """Valida contraseñas con el formato estándar de Django (pbkdf2_sha256)."""
    try:
        parts = hashed_password.split("$")
        if len(parts) == 4 and parts[0] == "pbkdf2_sha256":
            iterations = int(parts[1])
            salt = parts[2]
            expected_hash = parts[3]
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt.encode("ascii"),
                iterations,
            )
            return base64.b64encode(dk).decode("ascii") == expected_hash
    except Exception:
        pass
    return False


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica contraseñas hasheadas con Argon2id (pwdlib) o PBKDF2."""
    if not hashed_password:
        return False

    if hashed_password.startswith("pbkdf2_sha256$"):
        return verify_django_pbkdf2(plain_password, hashed_password)

    clean_hash = hashed_password
    if hashed_password.startswith("argon2$"):
        clean_hash = hashed_password[6:]

    try:
        return password_hash.verify(plain_password, clean_hash)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Genera el hash seguro de la contraseña con Argon2id."""
    standard_hash = password_hash.hash(password)
    return f"argon2{standard_hash}"
