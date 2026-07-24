"""normalize existing customer and order phone numbers

Revision ID: 517668c2df2a
Revises: cebcdf31f318
Create Date: 2026-07-23 21:34:22.772379

"""
from alembic import op
import sqlalchemy as sa

from app.utils.phone import normalize_br_phone

# revision identifiers, used by Alembic.
revision = '517668c2df2a'
down_revision = 'cebcdf31f318'
branch_labels = None
depends_on = None


def upgrade():
    """
    Reescreve Customer.phone e Order.customer_phone existentes no
    formato canônico "(DD) NNNNN-NNNN" — daqui pra frente todo telefone
    novo já entra normalizado (ver app/utils/phone.py), mas os
    registros anteriores a essa mudança ainda estão como o cliente
    digitou. Não mescla cadastros de Customer que porventura já
    tenham sido duplicados por formatos diferentes do mesmo número
    (fora de escopo — dado de produção baixo até aqui).
    """
    connection = op.get_bind()

    customers = connection.execute(sa.text("SELECT id, phone FROM customers")).fetchall()
    for customer_id, phone in customers:
        normalized = normalize_br_phone(phone)
        if normalized and normalized != phone:
            connection.execute(
                sa.text("UPDATE customers SET phone = :phone WHERE id = :id"),
                {"phone": normalized, "id": customer_id},
            )

    orders = connection.execute(sa.text("SELECT id, customer_phone FROM orders")).fetchall()
    for order_id, phone in orders:
        normalized = normalize_br_phone(phone)
        if normalized and normalized != phone:
            connection.execute(
                sa.text("UPDATE orders SET customer_phone = :phone WHERE id = :id"),
                {"phone": normalized, "id": order_id},
            )


def downgrade():
    # Normalização de dados não é reversível (o formato original digitado
    # pelo cliente não é recuperável a partir do formato canônico).
    pass
