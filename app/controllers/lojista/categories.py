from flask import flash, redirect, render_template, request, url_for

from app.forms.category_forms import CategoryForm
from app.services.category_service import CategoryService, CategoryLimitReachedError
from app.utils.decorators import lojista_required
from app.utils.tenant_context import get_current_tenant

from app.controllers.lojista import lojista_bp


@lojista_bp.route("/categorias")
@lojista_required
def categories_list():
    tenant = get_current_tenant()
    service = CategoryService(tenant)
    categories = service.list_all()
    return render_template("lojista/categories/list.html", categories=categories)


@lojista_bp.route("/categorias/nova", methods=["GET", "POST"])
@lojista_required
def categories_create():
    tenant = get_current_tenant()
    form = CategoryForm()

    if form.validate_on_submit():
        service = CategoryService(tenant)
        try:
            service.create(name=form.name.data, is_active=form.is_active.data)
        except CategoryLimitReachedError as exc:
            flash(str(exc), "warning")
        else:
            flash("Categoria criada com sucesso.", "success")
            return redirect(url_for("lojista.categories_list"))

    return render_template("lojista/categories/form.html", form=form, category=None)


@lojista_bp.route("/categorias/<int:category_id>/editar", methods=["GET", "POST"])
@lojista_required
def categories_edit(category_id):
    tenant = get_current_tenant()
    service = CategoryService(tenant)
    category = service.get_or_404(category_id)

    form = CategoryForm(obj=category)

    if form.validate_on_submit():
        service.update(category, name=form.name.data, is_active=form.is_active.data)
        flash("Categoria atualizada com sucesso.", "success")
        return redirect(url_for("lojista.categories_list"))

    return render_template("lojista/categories/form.html", form=form, category=category)


@lojista_bp.route("/categorias/<int:category_id>/alternar", methods=["POST"])
@lojista_required
def categories_toggle(category_id):
    tenant = get_current_tenant()
    service = CategoryService(tenant)
    category = service.get_or_404(category_id)
    service.toggle_active(category)
    return render_template("lojista/categories/_status_badge.html", category=category)


@lojista_bp.route("/categorias/<int:category_id>/excluir", methods=["POST"])
@lojista_required
def categories_delete(category_id):
    tenant = get_current_tenant()
    service = CategoryService(tenant)
    category = service.get_or_404(category_id)

    service.delete(category)

    if request.headers.get("HX-Request"):
        # A linha da tabela é removida no próprio navegador via hx-swap
        # (hx-target="closest tr"); uma resposta vazia é suficiente.
        return ""

    flash("Categoria excluída. Os produtos dela ficaram sem categoria.", "info")
    return redirect(url_for("lojista.categories_list"))
