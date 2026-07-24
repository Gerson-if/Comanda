from flask import render_template, request

from app.services.customer_service import CustomerService
from app.utils.decorators import lojista_required
from app.utils.tenant_context import get_current_tenant

from app.controllers.lojista import lojista_bp


@lojista_bp.route("/clientes")
@lojista_required
def customers_list():
    tenant = get_current_tenant()
    page = request.args.get("page", 1, type=int)

    service = CustomerService(tenant)
    pagination = service.paginated(page=page)

    return render_template("lojista/customers/list.html", pagination=pagination)
