from flask import flash, redirect, render_template, request, url_for

from app.forms.product_forms import ProductForm, ImageUploadForm
from app.forms.complement_forms import ComplementGroupForm, ComplementOptionForm
from app.services.category_service import CategoryService
from app.services.product_service import ProductService, ProductLimitReachedError
from app.utils.decorators import lojista_required
from app.utils.tenant_context import get_current_tenant

from app.controllers.lojista import lojista_bp


def _populate_category_choices(form, tenant):
    categories = CategoryService(tenant).list_all()
    form.category_id.choices = [(0, "Sem categoria")] + [(c.id, c.name) for c in categories]


@lojista_bp.route("/produtos")
@lojista_required
def products_list():
    tenant = get_current_tenant()
    category_id = request.args.get("categoria", type=int)
    page = request.args.get("page", 1, type=int)

    service = ProductService(tenant)
    pagination = service.repo.paginated(page=page, per_page=12, category_id=category_id)
    categories = CategoryService(tenant).list_all()

    return render_template(
        "lojista/products/list.html",
        products=pagination.items,
        pagination=pagination,
        categories=categories,
        selected_category_id=category_id,
    )


@lojista_bp.route("/produtos/novo", methods=["GET", "POST"])
@lojista_required
def products_create():
    tenant = get_current_tenant()
    form = ProductForm()
    _populate_category_choices(form, tenant)

    if form.validate_on_submit():
        service = ProductService(tenant)
        try:
            product = service.create(
                name=form.name.data,
                description=form.description.data,
                price_reais=float(form.price.data),
                cost_price_reais=float(form.cost_price.data) if form.cost_price.data is not None else None,
                category_id=form.category_id.data or None,
                is_active=form.is_active.data,
            )
        except ProductLimitReachedError as exc:
            flash(str(exc), "warning")
        else:
            flash("Produto criado com sucesso. Agora envie as fotos dele.", "success")
            return redirect(url_for("lojista.products_edit", product_id=product.id))

    return render_template("lojista/products/form.html", form=form, product=None)


@lojista_bp.route("/produtos/<int:product_id>/editar", methods=["GET", "POST"])
@lojista_required
def products_edit(product_id):
    tenant = get_current_tenant()
    service = ProductService(tenant)
    product = service.get_or_404(product_id)

    form = ProductForm(obj=product)
    if request.method == "GET":
        form.price.data = product.price_cents / 100
        form.cost_price.data = (product.cost_price_cents / 100) if product.cost_price_cents else None
        form.category_id.data = product.category_id or 0
    _populate_category_choices(form, tenant)

    if form.validate_on_submit():
        service.update(
            product,
            name=form.name.data,
            description=form.description.data,
            price_reais=float(form.price.data),
            cost_price_reais=float(form.cost_price.data) if form.cost_price.data is not None else None,
            category_id=form.category_id.data or None,
            is_active=form.is_active.data,
        )
        flash("Produto atualizado com sucesso.", "success")
        return redirect(url_for("lojista.products_edit", product_id=product.id))

    image_form = ImageUploadForm()

    return render_template(
        "lojista/products/form.html",
        form=form,
        product=product,
        image_form=image_form,
        group_form=ComplementGroupForm(),
        option_form=ComplementOptionForm(),
    )


@lojista_bp.route("/produtos/<int:product_id>/alternar", methods=["POST"])
@lojista_required
def products_toggle(product_id):
    tenant = get_current_tenant()
    service = ProductService(tenant)
    product = service.get_or_404(product_id)
    service.toggle_active(product)
    return render_template("lojista/products/_status_badge.html", product=product)


@lojista_bp.route("/produtos/<int:product_id>/excluir", methods=["POST"])
@lojista_required
def products_delete(product_id):
    tenant = get_current_tenant()
    service = ProductService(tenant)
    product = service.get_or_404(product_id)

    service.delete(product)

    if request.headers.get("HX-Request"):
        # Chamado a partir do card na listagem — o próprio card é removido
        # no navegador (hx-target="#product-card-<id>"), sem navegação.
        return ""

    flash("Produto excluído.", "info")
    return redirect(url_for("lojista.products_list"))
