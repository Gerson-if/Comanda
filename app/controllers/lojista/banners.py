from flask import flash, make_response, redirect, render_template, request, url_for

from app.forms.banner_forms import BannerForm
from app.services.banner_service import BannerService
from app.utils.decorators import lojista_required
from app.utils.tenant_context import get_current_tenant
from app.utils.uploads import InvalidImageError

from app.controllers.lojista import lojista_bp


def _rerender_banner_fragment(banner, *, trigger=None):
    """Ver _rerender_product_fragment em products.py — mesmo padrão pro
    drawer de banners: devolve só o fragmento, com HX-Trigger opcional
    pra avisar a listagem de fundo."""
    form = BannerForm(obj=banner)
    html = render_template(
        "lojista/banners/_form_fragment.html", form=form, banner=banner,
        form_action=url_for("lojista.banners_edit", banner_id=banner.id), hide_back_link=True,
    )
    response = make_response(html)
    if trigger:
        response.headers["HX-Trigger"] = trigger
    return response


@lojista_bp.route("/banners")
@lojista_required
def banners_list():
    tenant = get_current_tenant()
    banners = BannerService(tenant).list_all()
    return render_template("lojista/banners/list.html", banners=banners)


@lojista_bp.route("/banners/novo", methods=["GET", "POST"])
@lojista_required
def banners_create():
    tenant = get_current_tenant()
    form = BannerForm()
    is_hx = bool(request.headers.get("HX-Request"))

    if form.validate_on_submit():
        if not form.image.data:
            flash("Selecione uma imagem para o banner.", "danger")
        else:
            try:
                banner = BannerService(tenant).create(
                    title=form.title.data, subtitle=form.subtitle.data, link_url=form.link_url.data,
                    file_storage=form.image.data, is_active=form.is_active.data,
                )
            except InvalidImageError as exc:
                flash(str(exc), "danger")
            else:
                if is_hx:
                    return _rerender_banner_fragment(banner, trigger="bannerSaved")
                flash("Banner criado com sucesso.", "success")
                return redirect(url_for("lojista.banners_list"))

    if is_hx:
        return render_template(
            "lojista/banners/_form_fragment.html", form=form, banner=None,
            form_action=url_for("lojista.banners_create"), hide_back_link=True,
        )
    return render_template("lojista/banners/form.html", form=form, banner=None)


@lojista_bp.route("/banners/<int:banner_id>/editar", methods=["GET", "POST"])
@lojista_required
def banners_edit(banner_id):
    tenant = get_current_tenant()
    service = BannerService(tenant)
    banner = service.get_or_404(banner_id)
    is_hx = bool(request.headers.get("HX-Request"))

    form = BannerForm(obj=banner)

    if form.validate_on_submit():
        try:
            service.update(
                banner, title=form.title.data, subtitle=form.subtitle.data, link_url=form.link_url.data,
                is_active=form.is_active.data, file_storage=form.image.data,
            )
        except InvalidImageError as exc:
            flash(str(exc), "danger")
        else:
            if is_hx:
                return _rerender_banner_fragment(banner, trigger="bannerSaved")
            flash("Banner atualizado com sucesso.", "success")
            return redirect(url_for("lojista.banners_list"))

    if is_hx:
        return render_template(
            "lojista/banners/_form_fragment.html", form=form, banner=banner,
            form_action=url_for("lojista.banners_edit", banner_id=banner.id), hide_back_link=True,
        )
    return render_template("lojista/banners/form.html", form=form, banner=banner)


@lojista_bp.route("/banners/<int:banner_id>/alternar", methods=["POST"])
@lojista_required
def banners_toggle(banner_id):
    tenant = get_current_tenant()
    service = BannerService(tenant)
    banner = service.get_or_404(banner_id)
    service.toggle_active(banner)
    return render_template("lojista/banners/_status_badge.html", banner=banner)


@lojista_bp.route("/banners/<int:banner_id>/excluir", methods=["POST"])
@lojista_required
def banners_delete(banner_id):
    tenant = get_current_tenant()
    service = BannerService(tenant)
    banner = service.get_or_404(banner_id)
    service.delete(banner)
    flash("Banner excluído.", "info")
    return redirect(url_for("lojista.banners_list"))
