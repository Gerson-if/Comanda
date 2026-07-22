"""
Tenant = a "loja" (lojista/cliente) dentro da plataforma SaaS.
Plan   = plano de assinatura oferecido pelo Super Administrador.

Todo dado de domínio de uma loja (produtos, categorias, pedidos, clientes,
imagens) referencia tenants.id. O isolamento entre lojistas acontece
filtrando SEMPRE por tenant_id nas queries (ver base_repository.py).
"""

import enum
from datetime import datetime, time

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

# Dias da semana usados como chave no JSON de `opening_hours`, na ordem
# de exibição do formulário (segunda a domingo). O valor de cada dia é
# {"closed": true} ou {"open": "HH:MM", "close": "HH:MM"}.
WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAY_LABELS = {
    "mon": "Segunda", "tue": "Terça", "wed": "Quarta", "thu": "Quinta",
    "fri": "Sexta", "sat": "Sábado", "sun": "Domingo",
}


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

    # Endereço da loja (exibido no cardápio público — rodapé/sobre a
    # loja). Todos opcionais: uma loja só de entrega por raio, por
    # exemplo, pode preferir não divulgar o endereço físico.
    address_street = Column(String(180), nullable=True)
    address_number = Column(String(20), nullable=True)
    address_neighborhood = Column(String(100), nullable=True)
    address_city = Column(String(100), nullable=True)

    # Horário de funcionamento. JSON por dia da semana (chaves em
    # WEEKDAY_KEYS): {"mon": {"open": "18:00", "close": "23:00"}, ...}
    # ou {"mon": {"closed": true}} para um dia fechado. `None`/vazio
    # significa "sem horário configurado" — o cardápio público não
    # mostra o status aberto/fechado nesse caso.
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

    @property
    def has_opening_hours(self) -> bool:
        return bool(self.opening_hours)

    def opening_status(self, now: datetime | None = None) -> dict | None:
        """
        Calcula o status "aberto agora" / "fechado agora" a partir de
        `opening_hours`, usando o horário local do servidor (não há
        fuso horário por tenant nesta versão — para operação em mais
        de um fuso, considere adicionar um campo de timezone).

        Retorna None se a loja não configurou horário de funcionamento
        (nesse caso, o cardápio público simplesmente não mostra o
        badge de status). Caso contrário, retorna um dict:
            {"open": bool, "label": "Aberto agora · fecha às 23:00"}
        """
        if not self.opening_hours:
            return None

        now = now or datetime.now()
        today_key = WEEKDAY_KEYS[now.weekday()]
        today = self.opening_hours.get(today_key) or {}

        if today.get("closed") or not today.get("open") or not today.get("close"):
            next_label = self._next_opening_label(now)
            return {"open": False, "label": f"Fechado agora{next_label}"}

        try:
            open_t = time.fromisoformat(today["open"])
            close_t = time.fromisoformat(today["close"])
        except (ValueError, TypeError):
            return None

        current_t = now.time()
        # Horário "cruzando a meia-noite" (ex: abre 18:00, fecha 02:00)
        is_open = (open_t <= current_t <= close_t) if open_t <= close_t else (current_t >= open_t or current_t <= close_t)

        if is_open:
            return {"open": True, "label": f"Aberto agora · fecha às {today['close']}"}
        if current_t < open_t:
            return {"open": False, "label": f"Fechado agora · abre às {today['open']}"}
        return {"open": False, "label": f"Fechado agora{self._next_opening_label(now)}"}

    def _next_opening_label(self, now: datetime) -> str:
        """Procura o próximo dia (a partir de amanhã) com horário configurado."""
        for offset in range(1, 8):
            idx = (now.weekday() + offset) % 7
            day = self.opening_hours.get(WEEKDAY_KEYS[idx]) or {}
            if not day.get("closed") and day.get("open"):
                day_label = "amanhã" if offset == 1 else WEEKDAY_LABELS[WEEKDAY_KEYS[idx]]
                return f" · abre {day_label} às {day['open']}"
        return ""

    def __repr__(self):
        return f"<Tenant {self.slug} ({self.status})>"
