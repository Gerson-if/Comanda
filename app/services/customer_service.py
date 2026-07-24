"""
Consulta de clientes finais (Customer) pelo lojista — tela somente-leitura,
já que Customer é criado/atualizado automaticamente a partir do checkout
(ver app/models/customer.py), sem CRUD manual.
"""

from collections import namedtuple

from app.repositories.customer_repository import CustomerRepository

CustomerRow = namedtuple("CustomerRow", ["customer", "order_count", "total_spent_cents", "last_order_at"])


class CustomerService:
    def __init__(self, tenant):
        self.tenant = tenant
        self.repo = CustomerRepository(tenant.id)

    def paginated(self, page: int, per_page: int = 20):
        pagination = self.repo.paginated(page=page, per_page=per_page)
        stats = self.repo.order_stats_for([customer.id for customer in pagination.items])
        pagination.items = [
            CustomerRow(customer, *stats.get(customer.id, (0, 0, None)))
            for customer in pagination.items
        ]
        return pagination
