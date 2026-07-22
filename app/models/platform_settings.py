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

    # Cor de destaque (accent) do painel administrativo (Super Admin +
    # lojista compartilham o mesmo design system "chili"). Se vazio, usa
    # o vermelho-tijolo padrão da marca — nunca fica sem cor definida.
    admin_theme_accent = Column(String(7), nullable=True)

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

    @property
    def admin_theme_css_vars(self) -> dict | None:
        """Variáveis CSS derivadas da cor de destaque escolhida, prontas
        para injetar num <style> — ou None se não houver customização
        (nesse caso o painel usa a cor padrão definida em comanda.css).
        comanda.css deriva os tons mais claros com color-mix(--accent)
        na hora, então só --accent/--accent-dark precisam ser
        sobrescritos para todo o resto do design system acompanhar."""
        if not self.admin_theme_accent:
            return None
        from app.utils.colors import darken_hex

        return {"accent": self.admin_theme_accent, "accent_dark": darken_hex(self.admin_theme_accent)}

    def __repr__(self):
        return f"<PlatformSettings asaas_configured={self.asaas_configured}>"
