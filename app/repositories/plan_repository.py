from app.models import Plan
from app.repositories.base_repository import BaseRepository


class PlanRepository(BaseRepository[Plan]):
    model = Plan

    def get_by_slug(self, slug: str):
        return self.model.query.filter_by(slug=slug).first()

    def list_ordered(self):
        return self.model.query.order_by(Plan.price_cents).all()
