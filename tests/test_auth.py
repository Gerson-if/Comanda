from app.extensions import db
from app.models import Tenant, TenantStatus


class TestLogin:
    def test_login_page_loads(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200

    def test_invalid_credentials_shows_error(self, client, login_as):
        resp = login_as(client, "admin@cardapio.saas", "senha-errada")
        assert resp.status_code == 200
        assert "inválidos" in resp.get_data(as_text=True)

    def test_super_admin_login_redirects_to_admin_dashboard(self, client, login_as):
        resp = login_as(client, "admin@cardapio.saas", "admin123")
        assert resp.status_code == 200
        assert "Métricas Core" in resp.get_data(as_text=True)

    def test_lojista_login_redirects_to_lojista_dashboard(self, client, login_as):
        resp = login_as(client, "lojista@braseiroecia.com.br", "lojista123")
        assert resp.status_code == 200
        assert "Braseiro" in resp.get_data(as_text=True)

    def test_dashboard_requires_login(self, client):
        resp = client.get("/painel/dashboard", follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


class TestAuthorization:
    def test_super_admin_cannot_access_lojista_panel(self, client, login_as):
        login_as(client, "admin@cardapio.saas", "admin123")
        resp = client.get("/painel/dashboard")
        assert resp.status_code == 403

    def test_lojista_cannot_access_admin_panel(self, client, login_as):
        login_as(client, "lojista@braseiroecia.com.br", "lojista123")
        resp = client.get("/admin/dashboard")
        assert resp.status_code == 403

    def test_blocked_tenant_cannot_login(self, app, client, login_as):
        with app.app_context():
            tenant = Tenant.query.filter_by(slug="braseiro-cia").first()
            tenant.status = TenantStatus.BLOCKED_PAYMENT
            db.session.commit()

        resp = login_as(client, "lojista@braseiroecia.com.br", "lojista123")
        body = resp.get_data(as_text=True)
        assert "bloqueada por pendência de pagamento" in body
        # não deve ter acessado o dashboard
        assert "Categorias" not in body

    def test_blocked_tenant_public_menu_returns_404(self, app, client):
        with app.app_context():
            tenant = Tenant.query.filter_by(slug="braseiro-cia").first()
            tenant.status = TenantStatus.SUSPENDED
            db.session.commit()

        resp = client.get("/loja/braseiro-cia")
        assert resp.status_code == 404


class TestPublicMenu:
    def test_active_tenant_menu_is_reachable(self, client):
        resp = client.get("/loja/braseiro-cia")
        assert resp.status_code == 200
        assert "Braseiro" in resp.get_data(as_text=True)

    def test_unknown_slug_returns_404(self, client):
        resp = client.get("/loja/nao-existe")
        assert resp.status_code == 404
