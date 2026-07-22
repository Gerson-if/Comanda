"""
Configurações globais da plataforma, geridas pelo Super Administrador
(não são escopadas por tenant — não herdam TenantScopedMixin).

Hoje guarda só as credenciais da integração de cobrança com o Asaas
(usada para cobrar as faturas dos lojistas, ver
app/services/payment_gateway/ e app/services/admin_billing_service.py).
Antes só dava pra configurar via variável de ambiente (ASAAS_API_KEY
etc.) — isso continua funcionando como valor padrão/fallback (ver
`get_gateway()`), mas agora o Super Admin pode configurar e trocar pela
tela de administração, sem precisar de acesso ao servidor.

Tabela de linha única (singleton): sempre o registro de id=1, obtido
via `PlatformSettings.get_or_create()`.
"""

from sqlalchemy import Column, Integer, String

from app.extensions import db
from app.models.base import TimestampMixin

ASAAS_ENVIRONMENT_CHOICES = [
    ("sandbox", "Sandbox (testes)"),
    ("production", "Produção"),
]


class PlatformSettings(db.Model, TimestampMixin):
    __tablename__ = "platform_settings"

    id = Column(Integer, primary_key=True)

    asaas_api_key = Column(String(255), nullable=True)
    asaas_environment = Column(String(20), nullable=False, default="sandbox", server_default="sandbox")
    asaas_webhook_token = Column(String(255), nullable=True)

    @classmethod
    def get_or_create(cls) -> "PlatformSettings":
        settings = db.session.get(cls, 1)
        if settings is None:
            settings = cls(id=1, asaas_environment="sandbox")
            db.session.add(settings)
            db.session.commit()
        return settings

    @property
    def asaas_configured(self) -> bool:
        return bool(self.asaas_api_key)

    @property
    def asaas_webhook_configured(self) -> bool:
        return bool(self.asaas_webhook_token)

    def __repr__(self):
        return f"<PlatformSettings asaas_configured={self.asaas_configured}>"
