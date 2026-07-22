from app.models import Banner
from app.repositories.base_repository import TenantScopedRepository


class BannerRepository(TenantScopedRepository[Banner]):
    model = Banner

    def list_ordered(self):
        return self._base_query().order_by(Banner.display_order).all()

    def list_active_ordered(self):
        return self._base_query().filter(Banner.is_active.is_(True)).order_by(Banner.display_order).all()
