"""
Validação do payload de checkout enviado pelo cardápio público (JSON).

Importante: o cliente NUNCA envia preço — só `product_id` e `quantity`.
O preço usado no pedido é sempre o preço atual do produto no banco,
resolvido no OrderService. Isso torna impossível manipular o valor do
pedido alterando dados no navegador.
"""

import re

from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate, validates_schema

from app.models import DeliveryType, PaymentMethod

_PHONE_DIGITS_RE = re.compile(r"\D")


def _validate_phone(value: str) -> None:
    digits = _PHONE_DIGITS_RE.sub("", value or "")
    if not (10 <= len(digits) <= 15):
        raise ValidationError("Telefone inválido. Informe um número com DDD, entre 10 e 15 dígitos.")


def _validate_not_blank(value: str) -> None:
    if value is not None and not value.strip():
        raise ValidationError("Este campo não pode ficar em branco.")


class CheckoutItemSchema(Schema):
    class Meta:
        # Ignora silenciosamente qualquer campo extra (ex: um "price" que o
        # cliente tente injetar) — o preço usado é sempre o do servidor,
        # nunca o do payload, então nem faz sentido barrar a requisição
        # por isso.
        unknown = EXCLUDE

    product_id = fields.Integer(required=True, validate=validate.Range(min=1))
    quantity = fields.Integer(required=True, validate=validate.Range(min=1, max=50))
    option_ids = fields.List(
        fields.Integer(validate=validate.Range(min=1)),
        required=False,
        load_default=list,
    )


class CheckoutSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    customer_name = fields.String(required=True, validate=[validate.Length(min=2, max=150), _validate_not_blank])
    customer_phone = fields.String(required=True, validate=[validate.Length(min=8, max=20), _validate_phone])

    delivery_type = fields.String(
        required=True,
        validate=validate.OneOf([d.value for d in DeliveryType]),
    )

    address_street = fields.String(required=False, allow_none=True, validate=validate.Length(max=180))
    address_number = fields.String(required=False, allow_none=True, validate=validate.Length(max=20))
    address_complement = fields.String(required=False, allow_none=True, validate=validate.Length(max=120))
    address_neighborhood = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    address_city = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    address_reference = fields.String(required=False, allow_none=True, validate=validate.Length(max=180))

    payment_method = fields.String(
        required=True,
        validate=validate.OneOf([p.value for p in PaymentMethod]),
    )

    notes = fields.String(required=False, allow_none=True, validate=validate.Length(max=1000))

    items = fields.List(
        fields.Nested(CheckoutItemSchema),
        required=True,
        validate=validate.Length(min=1, error="O carrinho não pode estar vazio."),
    )

    @validates_schema
    def validate_delivery_address(self, data, **kwargs):
        if data.get("delivery_type") == DeliveryType.DELIVERY.value:
            required_fields = ["address_street", "address_number", "address_neighborhood"]
            missing = [f for f in required_fields if not (data.get(f) or "").strip()]
            if missing:
                raise ValidationError(
                    "Para entrega, informe rua, número e bairro.", field_name="address_street"
                )
