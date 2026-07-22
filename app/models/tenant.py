"""
Tenant = a "loja" (lojista/cliente) dentro da plataforma SaaS.
Plan   = plano de assinatura oferecido pelo Super Administrador.

Todo dado de domínio de uma loja (produtos, categorias, pedidos, clientes,
imagens) referencia tenants.id. O isolamento entre lojistas acontece
filtrando SEMPRE por tenant_id nas queries (ver base_repository.py).
"""

import enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin, str_enum


class TenantStatus(str, enum.Enum):
    TRIAL = "trial"                    # período de teste
    ACTIVE = "active"                  # conta ativa e em dia
    SUSPENDED = "suspended"            # suspensa manualmente pelo Super Admin
    BLOCKED_PAYMENT = "blocked_payment"  # bloqueada por inadimplência
    CANCELED = "canceled"              # cancelada definitivamente


class BillingCycle(str, enum.Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class Plan(db.Model, TimestampMixin):
    """Plano de assinatura (ex: Básico, Pro, Enterprise)."""

    __tablename__ = "plans"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    slug = Column(String(80), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    price_cents = Column(Integer, nullable=False, default=0)
    billing_cycle = Column(
        str_enum(BillingCycle, "billing_cycle"), nullable=False,
        default=BillingCycle.MONTHLY,
    )

    max_products = Column(Integer, nullable=True)   # null = ilimitado
    max_categories = Column(Integer, nullable=True)  # null = ilimitado
    max_images_per_product = Column(Integer, nullable=False, default=5)

    is_active = Column(Boolean, nullable=False, default=True)  # plano disponível p/ contratação

    tenants = relationship("Tenant", back_populates="plan")

    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="ck_plan_price_non_negative"),
    )

    def __repr__(self):
        return f"<Plan {self.slug}>"


class Tenant(db.Model, TimestampMixin):
    """Uma loja/lojista dentro da plataforma."""

    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True)

    # Identificação
    name = Column(String(150), nullable=False)          # nome fantasia (exibido no cardápio)
    legal_name = Column(String(150), nullable=True)      # razão social (opcional)
    document = Column(String(20), nullable=True)         # CPF/CNPJ (opcional)
    slug = Column(String(150), nullable=False, unique=True, index=True)  # usado na URL pública

    # Contato
    email = Column(String(180), nullable=False, unique=True, index=True)
    phone = Column(String(20), nullable=True)
    whatsapp_number = Column(String(20), nullable=True)  # número completo com DDI+DDD p/ wa.me

    # Plano / assinatura
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=True)
    plan = relationship("Plan", back_populates="tenants")

    # Status da conta (controlado pelo Super Admin)
    status = Column(
        str_enum(TenantStatus, "tenant_status"), nullable=False,
        default=TenantStatus.TRIAL, index=True,
    )
    blocked_reason = Column(String(255), nullable=True)
    blocked_at = Column(db.DateTime(timezone=True), nullable=True)

    # Configurações do cardápio / operação
    delivery_enabled = Column(Boolean, nullable=False, default=False)
    delivery_fee_cents = Column(Integer, nullable=True)
    free_delivery_above_cents = Column(Integer, nullable=True)  # entrega grátis acima deste valor (opcional)
    min_order_cents = Column(Integer, nullable=True)
    pickup_enabled = Column(Boolean, nullable=False, default=True)

    # Aparência (tema do cardápio público)
    logo_path = Column(String(255), nullable=True)
    banner_path = Column(String(255), nullable=True)
    theme_settings = Column(JSON, nullable=True)  # cores, fontes etc.

    # Integração de cobrança (Asaas) — preenchido automaticamente na
    # primeira cobrança gerada para este tenant. Ver
    # app/services/payment_gateway/.
    asaas_customer_id = Column(String(60), nullable=True)

    # Horário de funcionamento (JSON simples: {"mon": ["18:00","23:00"], ...})
    opening_hours = Column(JSON, nullable=True)

    # Relacionamentos (definidos nos respectivos models via back_populates)
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="tenant", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="tenant", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="tenant", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="tenant", cascade="all, delete-orphan")
    banners = relationship("Banner", back_populates="tenant", cascade="all, delete-orphan", order_by="Banner.display_order")
    subscriptions = relationship("Subscription", back_populates="tenant", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="tenant", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("slug", name="uq_tenant_slug"),
    )

    @property
    def is_active_account(self) -> bool:
        return self.status in (TenantStatus.TRIAL, TenantStatus.ACTIVE)

    def __repr__(self):
        return f"<Tenant {self.slug} ({self.status})>"
