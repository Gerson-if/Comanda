import re

import pytest

from app import create_app
from app.extensions import db
from app.models import Plan, BillingCycle, Tenant, TenantStatus, User, UserRole


@pytest.fixture()
def app():
    app = create_app("testing")

    with app.app_context():
        db.create_all()

        plan = Plan(name="Básico", slug="basico", price_cents=4990, billing_cycle=BillingCycle.MONTHLY)
        db.session.add(plan)
        db.session.flush()

        tenant = Tenant(
            name="Braseiro & Cia",
            slug="braseiro-cia",
            email="contato@braseiroecia.com.br",
            plan_id=plan.id,
            status=TenantStatus.ACTIVE,
            delivery_enabled=True,
        )
        db.session.add(tenant)
        db.session.flush()

        admin = User(name="Admin", email="admin@cardapio.saas", role=UserRole.SUPER_ADMIN, tenant_id=None)
        admin.set_password("admin123")

        owner = User(name="Lojista", email="lojista@braseiroecia.com.br", role=UserRole.OWNER, tenant_id=tenant.id)
        owner.set_password("lojista123")

        db.session.add_all([admin, owner])
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _extract_csrf(html: str) -> str | None:
    # Em TestingConfig, WTF_CSRF_ENABLED=False, então o campo pode nem
    # ser renderizado — nesse caso o backend também não vai validar,
    # então simplesmente seguimos sem o token.
    match = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', html)
    return match.group(1) if match else None


@pytest.fixture()
def login_as():
    """Fixture factory: login_as(client, email, password) -> Response"""

    def _login(client, email, password):
        resp = client.get("/login")
        csrf = _extract_csrf(resp.get_data(as_text=True))
        data = {"email": email, "password": password}
        if csrf:
            data["csrf_token"] = csrf
        return client.post("/login", data=data, follow_redirects=True)

    return _login
