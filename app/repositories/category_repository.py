from typing import Optional

from app.models import Category
from app.repositories.base_repository import TenantScopedRepository


class CategoryRepository(TenantScopedRepository[Category]):
    model = Category

    def list_ordered(self):
        return self._base_query().order_by(Category.display_order, Category.name).all()

    def get_by_slug(self, slug: str) -> Optional[Category]:
        return self._base_query().filter(Category.slug == slug).first()

    def count(self) -> int:
        return self._base_query().count()
