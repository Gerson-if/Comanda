"""Geração de slugs únicos dentro do escopo de um tenant."""

from slugify import slugify


def generate_unique_slug(base_text: str, slug_exists_fn, current_id: int | None = None) -> str:
    """
    `slug_exists_fn(slug) -> Optional[obj]` deve consultar o repositório
    (já filtrado por tenant) e retornar o registro existente com aquele
    slug, ou None. Se o registro encontrado for o próprio `current_id`
    (edição), não conta como conflito.
    """
    base_slug = slugify(base_text)[:150] or "item"
    slug = base_slug
    suffix = 2

    while True:
        existing = slug_exists_fn(slug)
        if existing is None or existing.id == current_id:
            return slug
        slug = f"{base_slug}-{suffix}"
        suffix += 1
