from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantScopedMixin, TimestampMixin


class Customer(db.Model, TenantScopedMixin, TimestampMixin):
    """
    Cliente final de uma loja específica. Criado/atualizado automaticamente
    a partir dos dados informados no checkout (nome + telefone), para permitir
    reconhecer clientes recorrentes e alimentar relatórios do lojista.
    """

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    phone = Column(String(20), nullable=True, index=True)

    tenant = relationship("Tenant", back_populates="customers")
    orders = relationship("Order", back_populates="customer")

    def __repr__(self):
        return f"<Customer {self.name}>"
