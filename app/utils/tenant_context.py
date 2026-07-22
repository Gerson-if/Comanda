"""
Contexto multi-tenant da requisição.

Duas formas de uma requisição "pertencer" a um tenant:

1. Lojista autenticado: o tenant é o do próprio usuário logado
   (`current_user.tenant`). Resolvido automaticamente em todo request
   autenticado por `load_tenant_from_session` (registrado como
   `before_request` no app factory).

2. Visitante do cardápio público: não há login, o tenant é resolvido pelo
   slug presente na URL (ex: /loja/<slug>). Feito explicitamente pelo
   controller público via `resolve_tenant_by_slug`, pois só ali existe
   o slug para consultar.

Em ambos os casos, o tenant resolvido fica em `flask.g.tenant`, e
`get_current_tenant()` é o único ponto de leitura usado pelo resto da
aplicação (services, templates) — nenhum código deve ler
`current_user.tenant_id` diretamente, para manter um único caminho de
resolução.
"""

from flask import g, abort
from flask_login import current_user

from app.models import Tenant, TenantStatus


def load_tenant_from_session() -> None:
    """Registrado como `before_request`. Preenche g.tenant quando há um
    lojista autenticado. Não faz nada para super admin (não tem tenant)
    nem para requisições ainda sem `g.tenant` de rota pública."""
    g.tenant = None
    if current_user.is_authenticated and not current_user.is_super_admin:
        g.tenant = current_user.tenant


def resolve_tenant_by_slug(slug: str) -> Tenant:
    """Usado pelas rotas públicas (/loja/<slug>). Aborta com 404 se a loja
    não existir ou não estiver com uma conta ativa — visitante nunca deve
    saber se um slug existe ou não caso a conta esteja bloqueada/cancelada,
    então tratamos os dois casos como 404 (não vazamos o motivo)."""
    tenant = Tenant.query.filter_by(slug=slug).first()
    if tenant is None or tenant.status not in (TenantStatus.TRIAL, TenantStatus.ACTIVE):
        abort(404)
    g.tenant = tenant
    return tenant


def get_current_tenant() -> Tenant | None:
    return getattr(g, "tenant", None)
