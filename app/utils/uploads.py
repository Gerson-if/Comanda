"""
Upload de imagens (produto, banner, logo da loja, landing page).

Regras:
- Extensão permitida validada tanto pelo nome do arquivo quanto abrindo o
  arquivo de fato com Pillow (evita que um arquivo malicioso renomeado
  para .jpg passe pela validação só de extensão).
- Redimensiona para no máximo 1600px no maior lado (evita uploads
  gigantes consumindo disco/banda) e recomprime como JPEG otimizado.
- Cada imagem recebe um nome aleatório (uuid4) — nunca confiamos no nome
  original do arquivo enviado pelo navegador.
- Imagens de um tenant ficam em `static/uploads/tenant_<tenant_id>/...` —
  isolamento também a nível de sistema de arquivos, não só de banco.
  Imagens da plataforma (sem tenant, ex: landing page) ficam em
  `static/uploads/platform/...`.
"""

import os
import uuid

from flask import current_app
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

MAX_DIMENSION = 1600
MAX_VIDEO_BYTES = 25 * 1024 * 1024  # 25MB
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm"}


class InvalidImageError(Exception):
    pass


class InvalidVideoError(Exception):
    pass


def _allowed_extension(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]


def save_product_image(tenant_id: int, product_id: int, file_storage) -> str:
    """
    Recebe um FileStorage (do request.files), valida e salva.
    Retorna o caminho relativo (para gravar em ProductImage.file_path),
    ex: "uploads/tenant_3/products/17/8f1c...a2.jpg".
    """
    return _save_validated_image(os.path.join(f"tenant_{tenant_id}", "products", str(product_id)), file_storage)


def save_banner_image(tenant_id: int, file_storage) -> str:
    return _save_validated_image(os.path.join(f"tenant_{tenant_id}", "banners"), file_storage)


def save_tenant_logo(tenant_id: int, file_storage) -> str:
    return _save_validated_image(os.path.join(f"tenant_{tenant_id}", "logo"), file_storage)


def save_platform_image(subdir: str, file_storage) -> str:
    """Imagens da própria plataforma, sem tenant (ex: landing page,
    editada pelo Super Admin) — ver PlatformSettingsService.update_landing_content."""
    return _save_validated_image(os.path.join("platform", subdir), file_storage)


def save_platform_video(subdir: str, file_storage) -> str:
    """Vídeo de fundo do hero da landing page. Sem transcodificação (o
    projeto não tem ffmpeg/lib de vídeo) — só valida extensão e tamanho
    e salva com nome aleatório; o Super Admin deve enviar um arquivo já
    otimizado para web (a UI de upload deixa isso explícito). O
    <video loop muted autoplay> no template cuida do loop automático."""
    filename = secure_filename(file_storage.filename or "")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if not filename or ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise InvalidVideoError("Formato de vídeo não suportado. Use MP4 ou WEBM.")

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_VIDEO_BYTES:
        raise InvalidVideoError(f"Vídeo muito grande (máximo {MAX_VIDEO_BYTES // (1024 * 1024)}MB). Envie um arquivo já otimizado para web.")

    relative_dir = os.path.join("uploads", "platform", subdir)
    absolute_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "platform", subdir)
    os.makedirs(absolute_dir, exist_ok=True)

    new_filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(absolute_dir, new_filename))

    return os.path.join(relative_dir, new_filename).replace(os.sep, "/")


def _save_validated_image(relative_subdir: str, file_storage) -> str:
    """`relative_subdir`: caminho relativo dentro de UPLOAD_FOLDER onde a
    imagem deve ser salva, ex: "tenant_3/products/17" ou "platform/landing"."""
    filename = secure_filename(file_storage.filename or "")
    if not filename or not _allowed_extension(filename):
        raise InvalidImageError(
            "Formato de imagem não suportado. Use PNG, JPG, JPEG ou WEBP."
        )

    try:
        image = Image.open(file_storage.stream)
        image.verify()  # valida que é realmente uma imagem válida
        # verify() invalida o objeto para uso posterior — reabrir
        file_storage.stream.seek(0)
        image = Image.open(file_storage.stream)
        image = image.convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise InvalidImageError("Arquivo enviado não é uma imagem válida.")

    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))

    relative_dir = os.path.join("uploads", relative_subdir)
    absolute_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], relative_subdir)
    os.makedirs(absolute_dir, exist_ok=True)

    new_filename = f"{uuid.uuid4().hex}.jpg"
    absolute_path = os.path.join(absolute_dir, new_filename)
    image.save(absolute_path, format="JPEG", quality=85, optimize=True)

    return os.path.join(relative_dir, new_filename).replace(os.sep, "/")


def delete_product_image_file(relative_path: str) -> None:
    absolute_path = os.path.join(current_app.static_folder, relative_path)
    if os.path.isfile(absolute_path):
        os.remove(absolute_path)
