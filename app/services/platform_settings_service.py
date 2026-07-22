"""
Regras de negócio das configurações globais da plataforma (Super
Admin) — hoje só a integração de cobrança com o Asaas.
"""

import secrets

from app.extensions import db
from app.models.platform_settings import PlatformSettings
from app.services.payment_gateway import get_gateway
from app.services.payment_gateway.base import PaymentGatewayError


class PlatformSettingsService:
    def __init__(self):
        self.settings = PlatformSettings.get_or_create()

    def update_asaas(
        self, *, environment: str,
        api_key: str | None = None, clear_api_key: bool = False,
        webhook_token: str | None = None, clear_webhook_token: bool = False,
    ) -> PlatformSettings:
        self.settings.asaas_environment = environment or "sandbox"

        if clear_api_key:
            self.settings.asaas_api_key = None
        elif api_key:
            self.settings.asaas_api_key = api_key.strip()

        if clear_webhook_token:
            self.settings.asaas_webhook_token = None
        elif webhook_token:
            self.settings.asaas_webhook_token = webhook_token.strip()

        db.session.commit()
        return self.settings

    def generate_webhook_token(self) -> str:
        """Gera um token aleatório e seguro (evita o erro comum de
        configurar um token curto/previsível "na mão"). Salva
        imediatamente — o valor só é exibido uma vez, no flash da
        própria requisição que chamou este método."""
        token = secrets.token_urlsafe(32)
        self.settings.asaas_webhook_token = token
        db.session.commit()
        return token

    def test_connection(self) -> None:
        """Chama o Asaas com a chave salva atualmente, só para leitura,
        e levanta PaymentGatewayError com uma mensagem exibível se a
        chave for inválida ou a conexão falhar. Usado pelo botão
        "Testar conexão" — detecta uma chave errada antes dela ser
        usada de verdade para gerar uma cobrança."""
        gateway = get_gateway()
        if gateway is None:
            raise PaymentGatewayError("Nenhuma chave de API configurada ainda.")
        gateway.ping()

    def update_admin_appearance(self, *, accent_color=None, reset_to_default=False):
        from app.utils.colors import normalize_hex

        if reset_to_default:
            self.settings.admin_theme_accent = None
        elif accent_color:
            normalized = normalize_hex(accent_color)
            if normalized:
                self.settings.admin_theme_accent = normalized
        db.session.commit()
        return self.settings
