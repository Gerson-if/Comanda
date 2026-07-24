from sqlalchemy import Boolean, Column, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantScopedMixin, TimestampMixin

# Ícones disponíveis para uma categoria no cardápio público (ver
# iconMap em app/static/js/store_menu.js). "other" é o padrão/fallback
# para categorias que não se encaixam nos ícones temáticos.
CATEGORY_ICON_CHOICES = [
    ("other", "Outro"),
    ("burger", "Lanches"),
    ("pizza", "Pizzas"),
    ("drink", "Bebidas"),
    ("dessert", "Sobremesas"),
    ("combo", "Combos"),
]
CATEGORY_ICON_KEYS = [key for key, _ in CATEGORY_ICON_CHOICES]


class Category(db.Model, TenantScopedMixin, TimestampMixin):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(120), nullable=False)
    icon = Column(String(20), nullable=False, default="other", server_default="other")
    # Ícone próprio enviado pelo lojista (PNG com transparência, ver
    # app/utils/uploads.py:save_category_icon) — quando presente, tem
    # prioridade sobre `icon` na renderização pública (mesmo padrão de
    # hero_image/hero_video na landing page: upload > escolha padrão).
    icon_image_path = Column(String(255), nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)

    tenant = relationship("Tenant", back_populates="categories")
    products = relationship("Product", back_populates="category")

    __table_args__ = (
        # O slug só precisa ser único DENTRO da mesma loja, não globalmente.
        UniqueConstraint("tenant_id", "slug", name="uq_category_tenant_slug"),
        # `icon` não tem CHECK CONSTRAINT no banco — a validação do valor
        # (deve ser uma das CATEGORY_ICON_KEYS) é feita no formulário
        # (CategoryForm), que já restringe a um SelectField fechado.
    )

    def __repr__(self):
        return f"<Category {self.name} (tenant={self.tenant_id})>"
