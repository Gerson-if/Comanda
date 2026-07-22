"""
Validadores WTForms customizados e reutilizados em vários formulários.
"""

import re

from wtforms.validators import ValidationError

_PHONE_DIGITS_RE = re.compile(r"\D")


def phone_number(min_digits: int = 10, max_digits: int = 15):
    """
    Valida um número de telefone/WhatsApp de forma tolerante a formatação
    (aceita espaços, parênteses, hífens, +) mas garante que, ao remover
    tudo que não é dígito, sobre uma quantidade razoável de números —
    evita cadastrar "abc" ou "11" como telefone.
    """

    def _validator(form, field):
        if not field.data:
            return  # campo opcional é responsabilidade de Optional()
        digits = _PHONE_DIGITS_RE.sub("", field.data)
        if not (min_digits <= len(digits) <= max_digits):
            raise ValidationError(
                f"Telefone inválido. Use um número com DDD (e DDI, se WhatsApp), "
                f"entre {min_digits} e {max_digits} dígitos."
            )

    return _validator


def not_blank(form, field):
    """Rejeita um texto que só tem espaços em branco (DataRequired sozinho
    deixa passar ' ' já que não está tecnicamente vazio)."""
    if field.data and not field.data.strip():
        raise ValidationError("Este campo não pode ficar em branco.")


_SLUG_RE = re.compile(r"^[a-z0-9-]+$")


def slug_format(form, field):
    if field.data and not _SLUG_RE.fullmatch(field.data):
        raise ValidationError("Use apenas letras minúsculas, números e hífens.")
