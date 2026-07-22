import json

from app.extensions import db
from app.models import Category, ComplementGroup, ComplementOption, Order, Product, Tenant


def _create_product_with_complements(app):
    with app.app_context():
        tenant = Tenant.query.filter_by(slug="braseiro-cia").first()
        tenant.whatsapp_number = "5567999998888"
        category = Category(tenant_id=tenant.id, name="Espetos", slug="espetos-cx", is_active=True)
        db.session.add(category)
        db.session.flush()

        product = Product(
            tenant_id=tenant.id, category_id=category.id, name="Espeto Misto",
            slug="espeto-misto-cx", price_cents=2000, is_active=True,
        )
        db.session.add(product)
        db.session.flush()

        size_group = ComplementGroup(
            tenant_id=tenant.id, product_id=product.id, name="Tamanho",
            is_variation=True, is_required=True, single_choice=True, display_order=0,
        )
        sauce_group = ComplementGroup(
            tenant_id=tenant.id, product_id=product.id, name="Molhos",
            is_variation=False, is_required=False, single_choice=False, display_order=1,
        )
        db.session.add_all([size_group, sauce_group])
        db.session.flush()

        big = ComplementOption(tenant_id=tenant.id, group_id=size_group.id, name="Grande", extra_price_cents=500, display_order=0)
        small = ComplementOption(tenant_id=tenant.id, group_id=size_group.id, name="Pequeno", extra_price_cents=0, display_order=1)
        bbq = ComplementOption(tenant_id=tenant.id, group_id=sauce_group.id, name="Barbecue", extra_price_cents=200, display_order=0)
        db.session.add_all([big, small, bbq])
        db.session.commit()

        return {
            "product_id": product.id, "tenant_id": tenant.id,
            "size_group_id": size_group.id, "sauce_group_id": sauce_group.id,
            "big_id": big.id, "small_id": small.id, "bbq_id": bbq.id,
        }


def _checkout(client, product_id, option_ids, quantity=1, phone="67999991234"):
    payload = {
        "customer_name": "Cliente Complementos", "customer_phone": phone,
        "delivery_type": "pickup", "payment_method": "pix",
        "items": [{"product_id": product_id, "quantity": quantity, "option_ids": option_ids}],
    }
    return client.post("/loja/braseiro-cia/pedido", data=json.dumps(payload), content_type="application/json")


class TestComplementsInCheckout:
    def test_menu_data_exposes_complement_groups(self, app, client):
        ids = _create_product_with_complements(app)
        resp = client.get("/loja/braseiro-cia")
        html = resp.get_data(as_text=True)
        assert "Tamanho" in html
        assert "Molhos" in html
        assert "Grande" in html

    def test_required_group_without_selection_is_rejected(self, app, client):
        ids = _create_product_with_complements(app)
        resp = _checkout(client, ids["product_id"], [])
        assert resp.status_code == 400
        assert "Tamanho" in resp.get_json()["error"]

    def test_valid_selection_computes_correct_price(self, app, client):
        ids = _create_product_with_complements(app)
        resp = _checkout(client, ids["product_id"], [ids["big_id"], ids["bbq_id"]], quantity=2)
        assert resp.status_code == 201
        data = resp.get_json()
        # (2000 base + 500 tamanho + 200 molho) * 2 = 5400
        assert data["total_cents"] == 5400

        with app.app_context():
            order = db.session.get(Order, data["order_id"])
            item = order.items[0]
            assert item.unit_price_cents == 2700
            choice_pairs = {(c.group_name, c.option_name) for c in item.choices}
            assert ("Tamanho", "Grande") in choice_pairs
            assert ("Molhos", "Barbecue") in choice_pairs

    def test_single_choice_group_rejects_two_selections(self, app, client):
        ids = _create_product_with_complements(app)
        resp = _checkout(client, ids["product_id"], [ids["big_id"], ids["small_id"]])
        assert resp.status_code == 400
        assert "uma opção" in resp.get_json()["error"]

    def test_nonexistent_option_id_is_rejected(self, app, client):
        ids = _create_product_with_complements(app)
        resp = _checkout(client, ids["product_id"], [999999])
        assert resp.status_code == 400

    def test_option_from_another_tenant_is_rejected(self, app, client):
        ids = _create_product_with_complements(app)

        with app.app_context():
            from app.models import Plan, TenantStatus

            plan = Plan.query.first()
            other_tenant = Tenant(name="Outra Loja Cx", slug="outra-loja-cx", email="outracx@x.com", plan_id=plan.id, status=TenantStatus.ACTIVE)
            db.session.add(other_tenant)
            db.session.flush()
            other_category = Category(tenant_id=other_tenant.id, name="Cat", slug="cat-cx", is_active=True)
            db.session.add(other_category)
            db.session.flush()
            other_product = Product(tenant_id=other_tenant.id, category_id=other_category.id, name="Produto Outro", slug="produto-outro-cx", price_cents=1000, is_active=True)
            db.session.add(other_product)
            db.session.flush()
            other_group = ComplementGroup(tenant_id=other_tenant.id, product_id=other_product.id, name="G", is_variation=False, is_required=False, single_choice=False)
            db.session.add(other_group)
            db.session.flush()
            other_option = ComplementOption(tenant_id=other_tenant.id, group_id=other_group.id, name="Barato", extra_price_cents=0)
            db.session.add(other_option)
            db.session.commit()
            other_option_id = other_option.id

        # tenta comprar o "Espeto Misto" da loja braseiro-cia usando o id
        # de uma opção que pertence a um produto de outra loja
        resp = _checkout(client, ids["product_id"], [other_option_id])
        assert resp.status_code == 400

    def test_optional_group_can_be_skipped(self, app, client):
        ids = _create_product_with_complements(app)
        resp = _checkout(client, ids["product_id"], [ids["small_id"]])  # só o obrigatório, sem molho
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["total_cents"] == 2000  # base + 0 (pequeno) + nenhum molho

    def test_whatsapp_message_includes_choices(self, app, client):
        ids = _create_product_with_complements(app)
        resp = _checkout(client, ids["product_id"], [ids["big_id"], ids["bbq_id"]])
        data = resp.get_json()

        import urllib.parse

        message = urllib.parse.unquote(data["whatsapp_url"].split("text=")[1])
        assert "Tamanho: Grande" in message
        assert "Molhos: Barbecue" in message

    def test_inactive_option_is_treated_as_unavailable(self, app, client):
        ids = _create_product_with_complements(app)
        with app.app_context():
            option = db.session.get(ComplementOption, ids["bbq_id"])
            option.is_active = False
            db.session.commit()

        resp = _checkout(client, ids["product_id"], [ids["big_id"], ids["bbq_id"]])
        assert resp.status_code == 400
