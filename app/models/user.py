"""
User = qualquer pessoa que faz login no sistema.

- role = SUPER_ADMIN  -> tenant_id é sempre NULL. Gerencia toda a plataforma.
- role = OWNER         -> dono da loja (lojista principal).
- role = STAFF         -> funcionário do lojista, acesso mais restrito
                          (reservado para uma futura tela de permissões).

Login para ambos os perfis é feito por e-mail + senha (ver
app/services/auth_service.py).
"""

import enum

from flask_login import UserMixin
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.extensions import db, bcrypt
from app.models.base import TimestampMixin, str_enum


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    OWNER = "owner"
    STAFF = "staff"


class User(db.Model, UserMixin, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    # tenant_id é NULL para super admins; obrigatório para owner/staff.
    # Não usamos TenantScopedMixin aqui de propósito, pois essa tabela
    # também guarda o super admin (que não pertence a tenant nenhum).
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)

    name = Column(String(150), nullable=False)
    email = Column(String(180), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)

    role = Column(str_enum(UserRole, "user_role"), nullable=False, default=UserRole.OWNER)
    is_active = Column(Boolean, nullable=False, default=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant", back_populates="users")

    __table_args__ = (
        CheckConstraint(
            "(role = 'super_admin' AND tenant_id IS NULL) OR "
            "(role != 'super_admin' AND tenant_id IS NOT NULL)",
            name="ck_user_tenant_consistency",
        ),
    )

    # --- Senha ---
    def set_password(self, raw_password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(raw_password).decode("utf-8")

    def check_password(self, raw_password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, raw_password)

    # --- Flask-Login ---
    def get_id(self):
        # Sobrescrito para incluir o papel no id de sessão é desnecessário;
        # o padrão (str(self.id)) já é suficiente e mais simples de manter.
        return str(self.id)

    @property
    def is_super_admin(self) -> bool:
        return self.role == UserRole.SUPER_ADMIN

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
