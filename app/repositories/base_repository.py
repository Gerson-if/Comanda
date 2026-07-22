"""
Repositório base — camada de acesso a dados.

Todo repositório de uma entidade "tenant-scoped" (Category, Product, Order,
Customer, etc.) deve herdar de `TenantScopedRepository`, que:

1. Recebe um `tenant_id` obrigatório no construtor.
2. Filtra AUTOMATICAMENTE qualquer query por esse tenant_id.

Isso existe para que seja estruturalmente difícil um lojista acessar dado
de outro por engano — o isolamento não depende de "lembrar" de filtrar em
cada query espalhada pela aplicação; ele fica centralizado aqui.

A implementação completa dos repositórios concretos (ProductRepository,
OrderRepository, etc.) e do middleware que resolve `tenant_id` a partir do
usuário logado ou do slug da URL pública será feita na fase de
Autenticação & Multi-tenant.
"""

from typing import Generic, Optional, Type, TypeVar

from app.extensions import db

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """Repositório genérico para entidades SEM escopo de tenant
    (ex: Plan, e o próprio Tenant)."""

    model: Type[ModelType]

    def get_by_id(self, entity_id: int) -> Optional[ModelType]:
        return db.session.get(self.model, entity_id)

    def list_all(self):
        return db.session.query(self.model).all()

    def add(self, entity: ModelType) -> ModelType:
        db.session.add(entity)
        db.session.commit()
        return entity

    def delete(self, entity: ModelType) -> None:
        db.session.delete(entity)
        db.session.commit()


class TenantScopedRepository(BaseRepository[ModelType]):
    """Repositório genérico para entidades COM escopo de tenant."""

    def __init__(self, tenant_id: int):
        if tenant_id is None:
            raise ValueError(
                "TenantScopedRepository exige um tenant_id — nunca instancie "
                "sem um tenant explícito, mesmo em código do Super Admin."
            )
        self.tenant_id = tenant_id

    def _base_query(self):
        return db.session.query(self.model).filter(self.model.tenant_id == self.tenant_id)

    def get_by_id(self, entity_id: int) -> Optional[ModelType]:
        return self._base_query().filter(self.model.id == entity_id).first()

    def list_all(self):
        return self._base_query().all()
