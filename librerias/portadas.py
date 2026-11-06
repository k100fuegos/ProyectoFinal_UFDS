import os
import re
import unicodedata
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_MEDIA = BASE_DIR / "media"
RUTA_PORTADAS = RUTA_MEDIA / "portadas"
RUTA_PORTADAS.mkdir(parents=True, exist_ok=True)

ZONA_HORARIA = ZoneInfo("America/El_Salvador")


def _entero_desde_entorno(nombre: str, defecto: int) -> int:
    try:
        return int(os.getenv(nombre, defecto))
    except (TypeError, ValueError):
        return defecto


# Configuración del procesamiento de portadas.
MAX_PORTADA_BYTES = _entero_desde_entorno("MAX_PORTADA_MB", 5) * 1024 * 1024
PORTADA_ANCHO = _entero_desde_entorno("PORTADA_ANCHO", 600)
PORTADA_ALTO = _entero_desde_entorno("PORTADA_ALTO", 900)


def _slug(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()
    return texto[:60] or "portada"


def _generar_nombre(nombre_original: str, titulo: str) -> str:
    nombre_original = (nombre_original or "").replace("\\", "/")
    base_original = Path(nombre_original).stem
    base = _slug(base_original or titulo)
    marca_tiempo = datetime.now(ZONA_HORARIA).strftime("%Y%m%d_%H%M%S")
    nombre_base = f"{base}_{marca_tiempo}"
    nombre = f"{nombre_base}.webp"
    contador = 1
    while (RUTA_PORTADAS / nombre).exists():
        contador += 1
        nombre = f"{nombre_base}_{contador}.webp"
    return nombre


def _preparar_imagen(contenido: bytes) -> Image.Image:
    try:
        imagen = Image.open(BytesIO(contenido))
        imagen.load()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo de portada no es una imagen válida",
        ) from exc

    imagen = ImageOps.exif_transpose(imagen)

    # WebP no admite el modo de paleta con transparencia de la misma forma que
    # PNG, así que se aplana sobre un fondo blanco antes de convertir a RGB.
    if imagen.mode in ("RGBA", "LA") or (
        imagen.mode == "P" and "transparency" in imagen.info
    ):
        imagen = imagen.convert("RGBA")
        fondo = Image.new("RGB", imagen.size, (255, 255, 255))
        fondo.paste(imagen, mask=imagen.getchannel("A"))
        imagen = fondo
    else:
        imagen = imagen.convert("RGB")

    # Reduce la imagen conservando la proporción y sin ampliarla si es pequeña.
    imagen.thumbnail(
        (PORTADA_ANCHO, PORTADA_ALTO),
        Image.Resampling.LANCZOS,
    )
    return imagen


async def guardar_portada(archivo: UploadFile, titulo: str) -> str:
    """Valida, redimensiona, convierte a WebP y guarda la portada.

    Devuelve únicamente el nombre del archivo, que es lo que se persiste en la
    base de datos. La imagen queda en ``media/portadas``.
    """
    contenido = await archivo.read(MAX_PORTADA_BYTES + 1)
    await archivo.close()

    if not contenido:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La portada está vacía",
        )

    if len(contenido) > MAX_PORTADA_BYTES:
        limite_mb = MAX_PORTADA_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"La portada no puede superar los {limite_mb} MB",
        )

    imagen = _preparar_imagen(contenido)
    nombre = _generar_nombre(archivo.filename or "", titulo)
    destino = RUTA_PORTADAS / nombre

    try:
        imagen.save(destino, format="WEBP", quality=85, method=6)
    except OSError as exc:
        destino.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo guardar la portada",
        ) from exc
    finally:
        imagen.close()

    return nombre


def eliminar_portada(nombre: str | None) -> None:
    """Elimina una portada anterior sin permitir rutas fuera de la carpeta."""
    if not nombre:
        return

    ruta = (RUTA_PORTADAS / os.path.basename(nombre)).resolve()
    if ruta.parent != RUTA_PORTADAS.resolve():
        return

    ruta.unlink(missing_ok=True)
