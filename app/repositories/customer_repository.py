from app.models import Customer, Order
from app.repositories.base_repository import TenantScopedRepository


class CustomerRepository(TenantScopedRepository[Customer]):
    model = Customer

    def get_by_phone(self, phone: str):
        return self._base_query().filter(Customer.phone == phone).first()

    def paginated(self, page: int, per_page: int = 20):
        from sqlalchemy import select

        from app.extensions import db

        stmt = (
            select(Customer)
            .where(Customer.tenant_id == self.tenant_id)
            .order_by(Customer.created_at.desc())
        )
        return db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    def order_stats_for(self, customer_ids: list[int]) -> dict:
        """
        {customer_id: (order_count, total_spent_cents, last_order_at)} para
        os ids informados — uma query agregada (mesmo estilo de
        app/services/report_service.py) em vez de uma por cliente, pra
        evitar N+1 ao montar a tabela de clientes paginada.
        """
        if not customer_ids:
            return {}

        from sqlalchemy import func

        from app.extensions import db

        rows = (
            db.session.query(
                Order.customer_id,
                func.count(Order.id),
                func.coalesce(func.sum(Order.total_cents), 0),
                func.max(Order.created_at),
            )
            .filter(Order.tenant_id == self.tenant_id, Order.customer_id.in_(customer_ids))
            .group_by(Order.customer_id)
            .all()
        )
        return {customer_id: (int(count), int(total), last) for customer_id, count, total, last in rows}
