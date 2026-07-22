from sqlalchemy import Boolean, Column, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantScopedMixin, TimestampMixin


class Category(db.Model, TenantScopedMixin, TimestampMixin):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(120), nullable=False)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)

    tenant = relationship("Tenant", back_populates="categories")
    products = relationship("Product", back_populates="category")

    __table_args__ = (
        # O slug só precisa ser único DENTRO da mesma loja, não globalmente.
        UniqueConstraint("tenant_id", "slug", name="uq_category_tenant_slug"),
    )

    def __repr__(self):
        return f"<Category {self.name} (tenant={self.tenant_id})>"
