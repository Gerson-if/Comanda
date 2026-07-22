"""
Camada de integração com gateway de pagamento (cobrança das faturas dos
lojistas pelo Super Admin).

Hoje só existe um gateway implementado (Asaas — asaas.com, popular no
Brasil para cobrança de SaaS via boleto/Pix/cartão), mas a estrutura em
`base.py` deixa explícito o contrato que qualquer outro gateway
precisaria implementar, caso o projeto queira adicionar um segundo no
futuro (Stripe, Pagar.me, etc.) sem reescrever `AdminBillingService`.

Uso:
    from app.services.payment_gateway import get_gateway

    gateway = get_gateway()
    if gateway is None:
        # ASAAS_API_KEY não configurada — integração desligada,
        # cobrança continua manual (fluxo já existente desde a Fase 5).
        ...
    else:
        gateway.ensure_customer(tenant)
        charge = gateway.create_charge(tenant, invoice)
"""

from flask import current_app

from app.services.payment_gateway.asaas_gateway import AsaasGateway


def get_gateway():
    """Retorna a instância do gateway configurado, ou None se nenhuma
    integração de pagamento estiver habilitada (ASAAS_API_KEY vazia)."""
    api_key = current_app.config.get("ASAAS_API_KEY")
    if not api_key:
        return None

    return AsaasGateway(
        api_key=api_key,
        environment=current_app.config.get("ASAAS_ENVIRONMENT", "sandbox"),
    )
