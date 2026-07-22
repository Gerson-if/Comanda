"""
Decorators de autorização, usados nos controllers.

`login_required` (do Flask-Login) garante apenas que existe alguém
logado. Estes decorators aqui adicionam a checagem de PAPEL e, no caso do
lojista, de STATUS DA CONTA (uma conta bloqueada por inadimplência ou
suspensa não pode acessar o painel mesmo estando com a senha correta).
"""

from functools import wraps

from flask import abort
from flask_login import current_user, login_required

from app.models import TenantStatus


def super_admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_super_admin:
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped


def lojista_required(view_func):
    """Exige um usuário lojista (owner/staff) com uma conta em status que
    permita acesso (trial ou active). Contas suspensas, bloqueadas por
    inadimplência ou canceladas são barradas aqui, centralizadamente —
    nenhuma rota do painel do lojista precisa checar isso individualmente."""

    @wraps(view_func)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.is_super_admin:
            abort(403)

        tenant = current_user.tenant
        if tenant is None or tenant.status not in (TenantStatus.TRIAL, TenantStatus.ACTIVE):
            abort(403, description="Conta suspensa, bloqueada ou cancelada. Fale com o suporte.")

        return view_func(*args, **kwargs)

    return wrapped
