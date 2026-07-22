"""
Regras de negócio de cobrança pelo Super Administrador.

Fluxo:
1. Cada tenant tem (ou ganha, na primeira fatura) uma Subscription ativa
   vinculada ao seu plano atual.
2. Faturas (Invoice) são lançadas manualmente pelo Super Admin.
3. Opcionalmente, se a integração com o Asaas estiver configurada
   (`ASAAS_API_KEY`), o Super Admin pode gerar uma cobrança real
   (boleto/Pix/cartão) para a fatura — ver `generate_asaas_charge`.
   Sem isso configurado, o fluxo manual (marcar como paga na mão)
   continua funcionando normalmente.
4. Marcar uma fatura como paga (manualmente, ou automaticamente via
   webhook do Asaas quando o pagamento é confirmado) é o gatilho que
   **libera automaticamente** um tenant que estava bloqueado por
   inadimplência.
"""

from datetime import date, datetime, timedelta, timezone

from app.extensions import db
from app.models import BillingCycle, Invoice, InvoiceStatus, Subscription, SubscriptionStatus, TenantStatus
from app.repositories.billing_repository import InvoiceRepository, SubscriptionRepository
from app.services.payment_gateway import get_gateway
from app.services.payment_gateway.base import PaymentGatewayError


class BillingError(Exception):
    pass


class AdminBillingService:
    def __init__(self):
        self.subscription_repo = SubscriptionRepository()
        self.invoice_repo = InvoiceRepository()

    def list_invoices_for_tenant(self, tenant_id: int):
        return self.invoice_repo.list_for_tenant(tenant_id)

    def get_invoice_or_404(self, invoice_id: int) -> Invoice:
        from flask import abort

        invoice = self.invoice_repo.get_by_id(invoice_id)
        if invoice is None:
            abort(404)
        return invoice

    def _get_or_create_subscription(self, tenant) -> Subscription:
        subscription = self.subscription_repo.get_active_for_tenant(tenant.id)
        if subscription is not None:
            return subscription

        if tenant.plan is None:
            raise BillingError("Este lojista não tem um plano associado. Defina um plano antes de lançar faturas.")

        period_days = 365 if tenant.plan.billing_cycle == BillingCycle.YEARLY else 30
        today = date.today()

        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=tenant.plan_id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=today,
            current_period_end=today + timedelta(days=period_days),
        )
        db.session.add(subscription)
        db.session.flush()
        return subscription

    def create_invoice(self, tenant, *, amount_reais: float, due_date: date) -> Invoice:
        subscription = self._get_or_create_subscription(tenant)

        invoice = Invoice(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            amount_cents=round(amount_reais * 100),
            status=InvoiceStatus.PENDING,
            due_date=due_date,
        )
        db.session.add(invoice)
        db.session.commit()
        return invoice

    def mark_paid(self, invoice: Invoice):
        """Marca a fatura como paga e libera o tenant se ele estava
        bloqueado por inadimplência (validação de pagamento)."""
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = datetime.now(timezone.utc)

        tenant = invoice.tenant
        if tenant.status == TenantStatus.BLOCKED_PAYMENT:
            tenant.status = TenantStatus.ACTIVE
            tenant.blocked_reason = None
            tenant.blocked_at = None

        if invoice.subscription.status == SubscriptionStatus.PAST_DUE:
            invoice.subscription.status = SubscriptionStatus.ACTIVE

        db.session.commit()
        return invoice

    def mark_overdue(self, invoice: Invoice):
        invoice.status = InvoiceStatus.OVERDUE
        if invoice.subscription:
            invoice.subscription.status = SubscriptionStatus.PAST_DUE
        db.session.commit()
        return invoice

    def cancel_invoice(self, invoice: Invoice):
        invoice.status = InvoiceStatus.CANCELED
        db.session.commit()
        return invoice

    # --- Integração Asaas ---
    def is_asaas_configured(self) -> bool:
        return get_gateway() is not None

    def generate_asaas_charge(self, invoice: Invoice) -> Invoice:
        """
        Gera (ou reaproveita) uma cobrança real no Asaas para esta
        fatura, e salva o link de pagamento. Não marca a fatura como
        paga — isso só acontece quando o pagamento é de fato confirmado
        (webhook do Asaas, ver app/controllers/webhooks_controller.py,
        ou manualmente pelo Super Admin como já era possível antes).
        """
        gateway = get_gateway()
        if gateway is None:
            raise BillingError(
                "Integração com o Asaas não está configurada. Defina a variável "
                "de ambiente ASAAS_API_KEY para habilitar cobrança automática."
            )

        if invoice.asaas_payment_id:
            raise BillingError("Esta fatura já tem uma cobrança Asaas gerada.")

        try:
            charge = gateway.create_charge(invoice.tenant, invoice)
        except PaymentGatewayError as exc:
            raise BillingError(str(exc)) from exc

        invoice.asaas_payment_id = charge["id"]
        invoice.payment_link_url = charge.get("payment_url")
        db.session.commit()
        return invoice

    def mark_paid_by_asaas_payment_id(self, asaas_payment_id: str) -> Invoice | None:
        """Usado pelo webhook: localiza a fatura pelo ID da cobrança no
        Asaas e marca como paga. Retorna None se não encontrar (ex:
        webhook de uma cobrança que não foi gerada por este sistema —
        ignorado silenciosamente, não é um erro)."""
        invoice = Invoice.query.filter_by(asaas_payment_id=asaas_payment_id).first()
        if invoice is None:
            return None
        if invoice.status == InvoiceStatus.PAID:
            return invoice  # já processado (webhook pode reenviar o mesmo evento)
        return self.mark_paid(invoice)
