from typing import Optional

from app.models import Product
from app.repositories.base_repository import TenantScopedRepository


class ProductRepository(TenantScopedRepository[Product]):
    model = Product

    def list_ordered(self, category_id: Optional[int] = None):
        query = self._base_query()
        if category_id is not None:
            query = query.filter(Product.category_id == category_id)
        return query.order_by(Product.display_order, Product.name).all()

    def paginated(self, page: int, per_page: int = 12, category_id: Optional[int] = None):
        from sqlalchemy import select

        from app.extensions import db

        stmt = select(Product).where(Product.tenant_id == self.tenant_id)
        if category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)
        stmt = stmt.order_by(Product.display_order, Product.name)
        return db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    def get_by_slug(self, slug: str) -> Optional[Product]:
        return self._base_query().filter(Product.slug == slug).first()

    def count(self) -> int:
        return self._base_query().count()
