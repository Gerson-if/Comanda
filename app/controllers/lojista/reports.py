from flask import render_template

from app.controllers.lojista.orders import STATUS_LABELS
from app.services.report_service import ReportService
from app.utils.decorators import lojista_required
from app.utils.tenant_context import get_current_tenant

from app.controllers.lojista import lojista_bp


@lojista_bp.route("/vendas")
@lojista_required
def reports_dashboard():
    tenant = get_current_tenant()
    service = ReportService(tenant)

    summary = service.summary()
    status_counts = service.order_count_by_status()
    daily_series = service.daily_revenue_series(days=14)
    top_products = service.top_products(limit=5)

    return render_template(
        "lojista/reports/dashboard.html",
        summary=summary,
        status_counts=status_counts,
        status_labels=STATUS_LABELS,
        daily_series=daily_series,
        top_products=top_products,
    )
