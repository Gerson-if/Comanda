from app.models import ProductImage
from app.repositories.base_repository import TenantScopedRepository


class ProductImageRepository(TenantScopedRepository[ProductImage]):
    model = ProductImage

    def list_for_product(self, product_id: int):
        return (
            self._base_query()
            .filter(ProductImage.product_id == product_id)
            .order_by(ProductImage.display_order)
            .all()
        )

    def clear_primary_flag(self, product_id: int) -> None:
        self._base_query().filter(ProductImage.product_id == product_id).update(
            {"is_primary": False}
        )
