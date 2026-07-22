from flask import render_template, url_for

from app.models import Category, Order, Product
from app.services.report_service import ReportService
from app.utils.decorators import lojista_required
from app.utils.tenant_context import get_current_tenant

from app.controllers.lojista import lojista_bp


@lojista_bp.route("/dashboard")
@lojista_required
def dashboard():
    tenant = get_current_tenant()

    total_categories = Category.query.filter_by(tenant_id=tenant.id).count()
    total_products = Product.query.filter_by(tenant_id=tenant.id).count()
    total_orders = Order.query.filter_by(tenant_id=tenant.id).count()
    revenue_summary = ReportService(tenant).summary()

    return render_template(
        "lojista/dashboard.html",
        tenant=tenant,
        total_categories=total_categories,
        total_products=total_products,
        total_orders=total_orders,
        revenue_summary=revenue_summary,
        cardapio_url_path=f"/loja/{tenant.slug}",
        cardapio_url_absolute=url_for("public.store_home", slug=tenant.slug, _external=True),
    )
