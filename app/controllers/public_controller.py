"""
Cardápio público — acessível sem login, por slug (/loja/<slug>).

- GET  /loja/<slug>          -> página do cardápio (categorias, produtos)
- POST /loja/<slug>/pedido   -> cria o pedido (JSON) e retorna o link do
                                 WhatsApp para o cliente finalizar o envio
"""

from flask import Blueprint, jsonify, render_template, request
from flask_wtf.csrf import validate_csrf, CSRFError
from marshmallow import ValidationError

from app.extensions import csrf
from app.models import Category, Product
from app.schemas.checkout_schema import CheckoutSchema
from app.services.order_service import OrderService, OrderValidationError
from app.utils.tenant_context import resolve_tenant_by_slug
from app.utils.whatsapp import build_order_message, build_whatsapp_url

public_bp = Blueprint("public", __name__, url_prefix="/loja")


def _serialize_product(product):
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description or "",
        "price_cents": product.price_cents,
        "tag": product.tag,
        "has_complements": bool(product.complement_groups),
        "image_url": (
            f"/static/{product.primary_image.file_path}"
            if product.primary_image
            else None
        ),
        "complement_groups": [
            {
                "id": group.id,
                "name": group.name,
                "is_variation": group.is_variation,
                "is_required": group.is_required,
                "single_choice": group.single_choice,
                "options": [
                    {
                        "id": option.id,
                        "name": option.name,
                        "extra_price_cents": option.extra_price_cents,
                    }
                    for option in group.options
                    if option.is_active
                ],
            }
            for group in sorted(product.complement_groups, key=lambda g: g.display_order)
            if group.options
        ],
    }


def _build_menu_data(tenant):
    categories = (
        Category.query.filter_by(tenant_id=tenant.id, is_active=True)
        .order_by(Category.display_order, Category.name)
        .all()
    )

    menu_categories = []
    for category in categories:
        products = [p for p in category.products if p.is_active]
        products.sort(key=lambda p: (p.display_order, p.name))
        if not products:
            continue

        menu_categories.append(
            {
                "id": category.id,
                "name": category.name,
                "icon": category.icon or "other",
                "products": [_serialize_product(product) for product in products],
            }
        )

    # Produtos sem categoria (category_id NULL) não pertencem a nenhum
    # Category.products acima — sem isso, ficariam cadastrados mas
    # invisíveis para sempre no cardápio público. Agrupamos todos num
    # bucket sintético no fim do menu.
    #
    # Importante: o nome desse bucket precisa ser diferente de "Outros"
    # — esse é um nome comum para uma categoria de verdade que o lojista
    # cria (ex: "Outros" com adicionais avulsos). Se os dois se
    # chamassem igual, o cliente veria duas entradas idênticas na barra
    # lateral (a categoria real "Outros" e este bucket sintético), o que
    # parece um bug de duplicação mesmo não sendo.
    uncategorized = (
        Product.query.filter_by(tenant_id=tenant.id, category_id=None, is_active=True)
        .order_by(Product.display_order, Product.name)
        .all()
    )
    if uncategorized:
        menu_categories.append(
            {
                "id": "uncategorized",
                "name": "Sem categoria",
                "icon": "other",
                "products": [_serialize_product(product) for product in uncategorized],
            }
        )

    address_parts = [
        f"{tenant.address_street}, {tenant.address_number}" if tenant.address_street and tenant.address_number
        else (tenant.address_street or ""),
        tenant.address_neighborhood or "",
        tenant.address_city or "",
    ]
    address_line = " — ".join(part for part in address_parts if part) or None

    service_labels = []
    if tenant.pickup_enabled:
        service_labels.append("Retirada")
    if tenant.delivery_enabled:
        service_labels.append("Entrega")
    service_line = " e ".join(service_labels) or None

    return {
        "tenant": {
            "name": tenant.name,
            "slug": tenant.slug,
            "delivery_enabled": tenant.delivery_enabled,
            "pickup_enabled": tenant.pickup_enabled,
            "delivery_fee_cents": tenant.delivery_fee_cents or 0,
            "free_delivery_above_cents": tenant.free_delivery_above_cents or 0,
            "min_order_cents": tenant.min_order_cents or 0,
            "address_line": address_line,
            "service_line": service_line,
            "opening_status": tenant.opening_status(),
            "accepted_payment_methods": tenant.accepted_payment_methods,
        },
        "categories": menu_categories,
    }


@public_bp.route("/<slug>")
def store_home(slug):
    tenant = resolve_tenant_by_slug(slug)
    menu_data = _build_menu_data(tenant)

    from app.services.banner_service import BannerService

    banners = BannerService(tenant).repo.list_active_ordered()
    banners_data = [
        {
            "id": banner.id,
            "title": banner.title,
            "subtitle": banner.subtitle or "",
            "link_url": banner.link_url,
            "image_url": f"/static/{banner.image_path}",
        }
        for banner in banners
    ]

    default_theme = {"accent": "#E8A33D", "accent_dark": "#C97F1F", "accent_soft": "rgba(232,163,61,0.14)"}
    theme = tenant.public_theme_css_vars or default_theme

    return render_template(
        "public/store_menu.html", tenant=tenant, menu_data=menu_data, banners=banners_data, theme=theme,
    )


@public_bp.route("/<slug>/pedido", methods=["POST"])
@csrf.exempt  # validado manualmente abaixo via cabeçalho X-CSRFToken
def create_order(slug):
    from flask import current_app

    if current_app.config.get("WTF_CSRF_ENABLED", True):
        try:
            validate_csrf(request.headers.get("X-CSRFToken", ""))
        except CSRFError:
            return jsonify({"error": "Sessão expirada, atualize a página e tente novamente."}), 400

    tenant = resolve_tenant_by_slug(slug)

    json_data = request.get_json(silent=True)
    if json_data is None:
        return jsonify({"error": "Payload inválido."}), 400

    schema = CheckoutSchema()
    try:
        payload = schema.load(json_data)
    except ValidationError as exc:
        return jsonify({"error": "Dados inválidos.", "details": exc.messages}), 400

    try:
        order = OrderService(tenant).create_order(payload)
    except OrderValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    message = build_order_message(order)
    whatsapp_url = build_whatsapp_url(tenant, message)

    return (
        jsonify(
            {
                "order_id": order.id,
                "order_number": order.order_number,
                "total_cents": order.total_cents,
                "whatsapp_url": whatsapp_url,
            }
        ),
        201,
    )
