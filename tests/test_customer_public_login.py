import json

from app.extensions import db
from app.models import Category, Product, Tenant


def _create_product_and_order(app, client, tenant_slug="braseiro-cia", phone="67999990000"):
    with app.app_context():
        tenant = Tenant.query.filter_by(slug=tenant_slug).first()
        category = Category(tenant_id=tenant.id, name="Espetos", slug="espetos-login-test", is_active=True)
        db.session.add(category)
        db.session.flush()
        product = Product(
            tenant_id=tenant.id, category_id=category.id, name="Espeto Teste Login",
            slug="espeto-teste-login", price_cents=3000, is_active=True,
        )
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    payload = {
        "customer_name": "Cliente Teste", "customer_phone": phone,
        "delivery_type": "pickup", "payment_method": "pix",
        "items": [{"product_id": product_id, "quantity": 2}],
    }
    resp = client.post(f"/loja/{tenant_slug}/pedido", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 201
    return resp.get_json()


class TestCustomerLogin:
    def test_login_with_existing_phone_returns_orders(self, app, client):
        _create_product_and_order(app, client, phone="67999990001")

        resp = client.post(
            "/loja/braseiro-cia/entrar",
            data=json.dumps({"phone": "67999990001"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Cliente Teste"

        resp = client.get("/loja/braseiro-cia/meus-pedidos")
        data = resp.get_json()
        assert data["logged_in"] is True
        assert len(data["orders"]) == 1
        assert data["orders"][0]["total_cents"] == 6000

    def test_login_with_unknown_phone_is_rejected_without_creating_customer(self, app, client):
        resp = client.post(
            "/loja/braseiro-cia/entrar",
            data=json.dumps({"phone": "67900000000"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

        with app.app_context():
            from app.models import Customer

            assert Customer.query.filter_by(phone="67900000000").first() is None

    def test_logout_clears_session(self, app, client):
        _create_product_and_order(app, client, phone="67999990002")
        client.post("/loja/braseiro-cia/entrar", data=json.dumps({"phone": "67999990002"}), content_type="application/json")

        client.post("/loja/braseiro-cia/sair")

        resp = client.get("/loja/braseiro-cia/meus-pedidos")
        assert resp.get_json()["logged_in"] is False

    def test_session_does_not_leak_across_tenants(self, app, client):
        _create_product_and_order(app, client, tenant_slug="braseiro-cia", phone="67999990003")
        client.post("/loja/braseiro-cia/entrar", data=json.dumps({"phone": "67999990003"}), content_type="application/json")

        with app.app_context():
            other_tenant = Tenant.query.filter(Tenant.slug != "braseiro-cia").first()

        if other_tenant is not None:
            resp = client.get(f"/loja/{other_tenant.slug}/meus-pedidos")
            assert resp.get_json()["logged_in"] is False
