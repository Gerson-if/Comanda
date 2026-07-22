from flask import flash, redirect, render_template, url_for

from app.forms.admin_forms import AsaasSettingsForm
from app.services.payment_gateway.base import PaymentGatewayError
from app.services.platform_settings_service import PlatformSettingsService
from app.utils.decorators import super_admin_required

from app.controllers.admin import admin_bp


@admin_bp.route("/configuracoes/asaas", methods=["GET", "POST"])
@super_admin_required
def settings_asaas():
    service = PlatformSettingsService()
    settings = service.settings
    form = AsaasSettingsForm()

    if not form.is_submitted():
        form.environment.data = settings.asaas_environment

    if form.validate_on_submit():
        service.update_asaas(
            environment=form.environment.data,
            api_key=form.api_key.data,
            clear_api_key=form.clear_api_key.data,
            webhook_token=form.webhook_token.data,
            clear_webhook_token=form.clear_webhook_token.data,
        )
        flash("Configurações do Asaas atualizadas.", "success")

        if settings.asaas_configured and not settings.asaas_webhook_configured:
            flash(
                "A chave de API está configurada, mas o token de webhook não. "
                "Sem o webhook, os pagamentos gerados no Asaas não liberam o "
                "lojista automaticamente — alguém precisa marcar a fatura como "
                "paga manualmente. Gere um token abaixo e cadastre a URL de "
                "webhook no painel do Asaas.",
                "warning",
            )
        return redirect(url_for("admin.settings_asaas"))

    webhook_url = url_for("webhooks.asaas_webhook", _external=True)

    return render_template(
        "admin/settings/asaas.html", form=form, settings=settings, webhook_url=webhook_url,
    )


@admin_bp.route("/configuracoes/asaas/gerar-token", methods=["POST"])
@super_admin_required
def settings_asaas_generate_token():
    service = PlatformSettingsService()
    token = service.generate_webhook_token()
    flash(
        f"Novo token de webhook gerado: {token} — copie agora e cadastre no "
        "painel do Asaas. Ele não será mostrado novamente nesta tela (mas você "
        "pode gerar outro a qualquer momento, sem perder a integração).",
        "success",
    )
    return redirect(url_for("admin.settings_asaas"))


@admin_bp.route("/configuracoes/asaas/testar", methods=["POST"])
@super_admin_required
def settings_asaas_test():
    service = PlatformSettingsService()
    try:
        service.test_connection()
    except PaymentGatewayError as exc:
        flash(f"Falha ao conectar com o Asaas: {exc}", "danger")
    else:
        flash("Conexão com o Asaas funcionando — a chave de API é válida.", "success")
    return redirect(url_for("admin.settings_asaas"))
