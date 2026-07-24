import json

from app.extensions import db
from app.models import Category, Order, Product, Tenant


def _create_category_and_product(app, tenant_slug="braseiro-cia", price_cents=5000, name="Espeto de Picanha"):
    with app.app_context():
        tenant = Tenant.query.filter_by(slug=tenant_slug).first()
        category = Category(tenant_id=tenant.id, name="Espetos", slug="espetos", is_active=True)
        db.session.add(category)
        db.session.flush()

        product = Product(
            tenant_id=tenant.id, category_id=category.id, name=name,
            slug="espeto-de-picanha", price_cents=price_cents, is_active=True,
        )
        db.session.add(product)
        db.session.commit()
        return product.id, tenant.id


class TestPublicMenuPage:
    def test_menu_shows_active_products_only(self, app, client):
        with app.app_context():
            tenant = Tenant.query.filter_by(slug="braseiro-cia").first()
            category = Category(tenant_id=tenant.id, name="Bebidas", slug="bebidas", is_active=True)
            db.session.add(category)
            db.session.flush()
            active = Product(tenant_id=tenant.id, category_id=category.id, name="Refrigerante", slug="refri", price_cents=800, is_active=True)
            inactive = Product(tenant_id=tenant.id, category_id=category.id, name="Suco Descontinuado", slug="suco-desc", price_cents=900, is_active=False)
            db.session.add_all([active, inactive])
            db.session.commit()

        resp = client.get("/loja/braseiro-cia")
        body = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "Refrigerante" in body
        assert "Suco Descontinuado" not in body


class TestCheckout:
    def test_pickup_order_is_created_and_price_comes_from_server(self, app, client):
        product_id, tenant_id = _create_category_and_product(app, price_cents=5000)

        payload = {
            "customer_name": "João Cliente",
            "customer_phone": "67999990000",
            "delivery_type": "pickup",
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": 3, "price_cents": 1}],  # preço "hackeado" deve ser ignorado
        }
        resp = client.post(
            "/loja/braseiro-cia/pedido",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["order_number"] == 1
        assert data["total_cents"] == 5000 * 3  # preço do servidor, não o "1" enviado pelo cliente

        with app.app_context():
            order = db.session.get(Order, data["order_id"])
            assert order.subtotal_cents == 15000
            assert order.total_cents == 15000
            assert order.customer_name == "João Cliente"
            assert order.items[0].unit_price_cents == 5000

    def test_order_number_increments_sequentially(self, app, client):
        product_id, _ = _create_category_and_product(app)

        for _ in range(2):
            payload = {
                "customer_name": "Cliente", "customer_phone": "67988887777",
                "delivery_type": "pickup", "payment_method": "pix",
                "items": [{"product_id": product_id, "quantity": 1}],
            }
            resp = client.post("/loja/braseiro-cia/pedido", data=json.dumps(payload), content_type="application/json")
            assert resp.status_code == 201

        with app.app_context():
            tenant = Tenant.query.filter_by(slug="braseiro-cia").first()
            numbers = sorted(o.order_number for o in Order.query.filter_by(tenant_id=tenant.id).all())
            assert numbers == [1, 2]

    def test_delivery_requires_address_fields(self, app, client):
        product_id, _ = _create_category_and_product(app)

        payload = {
            "customer_name": "Maria", "customer_phone": "67977776666",
            "delivery_type": "delivery", "payment_method": "card",
            "items": [{"product_id": product_id, "quantity": 1}],
        }
        resp = client.post("/loja/braseiro-cia/pedido", data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 400
        assert "details" in resp.get_json()

    def test_delivery_with_full_address_succeeds_and_applies_fee(self, app, client):
        product_id, tenant_id = _create_category_and_product(app, price_cents=4000)

        with app.app_context():
            tenant = db.session.get(Tenant, tenant_id)
            tenant.delivery_enabled = True
            tenant.delivery_fee_cents = 700
            db.session.commit()

        payload = {
            "customer_name": "Ana", "customer_phone": "67966665555",
            "delivery_type": "delivery", "payment_method": "pix",
            "address_street": "Rua das Palmeiras", "address_number": "42",
            "address_neighborhood": "Centro",
            "items": [{"product_id": product_id, "quantity": 2}],
        }
        resp = client.post("/loja/braseiro-cia/pedido", data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["total_cents"] == (4000 * 2) + 700

    def test_delivery_disabled_by_tenant_is_rejected(self, app, client):
        product_id, tenant_id = _create_category_and_product(app)
        with app.app_context():
            tenant = db.session.get(Tenant, tenant_id)
            tenant.delivery_enabled = False
            db.session.commit()

        payload = {
            "customer_name": "Carlos", "customer_phone": "67955554444",
            "delivery_type": "delivery", "payment_method": "cash",
            "address_street": "Rua X", "address_number": "1", "address_neighborhood": "Bairro",
            "items": [{"product_id": product_id, "quantity": 1}],
        }
        resp = client.post("/loja/braseiro-cia/pedido", data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 400
        assert "entrega" in resp.get_json()["error"].lower()

    def test_min_order_is_enforced(self, app, client):
        product_id, tenant_id = _create_category_and_product(app, price_cents=1000)
        with app.app_context():
            tenant = db.session.get(Tenant, tenant_id)
            tenant.min_order_cents = 5000
            db.session.commit()

        payload = {
            "customer_name": "Bruno", "customer_phone": "67944443333",
            "delivery_type": "pickup", "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": 1}],
        }
        resp = client.post("/loja/braseiro-cia/pedido", data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 400
        assert "mínimo" in resp.get_json()["error"].lower()

    def test_empty_cart_is_rejected(self, client):
        payload = {
            "customer_name": "Zero", "customer_phone": "67900000000",
            "delivery_type": "pickup", "payment_method": "cash",
            "items": [],
        }
        resp = client.post("/loja/braseiro-cia/pedido", data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 400

    def test_product_from_another_tenant_is_rejected(self, app, client):
        with app.app_context():
            from app.models import Plan, TenantStatus

            plan = Plan.query.first()
            other_tenant = Tenant(name="Outra Loja", slug="outra-loja", email="outra@loja.com", plan_id=plan.id, status=TenantStatus.ACTIVE)
            db.session.add(other_tenant)
            db.session.flush()
            other_category = Category(tenant_id=other_tenant.id, name="Cat", slug="cat", is_active=True)
            db.session.add(other_category)
            db.session.flush()
            other_product = Product(tenant_id=other_tenant.id, category_id=other_category.id, name="Produto Alheio", slug="produto-alheio", price_cents=100, is_active=True)
            db.session.add(other_product)
            db.session.commit()
            other_product_id = other_product.id

        payload = {
            "customer_name": "Tentando Trapacear", "customer_phone": "67911112222",
            "delivery_type": "pickup", "payment_method": "cash",
            "items": [{"product_id": other_product_id, "quantity": 1}],
        }
        # tenta comprar produto de "outra-loja" através do cardápio de "braseiro-cia"
        resp = client.post("/loja/braseiro-cia/pedido", data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 400

    def test_inactive_product_is_rejected(self, app, client):
        with app.app_context():
            tenant = Tenant.query.filter_by(slug="braseiro-cia").first()
            category = Category(tenant_id=tenant.id, name="Cat2", slug="cat2", is_active=True)
            db.session.add(category)
            db.session.flush()
            product = Product(tenant_id=tenant.id, category_id=category.id, name="Descontinuado", slug="descontinuado", price_cents=100, is_active=False)
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        payload = {
            "customer_name": "X", "customer_phone": "67900001111",
            "delivery_type": "pickup", "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": 1}],
        }
        resp = client.post("/loja/braseiro-cia/pedido", data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 400

    def test_whatsapp_url_is_returned_when_tenant_has_number(self, app, client):
        product_id, tenant_id = _create_category_and_product(app)
        with app.app_context():
            tenant = db.session.get(Tenant, tenant_id)
            tenant.whatsapp_number = "5567999998888"
            db.session.commit()

        payload = {
            "customer_name": "Whats Teste", "customer_phone": "67933332222",
            "delivery_type": "pickup", "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": 1}],
        }
        resp = client.post("/loja/braseiro-cia/pedido", data=json.dumps(payload), content_type="application/json")
        data = resp.get_json()
        assert data["whatsapp_url"].startswith("https://wa.me/5567999998888?text=")

    def test_repeat_customer_reuses_customer_record(self, app, client):
        product_id, tenant_id = _create_category_and_product(app)

        for _ in range(2):
            payload = {
                "customer_name": "Cliente Fiel", "customer_phone": "67922221111",
                "delivery_type": "pickup", "payment_method": "cash",
                "items": [{"product_id": product_id, "quantity": 1}],
            }
            client.post("/loja/braseiro-cia/pedido", data=json.dumps(payload), content_type="application/json")

        with app.app_context():
            from app.models import Customer
            from app.utils.phone import normalize_br_phone

            # Customer.phone é salvo normalizado (ver app/utils/phone.py) —
            # não no formato bruto que veio no payload.
            customers = Customer.query.filter_by(
                tenant_id=tenant_id, phone=normalize_br_phone("67922221111")
            ).all()
            assert len(customers) == 1
            assert len(customers[0].orders) == 2
