from app.models import Invoice, Subscription
from app.repositories.base_repository import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    model = Subscription

    def get_active_for_tenant(self, tenant_id: int):
        return (
            self.model.query.filter_by(tenant_id=tenant_id)
            .order_by(Subscription.current_period_end.desc())
            .first()
        )


class InvoiceRepository(BaseRepository[Invoice]):
    model = Invoice

    def list_for_tenant(self, tenant_id: int):
        return (
            self.model.query.filter_by(tenant_id=tenant_id)
            .order_by(Invoice.due_date.desc())
            .all()
        )
