"""
Repositório de User.

Não é TenantScopedRepository: no login, ainda não sabemos o tenant (é
justamente o e-mail que nos leva até ele). O isolamento entre lojistas
continua garantido porque, a partir daqui, todo dado do painel do lojista
é acessado via repositórios tenant-scoped usando `current_user.tenant_id`.
"""

from typing import Optional

from app.models import User
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_email(self, email: str) -> Optional[User]:
        return self.model.query.filter_by(email=email.lower().strip()).first()
