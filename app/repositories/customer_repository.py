from app.models import Customer
from app.repositories.base_repository import TenantScopedRepository


class CustomerRepository(TenantScopedRepository[Customer]):
    model = Customer

    def get_by_phone(self, phone: str):
        return self._base_query().filter(Customer.phone == phone).first()
