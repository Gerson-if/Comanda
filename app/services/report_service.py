"""
Relatórios de vendas e financeiro do lojista.

`summary()` e `top_products()` agregam com SQL (SUM/COUNT/GROUP BY —
portáveis entre SQLite e PostgreSQL, sem depender de funções de data
específicas de dialeto) em vez de carregar todos os pedidos/itens para
somar em Python, que não escalava conforme a loja acumulava histórico.

`daily_revenue_series()` continua agregando em Python: agrupar por dia de
forma portável entre SQLite/PostgreSQL exigiria funções de data específicas
de cada dialeto, e a janela é sempre pequena (dias/semanas), então o ganho
não compensa o risco.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import case, func

from app.extensions import db
from app.models import Order, OrderItem, OrderStatus

CANCELED = OrderStatus.CANCELED.value


def _aware_utc(dt: datetime) -> datetime:
    """
    Normaliza um datetime para timezone-aware (UTC).

    SQLite (usado em dev/test) não preserva timezone-awareness ao ler de
    volta uma coluna DateTime(timezone=True) — o valor volta "naive".
    PostgreSQL (produção) preserva normalmente. Esta função torna as
    comparações seguras nos dois ambientes.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ReportService:
    def __init__(self, tenant):
        self.tenant = tenant

    def _paid_orders_query(self):
        # "Receita" considera todo pedido que não foi cancelado — mesmo
        # ainda em preparo, pois já é uma venda confirmada pelo cliente.
        return Order.query.filter(
            Order.tenant_id == self.tenant.id,
            Order.status != CANCELED,
        )

    def revenue_between(self, start: datetime, end: datetime) -> int:
        orders = self._paid_orders_query().filter(
            Order.created_at >= start, Order.created_at < end
        ).all()
        return sum(o.total_cents for o in orders)

    def summary(self) -> dict:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        row = (
            db.session.query(
                func.coalesce(
                    func.sum(case((Order.created_at >= today_start, Order.total_cents), else_=0)), 0
                ),
                func.coalesce(
                    func.sum(case((Order.created_at >= week_start, Order.total_cents), else_=0)), 0
                ),
                func.coalesce(
                    func.sum(case((Order.created_at >= month_start, Order.total_cents), else_=0)), 0
                ),
                func.coalesce(func.sum(Order.total_cents), 0),
                func.count(Order.id),
            )
            .filter(Order.tenant_id == self.tenant.id, Order.status != CANCELED)
            .one()
        )

        return {
            "revenue_today_cents": int(row[0]),
            "revenue_week_cents": int(row[1]),
            "revenue_month_cents": int(row[2]),
            "revenue_total_cents": int(row[3]),
            "orders_total": int(row[4]),
        }

    def order_count_by_status(self) -> dict:
        orders = Order.query.filter(Order.tenant_id == self.tenant.id).all()
        counts = defaultdict(int)
        for order in orders:
            counts[order.status.value] += 1
        return dict(counts)

    def daily_revenue_series(self, days: int = 14) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days - 1)
        since = since.replace(hour=0, minute=0, second=0, microsecond=0)

        orders = self._paid_orders_query().all()

        by_day = defaultdict(int)
        for order in orders:
            created = _aware_utc(order.created_at)
            if created < since:
                continue
            day_key = created.date().isoformat()
            by_day[day_key] += order.total_cents

        series = []
        for i in range(days):
            day = (since + timedelta(days=i)).date()
            key = day.isoformat()
            series.append({"date": key, "revenue_cents": by_day.get(key, 0)})
        return series

    def top_products(self, limit: int = 5) -> list[dict]:
        rows = (
            db.session.query(
                OrderItem.product_name,
                func.sum(OrderItem.quantity),
                func.sum(OrderItem.subtotal_cents),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .filter(Order.tenant_id == self.tenant.id, Order.status != CANCELED)
            .group_by(OrderItem.product_name)
            .order_by(func.sum(OrderItem.subtotal_cents).desc())
            .limit(limit)
            .all()
        )
        return [
            {"name": name, "quantity": int(quantity), "revenue_cents": int(revenue_cents)}
            for name, quantity, revenue_cents in rows
        ]
