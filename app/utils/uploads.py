"""
Upload de imagens de produto.

Regras:
- Extensão permitida validada tanto pelo nome do arquivo quanto abrindo o
  arquivo de fato com Pillow (evita que um arquivo malicioso renomeado
  para .jpg passe pela validação só de extensão).
- Redimensiona para no máximo 1600px no maior lado (evita uploads
  gigantes consumindo disco/banda) e recomprime como JPEG otimizado.
- Cada imagem recebe um nome aleatório (uuid4) — nunca confiamos no nome
  original do arquivo enviado pelo navegador.
- Armazenada em `static/uploads/tenant_<tenant_id>/products/<product_id>/`
  — isolamento também a nível de sistema de arquivos, não só de banco.
"""

import os
import uuid

from flask import current_app
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

MAX_DIMENSION = 1600


class InvalidImageError(Exception):
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
    relative_subdir = os.path.join("products", str(product_id))
    return _save_validated_image(tenant_id, relative_subdir, file_storage)


def save_banner_image(tenant_id: int, file_storage) -> str:
    return _save_validated_image(tenant_id, "banners", file_storage)


def save_tenant_logo(tenant_id: int, file_storage) -> str:
    return _save_validated_image(tenant_id, "logo", file_storage)


def _save_validated_image(tenant_id: int, relative_subdir: str, file_storage) -> str:
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

    relative_dir = os.path.join("uploads", f"tenant_{tenant_id}", relative_subdir)
    absolute_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], f"tenant_{tenant_id}", relative_subdir)
    os.makedirs(absolute_dir, exist_ok=True)

    new_filename = f"{uuid.uuid4().hex}.jpg"
    absolute_path = os.path.join(absolute_dir, new_filename)
    image.save(absolute_path, format="JPEG", quality=85, optimize=True)

    return os.path.join(relative_dir, new_filename).replace(os.sep, "/")


def delete_product_image_file(relative_path: str) -> None:
    absolute_path = os.path.join(current_app.static_folder, relative_path)
    if os.path.isfile(absolute_path):
        os.remove(absolute_path)
