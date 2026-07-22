from flask import render_template

from app.models import Tenant, TenantStatus
from app.utils.decorators import super_admin_required

from app.controllers.admin import admin_bp


@admin_bp.route("/dashboard")
@super_admin_required
def dashboard():
    total_tenants = Tenant.query.count()
    active_tenants = Tenant.query.filter(
        Tenant.status.in_([TenantStatus.TRIAL, TenantStatus.ACTIVE])
    ).count()
    blocked_tenants = Tenant.query.filter_by(status=TenantStatus.BLOCKED_PAYMENT).count()

    return render_template(
        "admin/dashboard.html",
        total_tenants=total_tenants,
        active_tenants=active_tenants,
        blocked_tenants=blocked_tenants,
    )
