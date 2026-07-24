"""
Normalização/validação de telefone brasileiro do CLIENTE FINAL (checkout
e "Meus Pedidos" do cardápio público) — não usado para o telefone/
WhatsApp do próprio lojista (app/utils/validators.py:phone_number()
continua servindo esse caso, mais permissivo de propósito).

Único ponto de verdade: `normalize_br_phone` sempre devolve o mesmo
formato canônico para o mesmo número, não importa como foi digitado
("67999998888", "(67) 99999-9998", "+55 67 99999-9998" etc.) — isso é
o que permite que Customer.phone/Order.customer_phone comparem por
igualdade de string simples (CustomerRepository.get_by_phone) sem
precisar normalizar na hora da query.
"""

import re

_DIGITS_RE = re.compile(r"\D")


def normalize_br_phone(raw: str) -> str | None:
    """
    Retorna o telefone formatado "(DD) NNNNN-NNNN" (celular, 9 dígitos)
    ou "(DD) NNNN-NNNN" (fixo, 8 dígitos), ou None se `raw` não for um
    telefone brasileiro válido (DDD + número).
    """
    digits = _DIGITS_RE.sub("", raw or "")

    # DDI 55 opcional (com DDD+celular = 13 dígitos, com DDD+fixo = 12)
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]

    if len(digits) not in (10, 11):
        return None

    ddd, rest = digits[:2], digits[2:]
    if ddd[0] == "0":
        return None

    if len(rest) == 9:
        return f"({ddd}) {rest[:5]}-{rest[5:]}"
    return f"({ddd}) {rest[:4]}-{rest[4:]}"
