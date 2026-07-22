"""
Regras de negócio de autenticação.

Centraliza aqui (e não no controller) as regras de:
- credenciais inválidas
- usuário inativo
- conta do lojista (tenant) suspensa / bloqueada por inadimplência / cancelada

para que a mesma regra sirva tanto o login via formulário HTML (fase atual)
quanto uma futura API JSON, sem duplicar lógica.
"""

from datetime import datetime, timezone

from app.extensions import db
from app.models import User, TenantStatus
from app.repositories.user_repository import UserRepository


class AuthError(Exception):
    """Erro genérico de autenticação, com mensagem segura para exibir ao usuário."""


class InvalidCredentialsError(AuthError):
    def __init__(self):
        super().__init__("E-mail ou senha inválidos.")


class AccountInactiveError(AuthError):
    def __init__(self):
        super().__init__("Este usuário está inativo. Fale com o administrador.")


class TenantBlockedError(AuthError):
    def __init__(self, tenant_status: TenantStatus):
        messages = {
            TenantStatus.SUSPENDED: "Sua conta está suspensa. Fale com o suporte.",
            TenantStatus.BLOCKED_PAYMENT: "Sua conta está bloqueada por pendência de pagamento.",
            TenantStatus.CANCELED: "Sua conta foi cancelada.",
        }
        super().__init__(messages.get(tenant_status, "Sua conta não está disponível no momento."))


class AuthService:
    def __init__(self):
        self.user_repository = UserRepository()

    def authenticate(self, email: str, password: str) -> User:
        user = self.user_repository.get_by_email(email)

        if user is None or not user.check_password(password):
            raise InvalidCredentialsError()

        if not user.is_active:
            raise AccountInactiveError()

        if not user.is_super_admin:
            tenant = user.tenant
            if tenant is None or tenant.status not in (TenantStatus.TRIAL, TenantStatus.ACTIVE):
                status = tenant.status if tenant else TenantStatus.CANCELED
                raise TenantBlockedError(status)

        user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()

        return user
