from flask import flash, redirect, render_template, request, url_for

from app.forms.admin_forms import PlanForm
from app.services.admin_plan_service import AdminPlanService
from app.utils.decorators import super_admin_required

from app.controllers.admin import admin_bp


@admin_bp.route("/planos")
@super_admin_required
def plans_list():
    service = AdminPlanService()
    plans = service.list_all()
    return render_template("admin/plans/list.html", plans=plans)


@admin_bp.route("/planos/novo", methods=["GET", "POST"])
@super_admin_required
def plans_create():
    form = PlanForm()

    if form.validate_on_submit():
        service = AdminPlanService()
        service.create(
            name=form.name.data,
            description=form.description.data,
            price_reais=float(form.price.data),
            billing_cycle=form.billing_cycle.data,
            max_categories=form.max_categories.data,
            max_products=form.max_products.data,
            max_images_per_product=form.max_images_per_product.data,
            is_featured=form.is_featured.data,
            display_order=form.display_order.data,
        )
        flash("Plano criado com sucesso.", "success")
        return redirect(url_for("admin.plans_list"))

    return render_template("admin/plans/form.html", form=form, plan=None)


@admin_bp.route("/planos/<int:plan_id>/editar", methods=["GET", "POST"])
@super_admin_required
def plans_edit(plan_id):
    service = AdminPlanService()
    plan = service.get_or_404(plan_id)

    form = PlanForm(obj=plan)
    if request.method == "GET":
        form.price.data = plan.price_cents / 100
        form.billing_cycle.data = plan.billing_cycle.value

    if form.validate_on_submit():
        service.update(
            plan,
            name=form.name.data,
            description=form.description.data,
            price_reais=float(form.price.data),
            billing_cycle=form.billing_cycle.data,
            max_categories=form.max_categories.data,
            max_products=form.max_products.data,
            max_images_per_product=form.max_images_per_product.data,
            is_featured=form.is_featured.data,
            display_order=form.display_order.data,
        )
        flash("Plano atualizado com sucesso.", "success")
        return redirect(url_for("admin.plans_list"))

    return render_template("admin/plans/form.html", form=form, plan=plan)


@admin_bp.route("/planos/<int:plan_id>/alternar", methods=["POST"])
@super_admin_required
def plans_toggle(plan_id):
    service = AdminPlanService()
    plan = service.get_or_404(plan_id)
    service.toggle_active(plan)
    return render_template("admin/plans/_status_badge.html", plan=plan)
